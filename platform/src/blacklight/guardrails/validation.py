from __future__ import annotations

import json

from pydantic import ValidationError

from blacklight.guardrails.pii import detect_pii
from blacklight.models import GuardrailOutcome, TicketClassification, ValidationResult


def parse_ticket_classification(text: str) -> TicketClassification:
    return TicketClassification.model_validate(json.loads(text))


def validate_ticket_output(text: str, source_text: str = "") -> tuple[TicketClassification | None, ValidationResult]:
    errors: list[str] = []
    parsed: TicketClassification | None = None
    try:
        parsed = parse_ticket_classification(text)
    except (json.JSONDecodeError, ValidationError) as exc:
        errors.append(str(exc))

    pii_findings = detect_pii(source_text)
    if pii_findings and parsed:
        parsed.needs_review = True
    if errors:
        outcome = GuardrailOutcome.rejected
    elif pii_findings or (parsed and parsed.needs_review):
        outcome = GuardrailOutcome.needs_review
    else:
        outcome = GuardrailOutcome.accepted

    return parsed, ValidationResult(
        passed=outcome == GuardrailOutcome.accepted,
        outcome=outcome,
        errors=errors,
        pii_findings=pii_findings,
    )
