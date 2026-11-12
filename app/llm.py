from functools import lru_cache

from openai import OpenAI

from app.config import settings


@lru_cache(maxsize=1)
def get_client() -> OpenAI:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not set. Add it to .env.")
    return OpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        timeout=30.0,
    )


def complete(
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
    temperature: float | None = None,
) -> str:
    """Run one chat completion and return the assistant text.

    Temperature is omitted unless explicitly requested: some reasoning models
    on the LiteLLM proxy reject temperature=0 while reasoning is active.
    """
    kwargs: dict[str, object] = {
        "model": model or settings.llm_model,
        "messages": messages,
    }
    if temperature is not None:
        kwargs["temperature"] = temperature

    response = get_client().chat.completions.create(**kwargs)
    content = response.choices[0].message.content
    if not content:
        raise RuntimeError("LLM returned an empty response")
    return content
