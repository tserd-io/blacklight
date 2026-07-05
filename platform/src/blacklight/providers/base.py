from __future__ import annotations

from abc import ABC, abstractmethod

from blacklight.models import ProviderRequest, ProviderResponse


class LLMProvider(ABC):
    name: str

    @abstractmethod
    def complete(self, request: ProviderRequest) -> ProviderResponse:
        """Return a normalized model response."""
