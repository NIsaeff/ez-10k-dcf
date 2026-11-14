"""FRED macro data, reached through the third-party ``fred-mcp-server``.

The MCP server is an external Node process (AGPL-3.0) that we launch over stdio;
nothing from it is imported or vendored into this repo. This app owns
``FRED_API_KEY``: it reads the key from :mod:`app.config` and injects it into
that child process's environment, so the secret has exactly one owner.
"""

from __future__ import annotations

import asyncio
import os
import threading
from collections.abc import Awaitable, Callable
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

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
    """Start the server, run one action against it, then shut it down."""

    async def main() -> T:
        async with (
            stdio_client(_server_params()) as (read, write),
            ClientSession(read, write) as session,
        ):
            await session.initialize()
            return await action(session)

    try:
        return asyncio.run(asyncio.wait_for(main(), TIMEOUT_SECONDS))
    except FredMCPError:
        raise
    except TimeoutError as exc:
        raise FredMCPError(f"FRED MCP timed out after {TIMEOUT_SECONDS:.0f}s") from exc
    except BaseExceptionGroup as group:  # anyio wraps subprocess failures
        raise FredMCPError(_flatten(group)) from group
    except Exception as exc:
        raise FredMCPError(f"{type(exc).__name__}: {exc}") from exc


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
    """Drop cached tool schemas (used by tests)."""
    global _tools_cache
    with _tools_lock:
        _tools_cache = None
