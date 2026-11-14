"""FRED MCP wiring: schemas, tool execution and the chat tool loop.

Everything here is offline: the MCP child process and the LLM client are faked.
"""

from types import SimpleNamespace

from app import llm
from app.services import fred_mcp


def fake_tool(name: str = "fred_search", schema: dict | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        name=name,
        description="Search FRED series",
        input_schema=schema
        or {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "properties": {"search_text": {"type": "string"}},
        },
    )


def test_openai_tools_uses_server_schema_without_dialect(monkeypatch) -> None:
    fred_mcp.reset_cache()
    monkeypatch.setattr(fred_mcp, "_run", lambda action: [fake_tool()])

    tools = fred_mcp.openai_tools()

    assert tools[0]["type"] == "function"
    assert tools[0]["function"]["name"] == "fred_search"
    assert "$schema" not in tools[0]["function"]["parameters"]
    assert tools[0]["function"]["parameters"]["properties"] == {
        "search_text": {"type": "string"}
    }


def test_openai_tools_are_cached(monkeypatch) -> None:
    fred_mcp.reset_cache()
    calls: list[int] = []

    def fake_run(action):
        calls.append(1)
        return [fake_tool()]

    monkeypatch.setattr(fred_mcp, "_run", fake_run)
    fred_mcp.openai_tools()
    fred_mcp.openai_tools()

    assert len(calls) == 1


def test_render_joins_text_blocks_and_truncates() -> None:
    result = SimpleNamespace(content=[SimpleNamespace(text="a"), SimpleNamespace(text="b")])
    assert fred_mcp._render(result) == "a\nb"

    long = SimpleNamespace(content=[SimpleNamespace(text="x" * 10_000)])
    rendered = fred_mcp._render(long)
    assert len(rendered) < 10_000
    assert rendered.endswith("…(truncated)")


def test_configured_needs_key_and_flag(monkeypatch) -> None:
    monkeypatch.setattr(fred_mcp.settings, "fred_api_key", "")
    assert fred_mcp.configured() is False

    monkeypatch.setattr(fred_mcp.settings, "fred_api_key", "key")
    monkeypatch.setattr(fred_mcp.settings, "fred_mcp_enabled", False)
    assert fred_mcp.configured() is False

    monkeypatch.setattr(fred_mcp.settings, "fred_mcp_enabled", True)
    assert fred_mcp.configured() is True


class FakeClient:
    """Minimal OpenAI-compatible client returning scripted messages."""

    def __init__(self, messages: list) -> None:
        self._messages = list(messages)
        self.requests: list[dict] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.requests.append(kwargs)
        message = self._messages.pop(0)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def tool_call(name: str = "fred_get_series", arguments: str = '{"series_id":"DGS10"}') -> SimpleNamespace:
    return SimpleNamespace(
        id="call_1",
        function=SimpleNamespace(name=name, arguments=arguments),
    )


def test_chat_reply_executes_tool_then_answers(monkeypatch) -> None:
    monkeypatch.setattr(fred_mcp.settings, "fred_api_key", "key")
    monkeypatch.setattr(fred_mcp.settings, "fred_mcp_enabled", True)
    monkeypatch.setattr(fred_mcp, "openai_tools", lambda: [{"type": "function"}])
    monkeypatch.setattr(fred_mcp, "call_tool", lambda name, args: "DGS10=4.12 (2026-11-12)")

    client = FakeClient(
        [
            SimpleNamespace(content="", tool_calls=[tool_call()]),
            SimpleNamespace(content="The 10Y yield is 4.12%.", tool_calls=None),
        ]
    )
    monkeypatch.setattr(llm, "get_client", lambda: client)

    reply, trace, _proposals = llm.chat_reply([{"role": "user", "content": "10Y yield?"}])

    assert reply == "The 10Y yield is 4.12%."
    assert [step["tool"] for step in trace] == ["fred_get_series"]
    assert trace[0]["status"] == "ok"
    assert trace[0]["input"] == {"series_id": "DGS10"}
    assert trace[0]["duration_ms"] >= 0
    assert "4.12" in trace[0]["output"]
    # The second round must carry the tool result back to the model.
    tool_turns = [m for m in client.requests[1]["messages"] if m["role"] == "tool"]
    assert tool_turns[0]["tool_call_id"] == "call_1"
    assert "4.12" in tool_turns[0]["content"]


def test_chat_reply_reports_tool_errors_to_the_model(monkeypatch) -> None:
    monkeypatch.setattr(fred_mcp.settings, "fred_api_key", "key")
    monkeypatch.setattr(fred_mcp.settings, "fred_mcp_enabled", True)
    monkeypatch.setattr(fred_mcp, "openai_tools", lambda: [{"type": "function"}])

    def boom(name: str, args: dict) -> str:
        raise fred_mcp.FredMCPError("FRED_API_KEY is not set")

    monkeypatch.setattr(fred_mcp, "call_tool", boom)
    client = FakeClient(
        [
            SimpleNamespace(content="", tool_calls=[tool_call()]),
            SimpleNamespace(content="I couldn't reach FRED.", tool_calls=None),
        ]
    )
    monkeypatch.setattr(llm, "get_client", lambda: client)

    reply, trace, _proposals = llm.chat_reply([{"role": "user", "content": "10Y?"}])

    assert reply == "I couldn't reach FRED."
    assert [step["status"] for step in trace] == ["error"]
    tool_turn = next(m for m in client.requests[1]["messages"] if m["role"] == "tool")
    assert tool_turn["content"].startswith("ERROR calling fred_get_series")


def test_chat_reply_skips_fred_tools_when_unconfigured(monkeypatch) -> None:
    monkeypatch.setattr(fred_mcp.settings, "fred_api_key", "")
    seen: dict[str, list[str]] = {}

    class _Message:
        def __init__(self) -> None:
            self.content = "plain reply"
            self.tool_calls: list = []

    def fake_complete(messages, tools):
        seen["tools"] = [tool["function"]["name"] for tool in tools]
        return _Message()

    monkeypatch.setattr(llm, "_complete_with_tools", fake_complete)

    reply, trace, _proposals = llm.chat_reply([{"role": "user", "content": "hi"}])

    assert reply == "plain reply"
    assert trace == []
    assert "fred_get_series" not in seen["tools"]
    # Wizard tools stay available even without FRED.
    assert "propose_wizard_change" in seen["tools"]


def test_chat_reply_survives_a_broken_mcp_server(monkeypatch) -> None:
    monkeypatch.setattr(fred_mcp.settings, "fred_api_key", "key")
    monkeypatch.setattr(fred_mcp.settings, "fred_mcp_enabled", True)

    def boom() -> list:
        raise fred_mcp.FredMCPError("Connection closed")

    monkeypatch.setattr(fred_mcp, "openai_tools", boom)

    class _Message:
        def __init__(self) -> None:
            self.content = "plain reply"
            self.tool_calls: list = []

    seen: dict[str, list[str]] = {}

    def fake_complete(messages, tools):
        seen["tools"] = [tool["function"]["name"] for tool in tools]
        return _Message()

    monkeypatch.setattr(llm, "_complete_with_tools", fake_complete)

    reply, trace, _proposals = llm.chat_reply([{"role": "user", "content": "hi"}])

    assert reply == "plain reply"
    assert trace == []
    assert seen["tools"] == ["propose_wizard_change", "propose_navigation", "wizard_explain_assumption"]


def test_series_sources_reads_only_successful_get_series() -> None:
    trace = [
        {"tool": "fred_search", "status": "ok", "output": '{"series_id":"NOPE"}'},
        {"tool": "fred_get_series", "status": "error", "output": '{"series_id":"BAD"}'},
        {
            "tool": "fred_get_series",
            "status": "ok",
            "output": (
                '{"series_id":"DGS10","title":"10Y","units":"Percent",'
                '"data":[{"date":"2026-11-11"},{"date":"2026-11-12"}]}'
            ),
        },
        # Same series twice in one turn must not duplicate the chip.
        {
            "tool": "fred_get_series",
            "status": "ok",
            "output": '{"series_id":"DGS10","title":"10Y","units":"Percent"}',
        },
    ]
    assert fred_mcp.series_sources(trace) == [
        {
            "id": "DGS10",
            "title": "10Y",
            "units": "Percent",
            "date": "2026-11-12",
            "url": "https://fred.stlouisfed.org/series/DGS10",
        }
    ]


def test_series_sources_survives_truncated_output() -> None:
    # Metadata sits above the observation array, so a hard cut still parses.
    truncated = (
        '{\n  "series_id": "CPIAUCSL",\n  "title": "CPI",\n  "units": "Index",\n'
        '  "data": [{"date": "2026-10-01", "value": 3'
    )
    sources = fred_mcp.series_sources(
        [{"tool": "fred_get_series", "status": "ok", "output": truncated}]
    )
    assert sources[0]["id"] == "CPIAUCSL"
    assert sources[0]["date"] == "2026-10-01"


def test_series_sources_ignores_output_without_a_series_id() -> None:
    assert (
        fred_mcp.series_sources(
            [{"tool": "fred_get_series", "status": "ok", "output": "garbage"}]
        )
        == []
    )


def test_health_is_disabled_without_a_key(monkeypatch) -> None:
    fred_mcp.reset_cache()
    monkeypatch.setattr(fred_mcp.settings, "fred_api_key", "")
    assert fred_mcp.health() == "disabled"


def test_health_reports_stdio_transport(monkeypatch) -> None:
    fred_mcp.reset_cache()
    monkeypatch.setattr(fred_mcp.settings, "fred_api_key", "key")
    monkeypatch.setattr(fred_mcp.settings, "fred_mcp_transport", "stdio")
    assert fred_mcp.health() == "stdio"


def test_health_probes_the_sidecar_once(monkeypatch) -> None:
    fred_mcp.reset_cache()
    monkeypatch.setattr(fred_mcp.settings, "fred_api_key", "key")
    monkeypatch.setattr(fred_mcp.settings, "fred_mcp_transport", "http")

    probes: list[str] = []

    def probe() -> str:
        probes.append("probe")
        return "ok"

    monkeypatch.setattr(fred_mcp, "_probe_healthz", probe)

    assert fred_mcp.health() == "ok"
    assert fred_mcp.health() == "ok"
    assert len(probes) == 1


def test_transport_errors_point_at_the_sidecar_script(monkeypatch) -> None:
    monkeypatch.setattr(fred_mcp.settings, "fred_mcp_transport", "http")
    hint = fred_mcp._hint("Connection refused")
    assert "./scripts/dev-mcp.sh" in hint
    assert fred_mcp.settings.fred_mcp_url in hint


def test_stdio_errors_do_not_mention_the_sidecar(monkeypatch) -> None:
    monkeypatch.setattr(fred_mcp.settings, "fred_mcp_transport", "stdio")
    assert fred_mcp._hint("Connection closed") == "Connection closed"
