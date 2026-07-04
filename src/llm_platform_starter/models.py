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


class ProviderRequest(BaseModel):
    prompt: str
    model: str
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


class TicketRequest(BaseModel):
    subject: str
    body: str
    session_id: str | None = None
    idempotency_key: str | None = None


class ValidationResult(BaseModel):
    passed: bool
    errors: list[str] = Field(default_factory=list)
    pii_findings: list[str] = Field(default_factory=list)


class TraceRecord(BaseModel):
    request_id: str
    prompt_id: str
    prompt_version: int
    provider: str
    model: str
    latency_ms: float
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float
    validation_passed: bool
    error_category: str | None = None
