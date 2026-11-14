from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    project_name: str = "EZ-10k: Agentic DCF"
    frontend_dist: Path = ROOT_DIR / "frontend" / "dist"

    # OpenAI-compatible provider (LiteLLM proxy in this course).
    openai_api_key: str = ""
    openai_base_url: str = "https://parsity-litellm.fly.dev"
    llm_model: str = "gpt-6-luna"

    # SEC requires a descriptive User-Agent with contact information.
    sec_user_agent: str = "EZ-10k Capstone (contact@example.com)"
    data_dir: Path = ROOT_DIR / "data"

    # FRED macro data. This app owns the key: it reads FRED_API_KEY here and
    # passes it to the third-party `fred-mcp-server` child process's environment.
    fred_api_key: str = ""
    fred_mcp_enabled: bool = True
    fred_mcp_package: str = "fred-mcp-server"
    # "http" talks to a long-lived sidecar (scripts/dev-mcp.sh) so its cache and
    # rate limiter survive between turns; "stdio" spawns per call (slow, cold).
    fred_mcp_transport: str = "http"
    fred_mcp_url: str = "http://127.0.0.1:3101/mcp"


settings = Settings()
