"""One-shot provider smoke test.

Usage:
    uv run python -m scripts.check_llm

Tries the configured model, then a few fallbacks, and reports which one answered.
Never prints the API key.
"""

from app.config import settings
from app.llm import complete

FALLBACK_MODELS = ("gpt-6-luna", "gpt-6-sol", "gpt-4o-mini", "gpt-4o")


def main() -> int:
    print(f"base_url={settings.openai_base_url}")
    print(f"configured_model={settings.llm_model}")

    tried: list[str] = []
    for model in dict.fromkeys((settings.llm_model, *FALLBACK_MODELS)):
        tried.append(model)
        try:
            reply = complete(
                [{"role": "user", "content": "Reply with exactly: OK"}],
                model=model,
            )
        except Exception as exc:  # noqa: BLE001 - report any provider failure
            print(f"{model}: FAILED ({type(exc).__name__}: {exc})")
            continue

        print(f"{model}: OK -> {reply!r}")
        if model != settings.llm_model:
            print(f"Set LLM_MODEL={model} in .env")
        return 0

    print(f"All models failed: {', '.join(tried)}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
