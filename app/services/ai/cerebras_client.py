from dataclasses import dataclass

import httpx

from app.core.config import settings


@dataclass
class CerebrasResult:
    content: str
    model: str


class CerebrasClient:
    def __init__(self) -> None:
        self._base_url = settings.cerebras_base_url.rstrip("/")
        self._api_key = settings.cerebras_api_key
        self._model = settings.cerebras_model

    @property
    def enabled(self) -> bool:
        return bool(self._api_key)

    def chat(self, system_prompt: str, user_prompt: str, temperature: float = 0.0) -> CerebrasResult:
        if not self._api_key:
            raise RuntimeError("Cerebras API key not configured")

        response = httpx.post(
            f"{self._base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self._api_key}"},
            json={
                "model": self._model,
                "temperature": temperature,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "response_format": {"type": "json_object"},
            },
            timeout=25,
        )
        response.raise_for_status()
        payload = response.json()
        return CerebrasResult(content=payload["choices"][0]["message"]["content"], model=payload.get("model", self._model))
