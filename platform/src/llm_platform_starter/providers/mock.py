from __future__ import annotations

import json
import re

from llm_platform_starter.models import ProviderRequest, ProviderResponse
from llm_platform_starter.providers.base import LLMProvider


class MockProvider(LLMProvider):
    name = "mock"

    def complete(self, request: ProviderRequest) -> ProviderResponse:
        prompt = request.prompt.lower()
        category = self._category(prompt)
        severity = "high" if any(term in prompt for term in ["urgent", "outage", "fraud"]) else "medium"
        confidence = 0.92 if category != "general" else 0.72
        needs_review = bool(re.search(r"\b(ssn|credit card|password|fraud)\b", prompt))
        payload = {
            "category": category,
            "severity": severity,
            "confidence": confidence,
            "rationale": f"Matched synthetic {category} support-ticket signals.",
            "needs_review": needs_review,
        }
        return ProviderResponse(
            text=json.dumps(payload),
            provider=self.name,
            model=request.model,
            input_tokens=len(request.prompt.split()),
            output_tokens=len(json.dumps(payload).split()),
            metadata={"deterministic": True},
        )

    @staticmethod
    def _category(prompt: str) -> str:
        if any(term in prompt for term in ["invoice", "refund", "billing", "charged", "payment"]):
            return "billing"
        if any(term in prompt for term in ["error", "api", "login loop", "bug", "outage"]):
            return "technical"
        if any(term in prompt for term in ["password", "account", "profile", "access"]):
            return "account"
        return "general"
