from __future__ import annotations

from blacklight.models import ProviderRequest, ProviderResponse
from blacklight.providers.base import LLMProvider


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self, api_key: str | None = None) -> None:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("Install the openai extra to use OpenAIProvider.") from exc
        self.client = OpenAI(api_key=api_key)

    def complete(self, request: ProviderRequest) -> ProviderResponse:
        extra_headers = {}
        idempotency_key = request.metadata.get("idempotency_key")
        if idempotency_key:
            extra_headers["Idempotency-Key"] = str(idempotency_key)
        response = self.client.responses.create(
            model=request.model,
            input=request.prompt,
            extra_headers=extra_headers or None,
        )
        usage = getattr(response, "usage", None)
        return ProviderResponse(
            text=response.output_text,
            provider=self.name,
            model=request.model,
            input_tokens=getattr(usage, "input_tokens", 0) if usage else 0,
            output_tokens=getattr(usage, "output_tokens", 0) if usage else 0,
            metadata={"response_id": response.id},
        )
