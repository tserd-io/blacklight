from __future__ import annotations


def review_state_for_guardrail_outcome(guardrail_outcome: str) -> str:
    if guardrail_outcome == "needs_review":
        return "needs_review"
    if guardrail_outcome == "rejected":
        return "rejected"
    return "accepted"


def review_reason_for_guardrail_outcome(
    guardrail_outcome: str,
    error_category: str | None = None,
) -> str:
    if guardrail_outcome == "needs_review":
        return "Guardrails routed this output to human review before downstream touch."
    if guardrail_outcome == "rejected":
        if error_category:
            return f"Guardrails rejected this output because {error_category} was recorded."
        return "Guardrails rejected this output before downstream touch."
    return "Guardrails accepted this output for read-only range use."


def review_routing_decision(review_state: str) -> str:
    return "allow_read_only_output" if review_state == "accepted" else "block_downstream_touch"
