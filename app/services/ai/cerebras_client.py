from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import settings


@dataclass
class CerebrasResult:
    content: str
    model: str


class CerebrasClient:
    def __init__(self, model: str | None = None) -> None:
        self._base_url = settings.cerebras_base_url.rstrip("/")
        self._api_key = settings.cerebras_api_key
        self._model = model or settings.cerebras_model

    @property
    def enabled(self) -> bool:
        return bool(self._api_key)

    def complete(
        self,
        messages: list[dict[str, Any]],
        *,
        temperature: float = 0.0,
        model: str | None = None,
        json_response: bool = False,
    ) -> CerebrasResult:
        if not self._api_key:
            raise RuntimeError("Cerebras API key not configured")

        payload: dict[str, Any] = {
            "model": model or self._model,
            "temperature": temperature,
            "messages": messages,
        }
        if json_response:
            payload["response_format"] = {"type": "json_object"}

        response = httpx.post(
            f"{self._base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self._api_key}"},
            json=payload,
            timeout=45,
        )
        response.raise_for_status()
        payload = response.json()
        return CerebrasResult(content=payload["choices"][0]["message"]["content"], model=payload.get("model", model or self._model))

    def chat(self, system_prompt: str, user_prompt: str, temperature: float = 0.0) -> CerebrasResult:
        return self.complete(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            json_response=True,
        )
