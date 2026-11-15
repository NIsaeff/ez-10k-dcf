"""FRED macro data, reached through the third-party ``fred-mcp-server``.

The MCP server is an external Node process (AGPL-3.0) that we launch over stdio;
nothing from it is imported or vendored into this repo. This app owns
``FRED_API_KEY``: it reads the key from :mod:`app.config` and injects it into
that child process's environment, so the secret has exactly one owner.
"""

from __future__ import annotations

import asyncio
import os
import re
import threading
import time
import urllib.request
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamable_http_client

from app.config import settings

TIMEOUT_SECONDS = 45.0
MAX_RESULT_CHARS = 6_000

# fred-mcp-server 1.2.0 only starts when ``process.argv[1]`` is the real path of
# its entrypoint: its ``isMainModule`` guard compares that against
# ``import.meta.url``. ``npx`` puts a symlink on PATH, so the packaged bin exits
# silently and the client sees "Connection closed". Resolve the link and hand
# Node the real file instead.
_LAUNCH = 'exec node "$(readlink -f "$(command -v fred-mcp-server)")"'

_tools_cache: list[dict[str, Any]] | None = None
_tools_lock = threading.Lock()


class FredMCPError(RuntimeError):
    """The FRED MCP server is unreachable, misconfigured, or failed a tool call."""


def configured() -> bool:
    """True when the chat should offer FRED tools to the model."""
    return settings.fred_mcp_enabled and bool(settings.fred_api_key)


HEALTH_TTL_SECONDS = 10.0
_health_cache: tuple[float, str] | None = None
_health_lock = threading.Lock()


def _healthz_url() -> str:
    return settings.fred_mcp_url.removesuffix("/mcp").rstrip("/") + "/healthz"


def _probe_healthz() -> str:
    try:
        with urllib.request.urlopen(_healthz_url(), timeout=1.5) as response:
            return "ok" if response.status == 200 else "down"
    except Exception:  # noqa: BLE001 - health must never raise
        return "down"


def health() -> str:
    """ok | down | stdio | disabled, cached so /api/health stays cheap."""
    global _health_cache
    if not configured():
        return "disabled"
    if settings.fred_mcp_transport != "http":
        return "stdio"

    now = time.monotonic()
    with _health_lock:
        if _health_cache is not None and now - _health_cache[0] < HEALTH_TTL_SECONDS:
            return _health_cache[1]

    status = _probe_healthz()
    with _health_lock:
        _health_cache = (now, status)
    return status



def _server_params() -> StdioServerParameters:
    if not settings.fred_api_key:
        raise FredMCPError("FRED_API_KEY is not set. Add it to .env.")

    env = {
        **os.environ,
        "FRED_API_KEY": settings.fred_api_key,
        # stdout is the MCP transport; logs belong on stderr and at low volume.
        "LOG_LEVEL": "error",
        "TRANSPORT": "stdio",
        # npx prints "npm notice run ..." chatter on every launch otherwise.
        "npm_config_loglevel": "error",
        "npm_config_update_notifier": "false",
    }
    return StdioServerParameters(
        command="npx",
        args=["-y", "--package", settings.fred_mcp_package, "-c", _LAUNCH],
        env=env,
    )


def _flatten(error: BaseException) -> str:
    """anyio/task-group failures arrive nested; surface the leaf messages."""
    leaves: list[str] = []
    pending: list[BaseException] = [error]
    while pending:
        current = pending.pop()
        nested = getattr(current, "exceptions", None)
        if nested:
            pending.extend(nested)
        else:
            leaves.append(f"{type(current).__name__}: {current}")
    return "; ".join(leaves)


def _run[T](action: Callable[[ClientSession], Awaitable[T]]) -> T:
    """Run one action against the MCP server."""

    async def main() -> T:
        async with _session() as session:
            return await action(session)

    try:
        return asyncio.run(asyncio.wait_for(main(), TIMEOUT_SECONDS))
    except FredMCPError:
        raise
    except TimeoutError as exc:
        raise FredMCPError(
            _hint(f"FRED MCP timed out after {TIMEOUT_SECONDS:.0f}s")
        ) from exc
    except BaseExceptionGroup as group:  # anyio wraps subprocess failures
        raise FredMCPError(_hint(_flatten(group))) from group
    except Exception as exc:
        raise FredMCPError(_hint(f"{type(exc).__name__}: {exc}")) from exc


@asynccontextmanager
async def _session() -> AsyncIterator[ClientSession]:
    """One MCP session, over HTTP to the sidecar or over a fresh stdio child."""
    if settings.fred_mcp_transport == "stdio":
        async with (
            stdio_client(_server_params()) as (read, write),
            ClientSession(read, write) as session,
        ):
            await session.initialize()
            yield session
        return

    async with (
        streamable_http_client(settings.fred_mcp_url) as (read, write),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        yield session


def _hint(message: str) -> str:
    if settings.fred_mcp_transport == "stdio":
        return message
    return (
        f"{message}\nIs the FRED MCP sidecar running? Start it with "
        f"./scripts/dev-mcp.sh (expected at {settings.fred_mcp_url})."
    )


def _openai_tool(tool: Any) -> dict[str, Any]:
    schema = dict(tool.input_schema or {"type": "object", "properties": {}})
    schema.pop("$schema", None)
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": (tool.description or "")[:1024],
            "parameters": schema,
        },
    }


async def _list_tools(session: ClientSession) -> list[Any]:
    return list((await session.list_tools()).tools)


def openai_tools() -> list[dict[str, Any]]:
    """The server's own tool schemas, shaped for OpenAI ``tools=``."""
    global _tools_cache
    with _tools_lock:
        if _tools_cache is None:
            _tools_cache = [_openai_tool(tool) for tool in _run(_list_tools)]
    return _tools_cache


def _render(result: Any) -> str:
    parts: list[str] = []
    for block in result.content or []:
        text = getattr(block, "text", None)
        parts.append(text if text else block.model_dump_json())
    rendered = "\n".join(parts) or "(no content)"
    if len(rendered) > MAX_RESULT_CHARS:
        rendered = rendered[:MAX_RESULT_CHARS] + "\n…(truncated)"
    return rendered


async def _call(session: ClientSession, name: str, arguments: dict[str, Any]) -> str:
    result = await session.call_tool(name, arguments)
    rendered = _render(result)
    if result.is_error:
        raise FredMCPError(rendered)
    return rendered


def call_tool(name: str, arguments: dict[str, Any]) -> str:
    """Execute one MCP tool call and return its text payload."""
    return _run(lambda session: _call(session, name, arguments))


def reset_cache() -> None:
    """Drop cached tool schemas and health state (used by tests)."""
    global _tools_cache, _health_cache
    with _tools_lock, _health_lock:
        _tools_cache = None
        _health_cache = None


_SERIES_ID = re.compile(r'"series_id"\s*:\s*"([A-Za-z0-9_-]+)"')
_SERIES_TITLE = re.compile(r'"title"\s*:\s*"([^"]*)"')
_SERIES_UNITS = re.compile(r'"units"\s*:\s*"([^"]*)"')
_DATE = re.compile(r'"date"\s*:\s*"(\d{4}-\d{2}-\d{2})"')


def _first(pattern: re.Pattern[str], text: str) -> str:
    match = pattern.search(text)
    return match.group(1) if match else ""


def series_sources(trace: list[dict[str, Any]]) -> list[dict[str, str]]:
    """FRED series actually fetched, as citation chips.

    Reads the call output rather than the arguments, so a series that failed to
    load is never cited. Metadata sits at the top of the JSON, ahead of the
    observation array, so the regex still works on truncated output.
    """
    seen: set[str] = set()
    sources: list[dict[str, str]] = []

    for step in trace:
        if step.get("tool") != "fred_get_series" or step.get("status") != "ok":
            continue
        output = str(step.get("output") or "")
        series_id = _first(_SERIES_ID, output)
        if not series_id or series_id in seen:
            continue
        seen.add(series_id)
        dates = _DATE.findall(output)
        sources.append(
            {
                "id": series_id,
                "title": _first(_SERIES_TITLE, output),
                "units": _first(_SERIES_UNITS, output),
                "date": max(dates) if dates else "",
                "url": f"https://fred.stlouisfed.org/series/{series_id}",
            }
        )

    return sources

