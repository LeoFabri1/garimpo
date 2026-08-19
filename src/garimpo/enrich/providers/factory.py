"""Build LLM provider from settings (optional)."""

from __future__ import annotations

from garimpo.enrich.providers.base import LLMProvider
from garimpo.settings import Settings


def build_llm_provider(settings: Settings) -> LLMProvider | None:
    if not settings.llm.enabled:
        return None
    key = settings.env(settings.llm.api_key_env)
    if not key:
        return None
    if settings.llm.provider in {"openai_compatible", "groq", "openrouter"}:
        from garimpo.enrich.providers.openai_compatible import OpenAICompatibleProvider

        return OpenAICompatibleProvider(
            base_url=settings.llm.base_url,
            api_key=key,
            model=settings.llm.model,
            timeout_s=settings.llm.timeout_s,
        )
    return None
