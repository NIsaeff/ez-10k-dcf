#!/usr/bin/env bash
# Start the API on the port declared in the repo-root .env.
#
# `fastapi dev` reads its --port from an env var named PORT, and uv does not
# load .env on its own, so this wrapper passes the file through. Everything
# else is the plain `uv run fastapi dev app/main.py` executed from backend/.
set -euo pipefail
cd "$(dirname "$0")/.."
REPO_ROOT="$(cd .. && pwd)"

env_args=()
if [ -f "$REPO_ROOT/.env" ]; then
  env_args=(--env-file "$REPO_ROOT/.env")
fi

exec uv run "${env_args[@]}" fastapi dev app/main.py "$@"
