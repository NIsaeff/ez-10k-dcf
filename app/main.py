from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from app.config import settings
from app.schemas import ChatRequest, ChatResponse

app = FastAPI(title=settings.project_name)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/chat", response_model=ChatResponse)
def chat(payload: ChatRequest) -> ChatResponse:
    """Phase 1 stub: echo the last user message.

    The real pipeline (ticker → EDGAR → DCF) and LLM narration land in Phase 4.
    """
    last_user = next(
        (message for message in reversed(payload.messages) if message.role == "user"),
        payload.messages[-1],
    )
    return ChatResponse(reply=f"Echo: {last_user.content}")


if settings.frontend_dist.is_dir():
    app.frontend("/", directory=settings.frontend_dist)
else:

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def index() -> str:
        return (
            "<p>Frontend not built. Run "
            "<code>cd frontend &amp;&amp; bun run build</code>.</p>"
        )
