from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class TicketCategory(str, Enum):
    billing = "billing"
    technical = "technical"
    account = "account"
    general = "general"


class Severity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class GuardrailOutcome(str, Enum):
    accepted = "accepted"
    needs_review = "needs_review"
    rejected = "rejected"


class ProviderRequest(BaseModel):
    prompt: str
    model: str
    output_format: str | None = None
    output_schema_name: str | None = None
    output_schema: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProviderResponse(BaseModel):
    text: str
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class TicketClassification(BaseModel):
    category: TicketCategory
    severity: Severity
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str
    needs_review: bool = False


def ticket_classification_output_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["category", "severity", "confidence", "rationale", "needs_review"],
        "properties": {
            "category": {
                "type": "string",
                "enum": [category.value for category in TicketCategory],
            },
            "severity": {
                "type": "string",
                "enum": [severity.value for severity in Severity],
            },
            "confidence": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
            },
            "rationale": {
                "type": "string",
            },
            "needs_review": {
                "type": "boolean",
            },
        },
    }


class TicketRequest(BaseModel):
    subject: str
    body: str
    session_id: str | None = None
    idempotency_key: str | None = None
    agent_run_id: str | None = None


class ValidationResult(BaseModel):
    passed: bool
    outcome: GuardrailOutcome
    errors: list[str] = Field(default_factory=list)
    pii_findings: list[str] = Field(default_factory=list)


class TraceRecord(BaseModel):
    request_id: str
    session_id: str = "anonymous"
    eval_run_id: str | None = None
    agent_run_id: str | None = None
    prompt_id: str
    prompt_version: int
    provider: str
    model: str
    latency_ms: float
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float
    validation_passed: bool
    guardrail_outcome: GuardrailOutcome = GuardrailOutcome.accepted
    error_category: str | None = None
