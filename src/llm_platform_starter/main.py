from __future__ import annotations

from llm_platform_starter.examples.ticket_classifier import TicketClassifier
from llm_platform_starter.models import TicketRequest
from llm_platform_starter.providers.factory import create_provider
from llm_platform_starter.settings import load_settings


def main() -> None:
    settings = load_settings()
    classifier = TicketClassifier(provider=create_provider(settings), model=settings.model)
    result = classifier.classify(
        TicketRequest(
            subject="Duplicate invoice charge",
            body="Customer reports being charged twice for the same monthly subscription.",
        )
    )
    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
