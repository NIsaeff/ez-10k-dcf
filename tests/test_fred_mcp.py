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

    reply, tools_used = llm.chat_reply([{"role": "user", "content": "10Y yield?"}])

    assert reply == "The 10Y yield is 4.12%."
    assert tools_used == ["fred_get_series"]
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

    reply, tools_used = llm.chat_reply([{"role": "user", "content": "10Y?"}])

    assert reply == "I couldn't reach FRED."
    assert tools_used == ["fred_get_series"]
    tool_turn = next(m for m in client.requests[1]["messages"] if m["role"] == "tool")
    assert tool_turn["content"].startswith("ERROR calling fred_get_series")


def test_chat_reply_skips_tools_when_unconfigured(monkeypatch) -> None:
    monkeypatch.setattr(fred_mcp.settings, "fred_api_key", "")
    monkeypatch.setattr(llm, "complete", lambda messages, **_: "plain reply")

    reply, tools_used = llm.chat_reply([{"role": "user", "content": "hi"}])

    assert reply == "plain reply"
    assert tools_used == []


def test_chat_reply_survives_a_broken_mcp_server(monkeypatch) -> None:
    monkeypatch.setattr(fred_mcp.settings, "fred_api_key", "key")
    monkeypatch.setattr(fred_mcp.settings, "fred_mcp_enabled", True)

    def boom() -> list:
        raise fred_mcp.FredMCPError("Connection closed")

    monkeypatch.setattr(fred_mcp, "openai_tools", boom)
    monkeypatch.setattr(llm, "complete", lambda messages, **_: "plain reply")

    reply, tools_used = llm.chat_reply([{"role": "user", "content": "hi"}])

    assert (reply, tools_used) == ("plain reply", [])
