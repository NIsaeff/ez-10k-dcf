"""Entrypoint for Databricks Apps (and any other "one process from the root" host).

The app itself lives in `backend/` (FastAPI full-stack template layout), while the
platform starts a single command from the repo root, so this puts `backend/` on
`sys.path` and binds the port the platform assigns.

Locally you never need this: `./backend/scripts/dev-backend.sh` runs `fastapi dev`
from inside `backend/`. Use it when something starts the app from the root, e.g.

    DATABRICKS_APP_PORT=8000 uv run python serve.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import uvicorn

BACKEND_DIR = Path(__file__).resolve().parent / "backend"
# Must happen before uvicorn resolves "app.main:app", not at module import time.
sys.path.insert(0, str(BACKEND_DIR))


def main() -> None:
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=int(os.environ.get("DATABRICKS_APP_PORT", "8000")),
        # Databricks terminates TLS and forwards; trust its X-Forwarded-* headers
        # so redirects and absolute URLs keep the public scheme and host.
        proxy_headers=True,
        forwarded_allow_ips="*",
    )


if __name__ == "__main__":
    main()
