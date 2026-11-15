# backend

The FastAPI app: SEC EDGAR ingestion, the deterministic DCF engine, the LLM narration
and proposal tools, and the SPA mount.

It is the `uv` project for the repo (`pyproject.toml`, `uv.lock`), following the
[FastAPI full-stack template](https://github.com/fastapi/full-stack-fastapi-template)
layout. The React app lives in `../frontend/`.

```bash
uv sync                                  # workspace root; works from here too
./scripts/dev-backend.sh                 # API on PORT (repo-root .env)
uv run pytest -q
uvx ruff check app scripts tests
```

`pyproject.toml` here is the project, but `uv.lock` and the venv live at the repo root:
the root `pyproject.toml` declares a uv workspace with `members = ["backend"]`, which is
what lets Databricks run `uv sync` at the app root.

Paths the two halves share resolve to the repo root, not here: `.env`,
`frontend/dist` and `data/` all sit one level up (`app/config.py`). See the root
`README.md` for the full picture and `../docs/databricks.md` for deployment.
