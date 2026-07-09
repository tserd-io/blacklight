from __future__ import annotations

import json
import re
from typing import Any

from pydantic import ValidationError

from blacklight.guardrails.pii import detect_pii
from blacklight.models import GuardrailOutcome, Severity, TicketCategory, TicketClassification, ValidationResult


_CATEGORY_ALIASES = {
    "billing issue": TicketCategory.billing.value,
    "financial billing": TicketCategory.billing.value,
    "financial invoicing": TicketCategory.billing.value,
    "financial": TicketCategory.billing.value,
    "invoicing": TicketCategory.billing.value,
    "payment": TicketCategory.billing.value,
    "refund": TicketCategory.billing.value,
    "technical issue": TicketCategory.technical.value,
    "tech": TicketCategory.technical.value,
    "account access": TicketCategory.account.value,
    "access": TicketCategory.account.value,
}

_SEVERITY_ALIASES = {
    "low moderate": Severity.medium.value,
    "moderate": Severity.medium.value,
}

_CONFIDENCE_ALIASES = {
    "low": 0.35,
    "medium": 0.65,
    "moderate": 0.65,
    "high": 0.9,
}


def parse_ticket_classification(text: str) -> TicketClassification:
    return TicketClassification.model_validate(_normalize_ticket_payload(json.loads(text)))


def _normalize_ticket_payload(payload: Any) -> Any:
    if not isinstance(payload, dict):
        return payload
    normalized = dict(payload)
    if "category" in normalized:
        normalized["category"] = _normalize_category(normalized["category"])
    if "severity" in normalized:
        normalized["severity"] = _normalize_severity(normalized["severity"])
    if "confidence" in normalized:
        normalized["confidence"] = _normalize_confidence(normalized["confidence"])
    return normalized


def _normalize_category(value: Any) -> Any:
    normalized = _normalize_enum_value(value, TicketCategory)
    if normalized != value:
        return normalized
    if not isinstance(value, str):
        return value
    return _CATEGORY_ALIASES.get(_normalized_label(value), value)


def _normalize_enum_value(value: Any, enum_type: type[TicketCategory] | type[Severity]) -> Any:
    if not isinstance(value, str):
        return value
    label = _normalized_label(value)
    for enum_value in enum_type:
        if label == _normalized_label(enum_value.value):
            return enum_value.value
    return value


def _normalize_severity(value: Any) -> Any:
    normalized = _normalize_enum_value(value, Severity)
    if normalized != value:
        return normalized
    if not isinstance(value, str):
        return value
    return _SEVERITY_ALIASES.get(_normalized_label(value), value)


def _normalize_confidence(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    label = _normalized_label(value)
    return _CONFIDENCE_ALIASES.get(label, value)


def _normalized_label(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", value.lower())).strip()


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
