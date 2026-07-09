from __future__ import annotations

import hashlib
import json
from typing import Any

from blacklight.agents.registry import AgentDefinition
from blacklight.eval_evidence import build_eval_evidence
from blacklight.review import (
    review_reason_for_guardrail_outcome,
    review_routing_decision,
    review_state_for_guardrail_outcome,
)
from blacklight.session_history import trace_detail


def quote_command_arg(value: str) -> str:
    return json.dumps(value)


def command_string(parts: list[str]) -> str:
    return " ".join(quote_command_arg(part) if " " in part else part for part in parts)


def build_agent_run_payload(
    *,
    agent: AgentDefinition,
    run_id: str,
    requested_session_id: str | None,
    session_id: str,
    db_path: str,
    result: Any | None,
    trace: dict[str, Any],
    verbose: bool,
    validation_errors: list[str] | None = None,
) -> dict[str, Any]:
    review_state = review_state_for_guardrail_outcome(trace["guardrail_outcome"])
    review_reason = review_reason_for_guardrail_outcome(
        trace["guardrail_outcome"],
        trace["error_category"],
    )
    payload: dict[str, Any] = {
        "agent_run": {
            "run_id": run_id,
            "agent_run_id": run_id,
            "agent_id": agent.agent_id,
            "agent_version": agent.version,
            "workflow_id": agent.workflow_id,
            "run_status": "failed" if result is None else "completed",
            "session_id": session_id,
            "requested_session_id": requested_session_id,
        },
        "trace": {
            "trace_id": trace["request_id"],
            "request_id": trace["request_id"],
            "session_id": trace["session_id"],
            "agent_run_id": trace["agent_run_id"],
            "session_linkage": (
                "Trace session_id is the generated agent run ID and trace.agent_run_id stores the same value."
                if requested_session_id is None
                else "Trace session_id preserves the requested session, while trace.agent_run_id stores the durable run link."
            ),
            "trace_db_path": db_path,
            "inspect_command": command_string(
                [
                    "blacklight",
                    "trace",
                    "show",
                    trace["request_id"],
                    "--trace-db-path",
                    db_path,
                ]
            ),
            "session_command": command_string(
                [
                    "blacklight",
                    "session",
                    "show",
                    trace["session_id"],
                    "--trace-db-path",
                    db_path,
                ]
            ),
        },
        "validation": {
            "passed": trace["validation_passed"],
            "guardrail_outcome": trace["guardrail_outcome"],
            "review_state": review_state,
            "review_required": trace["guardrail_outcome"] in {"needs_review", "rejected"},
            "review_reason": review_reason,
            "routing_decision": review_routing_decision(review_state),
            "error_category": trace["error_category"],
            "errors": validation_errors or [],
        },
        "guardrail": {
            "outcome": trace["guardrail_outcome"],
            "reason": review_reason,
            "error_category": trace["error_category"],
        },
        "review": {
            "state": review_state,
            "required": trace["guardrail_outcome"] in {"needs_review", "rejected"},
            "reason": review_reason,
            "routing_decision": review_routing_decision(review_state),
            "queue_hint": (
                "Show this run in review queues before downstream automation."
                if review_state in {"needs_review", "rejected"}
                else "No review queue item required."
            ),
        },
        "output_summary": None,
        "output": None,
    }
    if result is not None:
        payload["output_summary"] = {
            "category": result.category.value,
            "severity": result.severity.value,
            "confidence": result.confidence,
            "needs_review": result.needs_review,
            "rationale": result.rationale,
        }
        payload["output"] = result.model_dump(mode="json")
    if verbose:
        payload["domain_to_range_traceability"] = {
            "required_steps": agent.trace_contract.required_steps,
            "evidence_fields": {
                "agent_id": agent.agent_id,
                "agent_version": agent.version,
                "workflow_id": agent.workflow_id,
                "session_id": session_id,
                "agent_run_id": trace["agent_run_id"],
                "request_id": trace["request_id"],
                "prompt_id": trace["prompt_id"],
                "prompt_version": trace["prompt_version"],
                "provider": trace["provider"],
                "model": trace["model"],
                "validation_passed": trace["validation_passed"],
                "guardrail_outcome": trace["guardrail_outcome"],
                "error_category": trace["error_category"],
                "eval_evidence": build_eval_evidence(
                    trace,
                    agent_id=agent.agent_id,
                    workflow_id=agent.workflow_id,
                    trace_db_path=db_path,
                ),
            },
        }
        payload["trace"]["record"] = trace_detail(trace)
    return payload


def build_agent_run_envelope(
    *,
    agent: AgentDefinition,
    run_id: str,
    session_id: str,
    subject: str,
    body: str,
    trace: dict[str, Any],
    payload: dict[str, Any],
) -> dict[str, Any]:
    output = payload["output"]
    validation = payload["validation"]
    review_state = validation["review_state"]
    review_reason = validation["review_reason"]
    routing_decision = validation["routing_decision"]
    return {
        "agent_run_id": run_id,
        "agent_id": agent.agent_id,
        "agent_version": agent.version,
        "workflow_id": agent.workflow_id,
        "run_status": payload["agent_run"]["run_status"],
        "session_id": session_id,
        "trace_request_id": trace["request_id"],
        "trace_id": trace["request_id"],
        "domain_snapshot": {
            "retrieval_surface": agent.domain.retrieval_surface,
            "context_inputs": agent.domain.context_inputs,
            "context_boundaries": agent.domain.context_boundaries,
            "tools": agent.domain.tools,
            "provider_policy": agent.domain.provider_policy,
            "prompt_ids": agent.domain.prompt_ids,
            "prompt_versions": agent.domain.prompt_versions,
            "limits": agent.domain.limits,
            "raw_private_inputs_persisted": False,
        },
        "context_bundle": {
            "input_fields": ["subject", "body", "session_id"],
            "inputs": {
                "subject": {
                    "length": len(subject),
                    "sha256": _sha256_text(subject),
                },
                "body": {
                    "length": len(body),
                    "sha256": _sha256_text(body),
                },
                "session_id": session_id,
            },
            "raw_inputs_persisted": False,
            "prompt_text_persisted": False,
            "privacy_note": "Raw subject, body, rendered prompts, API keys, and provider secrets are not stored in the agent run envelope.",
        },
        "provider_call": {
            "trace_request_id": trace["request_id"],
            "prompt_id": trace["prompt_id"],
            "prompt_version": trace["prompt_version"],
            "provider": trace["provider"],
            "model": trace["model"],
            "latency_ms": trace["latency_ms"],
            "input_tokens": trace["input_tokens"],
            "output_tokens": trace["output_tokens"],
            "estimated_cost_usd": trace["estimated_cost_usd"],
            "prompt_text_persisted": False,
        },
        "validation": {
            "passed": validation["passed"],
            "errors": validation["errors"],
        },
        "guardrail": {
            "outcome": validation["guardrail_outcome"],
            "reason": review_reason,
            "error_category": validation["error_category"],
        },
        "range_output": {
            "schema": agent.governed_range.output_schema,
            "output": output,
            "output_summary": payload["output_summary"],
            "allowed_side_effects": agent.governed_range.allowed_side_effects,
        },
        "review": {
            "state": review_state,
            "required": validation["review_required"],
            "reason": review_reason,
            "routing_decision": routing_decision,
            "touch_decision": routing_decision,
            "export_decision": "not_exported",
            "queue_hint": payload["review"]["queue_hint"],
        },
        "eval_evidence": {
            **build_eval_evidence(
                trace,
                agent_id=agent.agent_id,
                workflow_id=agent.workflow_id,
                trace_db_path=payload["trace"]["trace_db_path"],
            ),
        },
    }


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
