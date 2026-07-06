from __future__ import annotations

import json
import os
from urllib import request as urlrequest

from blacklight.models import ProviderRequest, ProviderResponse
from blacklight.providers.base import LLMProvider
from blacklight.settings import load_settings


class OllamaProvider(LLMProvider):
    name = "ollama"

    def __init__(self, base_url: str | None = None) -> None:
        settings = load_settings()
        self.base_url = (
            base_url
            or os.getenv("OLLAMA_BASE_URL")
            or settings.ollama_base_url
            or "http://localhost:11434"
        ).rstrip("/")

    def complete(self, request: ProviderRequest) -> ProviderResponse:
        payload = json.dumps(
            {
                "model": request.model,
                "prompt": request.prompt,
                "stream": False,
            }
        ).encode("utf-8")
        http_request = urlrequest.Request(
            f"{self.base_url}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlrequest.urlopen(http_request, timeout=60) as response:
            data = json.loads(response.read().decode("utf-8"))

        text = data.get("response", "")
        return ProviderResponse(
            text=text,
            provider=self.name,
            model=data.get("model", request.model),
            input_tokens=int(data.get("prompt_eval_count") or _rough_token_count(request.prompt)),
            output_tokens=int(data.get("eval_count") or _rough_token_count(text)),
            metadata={
                "base_url": self.base_url,
                "done": data.get("done"),
                "total_duration": data.get("total_duration"),
                "load_duration": data.get("load_duration"),
            },
        )


def _rough_token_count(text: str) -> int:
    return len(text.split())
