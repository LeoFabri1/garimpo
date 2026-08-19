"""OpenAI-compatible chat completions (Groq, OpenRouter, etc.) via httpx."""

from __future__ import annotations

import json
from pathlib import Path

import httpx

from garimpo.enrich.providers.base import ExtractedOffer

_PROMPT = Path(__file__).resolve().parents[1] / "prompts" / "extract_v1.txt"


class OpenAICompatibleProvider:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout_s: float = 20.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._timeout = timeout_s
        self._prompt = _PROMPT.read_text(encoding="utf-8")

    async def extract(self, text: str) -> ExtractedOffer | None:
        payload = {
            "model": self._model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": self._prompt},
                {"role": "user", "content": text},
            ],
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                f"{self._base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
        content = data["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        offer = ExtractedOffer.model_validate(parsed)
        if not offer.is_gpu or offer.price is None or not offer.model_raw:
            return None
        return offer
