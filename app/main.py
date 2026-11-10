from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

ROOT_DIR = Path(__file__).resolve().parent.parent
# TODO define title once for fullstack: DRY principle
app = FastAPI(title="EZ-10k: Agentic DCF")

FRONTEND_DIST = ROOT_DIR / "frontend" / "dist"

    
@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

if FRONTEND_DIST.is_dir():
    app.frontend("/", directory=FRONTEND_DIST)
else:
    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def index() -> str:
        return "<p>Frontend is broken as shit. Run <code>cd frontend && bun... </code>.</p>"
