#!/usr/bin/env bash
# Run the FRED MCP server as a long-lived HTTP sidecar.
#
# Chat connects to it over HTTP (FRED_MCP_URL), so the server's response cache and
# rate limiter survive between turns and across app reloads. Spawning the server
# per call throws that state away on every request.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

export PORT="${FRED_MCP_PORT:-3101}"
export TRANSPORT=http
export LOG_LEVEL=error
export npm_config_loglevel=error
export npm_config_update_notifier=false

echo "FRED MCP sidecar → http://127.0.0.1:${PORT}/mcp (cache ttl ${FRED_CACHE_TTL_MS:-60000} ms)"

# 1.2.0's isMainModule guard never matches when node is handed the npx symlink,
# so resolve the real entrypoint — same workaround as app/services/fred_mcp.py.
exec npx -y --package "${FRED_MCP_PACKAGE:-fred-mcp-server}" -c \
  'exec node "$(readlink -f "$(command -v fred-mcp-server)")" --http'
