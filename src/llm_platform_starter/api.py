from __future__ import annotations

from fastapi import FastAPI

from llm_platform_starter.examples.ticket_classifier import TicketClassifier
from llm_platform_starter.models import TicketClassification, TicketRequest
from llm_platform_starter.observability.storage import TraceStore
from llm_platform_starter.providers.factory import create_provider
from llm_platform_starter.settings import load_settings

settings = load_settings()
trace_store = TraceStore(settings.trace_db_path)
classifier = TicketClassifier(
    provider=create_provider(settings),
    model=settings.model,
    trace_store=trace_store,
)

app = FastAPI(title="LLM Platform Starter", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/classify-ticket")
def classify_ticket(ticket: TicketRequest) -> TicketClassification:
    return classifier.classify(ticket)


@app.get("/metrics")
def metrics() -> dict[str, float | int]:
    return trace_store.metrics()
