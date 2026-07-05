import json

from llm_platform_starter.guardrails.validation import validate_ticket_output
from llm_platform_starter.models import GuardrailOutcome


def test_validate_ticket_output_accepts_schema():
    text = json.dumps(
        {
            "category": "billing",
            "severity": "medium",
            "confidence": 0.9,
            "rationale": "Billing terms were present.",
            "needs_review": False,
        }
    )

    parsed, validation = validate_ticket_output(text)

    assert parsed is not None
    assert validation.passed
    assert validation.outcome == GuardrailOutcome.accepted


def test_validate_ticket_output_flags_pii():
    text = json.dumps(
        {
            "category": "account",
            "severity": "medium",
            "confidence": 0.8,
            "rationale": "Account access issue.",
            "needs_review": False,
        }
    )

    parsed, validation = validate_ticket_output(text, source_text="User email is test@example.com")

    assert parsed is not None
    assert not validation.passed
    assert validation.outcome == GuardrailOutcome.needs_review
    assert parsed.needs_review
    assert validation.pii_findings == ["email"]


def test_validate_ticket_output_routes_model_review_flag_to_needs_review():
    text = json.dumps(
        {
            "category": "account",
            "severity": "high",
            "confidence": 0.65,
            "rationale": "Risky account access issue.",
            "needs_review": True,
        }
    )

    parsed, validation = validate_ticket_output(text)

    assert parsed is not None
    assert not validation.passed
    assert validation.outcome == GuardrailOutcome.needs_review
    assert parsed.needs_review


def test_validate_ticket_output_rejects_invalid_json():
    parsed, validation = validate_ticket_output("not json")

    assert parsed is None
    assert not validation.passed
    assert validation.outcome == GuardrailOutcome.rejected
    assert validation.errors


def test_validate_ticket_output_rejects_schema_errors():
    parsed, validation = validate_ticket_output(json.dumps({"category": "billing"}))

    assert parsed is None
    assert not validation.passed
    assert validation.outcome == GuardrailOutcome.rejected
    assert validation.errors
