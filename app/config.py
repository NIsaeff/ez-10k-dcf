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


settings = Settings()
