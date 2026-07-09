from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import uuid
from typing import Any

from blacklight.agents import AgentDefinition, AgentRegistry
from blacklight.demo_seed import seed_demo_data
from blacklight.errors import (
    GuardrailValidationError,
    agent_not_found_error,
    describe_exception,
    is_known_error,
    session_not_found_error,
    trace_not_found_error,
)
from blacklight.evals.runner import (
    compare_ticket_classification_prompt_versions,
    run_ticket_classification_eval,
)
from blacklight.examples.ticket_classifier import TicketClassifier
from blacklight.local_models import local_model_status
from blacklight.models import TicketRequest
from blacklight.observability.agent_runs import AgentRunStore
from blacklight.observability.evaluations import EvalMetricStore
from blacklight.observability.idempotency import IdempotencyStore
from blacklight.observability.storage import TraceStore
from blacklight.prompts.registry import PromptRegistry
from blacklight.providers.factory import create_provider
from blacklight.providers.mock import MockProvider
from blacklight.session_history import (
    summarize_session,
    trace_detail,
    trace_domain_to_range_detail,
)
from blacklight.settings import load_settings

DEMO_SUBJECT = "Refund request"
DEMO_BODY = "Customer asks for a refund after duplicate billing."
DEMO_SESSION_ID = "demo"
DEMO_MODEL = "mock-ticket-classifier"


def _print_json(payload: dict[str, Any], *, file: Any | None = None) -> None:
    print(json.dumps(payload, indent=2), file=file or sys.stdout)


def _print_error(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2), file=sys.stderr)


def _print_text_error(message: str) -> None:
    print(message, file=sys.stderr)


def _print_text(text: str) -> None:
    print(text)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _quote_command_arg(value: str) -> str:
    return json.dumps(value)


def _command_string(parts: list[str]) -> str:
    return " ".join(_quote_command_arg(part) if " " in part else part for part in parts)


def demo(args: argparse.Namespace) -> int:
    settings = load_settings()
    db_path = args.trace_db_path or settings.trace_db_path
    session_id = args.session_id
    trace_store = TraceStore(db_path)
    idempotency_store = IdempotencyStore(db_path)
    classifier = TicketClassifier(
        provider=MockProvider(),
        model=DEMO_MODEL,
        trace_store=trace_store,
        idempotency_store=idempotency_store,
        provider_timeout_seconds=settings.provider_timeout_seconds,
        provider_max_retries=settings.provider_max_retries,
        provider_rate_limit_requests=settings.provider_rate_limit_requests,
        provider_rate_limit_window_seconds=settings.provider_rate_limit_window_seconds,
    )
    result = classifier.classify(
        TicketRequest(
            subject=DEMO_SUBJECT,
            body=DEMO_BODY,
            session_id=session_id,
            idempotency_key=f"demo-{uuid.uuid4()}",
        )
    )
    traces = trace_store.list_by_session_id(session_id, limit=500)
    trace = traces[-1]
    detail = trace_detail(trace)
    trace_command = _command_string(
        [
            "blacklight",
            "trace",
            "show",
            trace["request_id"],
            "--trace-db-path",
            db_path,
        ]
    )
    session_command = _command_string(
        [
            "blacklight",
            "session",
            "show",
            session_id,
            "--trace-db-path",
            db_path,
        ]
    )
    eval_command = _command_string(
        [
            "blacklight",
            "eval",
            "run",
            "--trace-db-path",
            db_path,
            "--session-id",
            f"{session_id}-eval",
        ]
    )
    equivalent_workflow_command = _command_string(
        [
            "blacklight",
            "classify",
            "--subject",
            DEMO_SUBJECT,
            "--body",
            DEMO_BODY,
            "--trace-db-path",
            db_path,
            "--session-id",
            session_id,
        ]
    )

    payload: dict[str, Any] = {
        "demo": "ticket_classifier",
        "message": "Mock-mode demo completed without live provider credentials.",
        "sample_input": {
            "subject": DEMO_SUBJECT,
            "body": DEMO_BODY,
            "session_id": session_id,
        },
        "result": result.model_dump(mode="json"),
        "trace": {
            "request_id": trace["request_id"],
            "session_id": session_id,
            "trace_db_path": db_path,
            "inspect_command": trace_command,
            "session_command": session_command,
        },
        "next_commands": {
            "equivalent_workflow_command": equivalent_workflow_command,
            "eval_command": eval_command,
        },
    }
    if args.verbose:
        payload["runtime"] = {
            "provider": "mock",
            "model": DEMO_MODEL,
            "live_credentials_required": False,
        }
        payload["trace"]["record"] = detail
    _print_json(payload)
    return 0


def classify(args: argparse.Namespace) -> int:
    settings = load_settings()
    trace_store = TraceStore(args.trace_db_path or settings.trace_db_path)
    idempotency_store = IdempotencyStore(args.trace_db_path or settings.trace_db_path)
    classifier = TicketClassifier(
        provider=create_provider(settings),
        model=settings.model,
        trace_store=trace_store,
        idempotency_store=idempotency_store,
        provider_timeout_seconds=settings.provider_timeout_seconds,
        provider_max_retries=settings.provider_max_retries,
        provider_rate_limit_requests=settings.provider_rate_limit_requests,
        provider_rate_limit_window_seconds=settings.provider_rate_limit_window_seconds,
    )
    result = classifier.classify(
        TicketRequest(
            subject=args.subject,
            body=args.body,
            session_id=args.session_id,
            idempotency_key=args.idempotency_key,
        )
    )
    _print_json(result.model_dump(mode="json"))
    return 0


def eval_run(args: argparse.Namespace) -> int:
    settings = load_settings()
    db_path = args.trace_db_path or settings.trace_db_path
    eval_store = EvalMetricStore(db_path)
    trace_store = TraceStore(db_path)
    _print_json(
        run_ticket_classification_eval(
            session_id=args.session_id,
            prompt_version=args.prompt_version,
            eval_store=eval_store,
            trace_store=trace_store,
        )
    )
    return 0


def eval_compare(args: argparse.Namespace) -> int:
    _print_json(
        compare_ticket_classification_prompt_versions(
            baseline_version=args.baseline_version,
            candidate_version=args.candidate_version,
            session_id=args.session_id,
        )
    )
    return 0


def eval_list(args: argparse.Namespace) -> int:
    settings = load_settings()
    eval_store = EvalMetricStore(args.trace_db_path or settings.trace_db_path)
    _print_json({"eval_runs": eval_store.list_runs(limit=args.limit)})
    return 0


def eval_show(args: argparse.Namespace) -> int:
    settings = load_settings()
    db_path = args.trace_db_path or settings.trace_db_path
    eval_store = EvalMetricStore(db_path)
    trace_store = TraceStore(db_path)
    run = eval_store.get_run(args.eval_run_id)
    _print_json(
        {
            "eval_run": run,
            "traces": trace_store.list_by_eval_run_id(args.eval_run_id),
        }
    )
    return 0


def metrics(args: argparse.Namespace) -> int:
    settings = load_settings()
    trace_store = TraceStore(args.trace_db_path or settings.trace_db_path)
    _print_json(trace_store.metrics())
    return 0


def health(_args: argparse.Namespace) -> int:
    settings = load_settings()
    _print_json(_health_payload(settings))
    return 0


def _health_payload(settings: Any) -> dict[str, Any]:
    return {
        "provider": settings.provider,
        "model": settings.model,
        "trace_db_path": settings.trace_db_path,
        "openai_configured": bool(settings.openai_api_key),
        "custom_provider_configured": bool(settings.custom_provider_path),
        "ollama_base_url": settings.ollama_base_url,
        "provider_timeout_seconds": settings.provider_timeout_seconds,
        "provider_max_retries": settings.provider_max_retries,
        "provider_rate_limit_requests": settings.provider_rate_limit_requests,
        "provider_rate_limit_window_seconds": settings.provider_rate_limit_window_seconds,
    }


def providers_list(_args: argparse.Namespace) -> int:
    settings = load_settings()
    _print_json(
        {
            "active_provider": settings.provider,
            "providers": [
                {
                    "name": "mock",
                    "configured": True,
                    "selected": settings.provider == "mock",
                    "requires_secret": False,
                    "summary": "Ready by default for demos, tests, and CI.",
                },
                {
                    "name": "openai",
                    "configured": bool(settings.openai_api_key),
                    "selected": settings.provider == "openai",
                    "requires_secret": True,
                    "summary": "Uses OPENAI_API_KEY from private environment settings.",
                },
                {
                    "name": "custom",
                    "configured": bool(settings.custom_provider_path),
                    "selected": settings.provider == "custom",
                    "requires_secret": False,
                    "summary": "Uses LLM_CUSTOM_PROVIDER import path for user-owned providers.",
                },
            ],
        }
    )
    return 0


def providers_status(_args: argparse.Namespace) -> int:
    settings = load_settings()
    local_status = local_model_status(settings).as_dict()
    _print_json(
        {
            "runtime": _health_payload(settings),
            "providers": {
                "mock": {
                    "configured": True,
                    "ready": True,
                    "selected": settings.provider == "mock",
                    "message": "Mock provider is ready without live credentials.",
                },
                "openai": {
                    "configured": bool(settings.openai_api_key),
                    "ready": bool(settings.openai_api_key),
                    "selected": settings.provider == "openai",
                    "message": (
                        "OpenAI provider key is configured."
                        if settings.openai_api_key
                        else "OpenAI provider requires OPENAI_API_KEY in a private environment."
                    ),
                },
                "custom": {
                    "configured": bool(settings.custom_provider_path),
                    "ready": bool(settings.custom_provider_path),
                    "selected": settings.provider == "custom",
                    "message": (
                        "Custom provider import path is configured."
                        if settings.custom_provider_path
                        else "Custom provider requires LLM_CUSTOM_PROVIDER."
                    ),
                },
            },
            "local_model": {
                "runtime": local_status["runtime"],
                "configured": local_status["configured"],
                "selected": local_status["selected"],
                "status": local_status["status"],
                "ready": local_status["ready"],
                "message": local_status["status_message"],
            },
        }
    )
    return 0


def local_model_status_command(_args: argparse.Namespace) -> int:
    settings = load_settings()
    _print_json(local_model_status(settings).as_dict())
    return 0


def _agent_payload(agent: AgentDefinition) -> dict[str, Any]:
    payload = agent.model_dump(mode="json")
    payload["cli_commands"] = {
        "show": f"blacklight agents show {agent.agent_id}",
        "show_json": f"blacklight agents show {agent.agent_id} --json",
        "run": (
            f"blacklight agents run {agent.agent_id} "
            f"--subject {json.dumps(DEMO_SUBJECT)} --body {json.dumps(DEMO_BODY)}"
        ),
        "workflow": f"blacklight classify --subject {json.dumps(DEMO_SUBJECT)} --body {json.dumps(DEMO_BODY)}",
        "prompt": " ".join(
            [
                "blacklight",
                "prompts",
                "show",
                agent.domain.prompt_ids[0],
            ]
        ),
        "eval": "blacklight eval run --session-id agent-definition-eval",
    }
    return payload


def _format_bullets(items: list[str]) -> str:
    return "\n".join(f"  - {item}" for item in items)


def _format_prompt_versions(agent: AgentDefinition) -> str:
    return "\n".join(
        f"  - {prompt_id}: {', '.join(str(version) for version in versions)}"
        for prompt_id, versions in sorted(agent.domain.prompt_versions.items())
    )


def _format_agent_summary(agent: AgentDefinition) -> str:
    return "\n".join(
        [
            f"{agent.display_name} ({agent.agent_id})",
            f"Version: {agent.version}",
            f"Workflow: {agent.workflow_id}",
            f"Active: {str(agent.active).lower()}",
            f"Description: {agent.description}",
            "",
            "Domain",
            "Retrieval surface:",
            _format_bullets(agent.domain.retrieval_surface),
            "Context inputs:",
            _format_bullets(agent.domain.context_inputs),
            "Context boundaries:",
            _format_bullets(agent.domain.context_boundaries),
            "Tools:",
            _format_bullets(agent.domain.tools or ["none"]),
            f"Provider policy: {agent.domain.provider_policy}",
            "Prompt versions:",
            _format_prompt_versions(agent),
            "Limits:",
            _format_bullets(agent.domain.limits),
            "",
            "Governed Range",
            "Touch surface:",
            _format_bullets(agent.governed_range.touch_surface),
            f"Output schema: {agent.governed_range.output_schema}",
            "Output expectations:",
            _format_bullets(agent.governed_range.output_expectations),
            "Allowed side effects:",
            _format_bullets(agent.governed_range.allowed_side_effects or ["none"]),
            "Review requirements:",
            _format_bullets(agent.governed_range.review_requirements),
            "Guardrail enforcement:",
            _format_bullets(agent.governed_range.guardrail_enforcement),
            "",
            "Domain-To-Range Traceability",
            "Required steps:",
            _format_bullets(agent.trace_contract.required_steps),
            "Evidence fields:",
            _format_bullets(agent.trace_contract.evidence_fields),
            "Eval evidence:",
            _format_bullets(agent.trace_contract.eval_evidence),
            "",
            "Next steps",
            f"  - blacklight agents show {agent.agent_id} --json",
            f"  - blacklight prompts show {agent.domain.prompt_ids[0]}",
            "  - blacklight eval run --session-id agent-definition-eval",
        ]
    )


def _get_agent_or_print_error(agent_id: str) -> AgentDefinition | None:
    registry = AgentRegistry()
    agent = registry.get_optional(agent_id)
    if agent is None:
        _print_error(agent_not_found_error(agent_id).as_payload())
        return None
    return agent


def _assert_ticket_classifier_agent(agent: AgentDefinition) -> None:
    if agent.workflow_id != "ticket_classifier":
        raise ValueError(
            f"Agent {agent.agent_id} is not runnable by this CLI yet. "
            "Only workflow_id='ticket_classifier' is currently supported."
        )


def agents_list(args: argparse.Namespace) -> int:
    agents = AgentRegistry().list()
    payload = {
        "agents": [
            {
                "agent_id": agent.agent_id,
                "display_name": agent.display_name,
                "version": agent.version,
                "active": agent.active,
                "workflow_id": agent.workflow_id,
                "output_schema": agent.governed_range.output_schema,
                "prompt_ids": agent.domain.prompt_ids,
                "cli_command": f"blacklight agents show {agent.agent_id}",
            }
            for agent in agents
        ],
        "cli_commands": {
            "list": "blacklight agents list",
            "show_ticket_classifier": "blacklight agents show ticket_classifier_agent",
        },
    }
    if args.json_output:
        _print_json(payload)
        return 0
    lines = ["Managed Agents", ""]
    for agent in payload["agents"]:
        lines.extend(
            [
                f"- {agent['agent_id']} v{agent['version']} ({agent['display_name']})",
                f"  workflow: {agent['workflow_id']}",
                f"  output schema: {agent['output_schema']}",
                f"  inspect: {agent['cli_command']}",
            ]
        )
    lines.extend(["", "Next steps", "  - blacklight agents show ticket_classifier_agent"])
    _print_text("\n".join(lines))
    return 0


def agents_show(args: argparse.Namespace) -> int:
    agent = _get_agent_or_print_error(args.agent_id)
    if agent is None:
        return 1
    payload = _agent_payload(agent)
    if args.json_output:
        _print_json(payload)
        return 0
    _print_text(_format_agent_summary(agent))
    return 0


def _agent_run_payload(
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
    payload: dict[str, Any] = {
        "agent_run": {
            "run_id": run_id,
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
            "inspect_command": _command_string(
                [
                    "blacklight",
                    "trace",
                    "show",
                    trace["request_id"],
                    "--trace-db-path",
                    db_path,
                ]
            ),
            "session_command": _command_string(
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
            "review_state": (
                "needs_review"
                if trace["guardrail_outcome"] == "needs_review"
                else "rejected"
                if trace["guardrail_outcome"] == "rejected"
                else "accepted"
            ),
            "review_required": trace["guardrail_outcome"] in {"needs_review", "rejected"},
            "error_category": trace["error_category"],
            "errors": validation_errors or [],
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
            },
        }
        payload["trace"]["record"] = trace_detail(trace)
    return payload


def _agent_run_envelope(
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
            "touch_decision": "allow_read_only_output" if review_state == "accepted" else "block_downstream_touch",
            "export_decision": "not_exported",
        },
        "eval_evidence": {
            "eval_run_id": trace["eval_run_id"],
            "linked": trace["eval_run_id"] is not None,
        },
    }


def _format_agent_run_summary(payload: dict[str, Any]) -> str:
    run = payload["agent_run"]
    trace = payload["trace"]
    validation = payload["validation"]
    summary = payload["output_summary"]
    lines = [
        "Managed Agent Run",
        "",
        f"Agent: {run['agent_id']} v{run['agent_version']}",
        f"Workflow: {run['workflow_id']}",
        f"Status: {run['run_status']}",
        f"Run ID: {run['run_id']}",
        f"Trace ID: {trace['trace_id']}",
        f"Session ID: {run['session_id']}",
        "",
        "Validation",
        f"  passed: {str(validation['passed']).lower()}",
        f"  guardrail outcome: {validation['guardrail_outcome']}",
        f"  review state: {validation['review_state']}",
    ]
    if validation["errors"]:
        lines.append(f"  errors: {'; '.join(validation['errors'])}")
    if summary is not None:
        lines.extend(
            [
                "",
                "Output Summary",
                f"  category: {summary['category']}",
                f"  severity: {summary['severity']}",
                f"  confidence: {summary['confidence']}",
                f"  needs review: {str(summary['needs_review']).lower()}",
                f"  rationale: {summary['rationale']}",
            ]
        )
    lines.extend(
        [
            "",
            "Inspect",
            f"  - {trace['inspect_command']}",
            f"  - {trace['session_command']}",
        ]
    )
    if "domain_to_range_traceability" in payload:
        evidence = payload["domain_to_range_traceability"]["evidence_fields"]
        lines.extend(
            [
                "",
                "Domain-To-Range Evidence",
                f"  prompt: {evidence['prompt_id']} v{evidence['prompt_version']}",
                f"  provider/model: {evidence['provider']} / {evidence['model']}",
                f"  guardrail: {evidence['guardrail_outcome']}",
            ]
        )
    return "\n".join(lines)


def agents_run(args: argparse.Namespace) -> int:
    agent = _get_agent_or_print_error(args.agent_id)
    if agent is None:
        return 1
    _assert_ticket_classifier_agent(agent)

    settings = load_settings()
    db_path = args.trace_db_path or settings.trace_db_path
    run_id = f"agent-run-{uuid.uuid4()}"
    requested_session_id = args.session_id
    session_id = requested_session_id or run_id
    trace_store = TraceStore(db_path)
    agent_run_store = AgentRunStore(db_path)
    classifier = TicketClassifier(
        provider=create_provider(settings),
        model=settings.model,
        trace_store=trace_store,
        idempotency_store=IdempotencyStore(db_path),
        provider_timeout_seconds=settings.provider_timeout_seconds,
        provider_max_retries=settings.provider_max_retries,
        provider_rate_limit_requests=settings.provider_rate_limit_requests,
        provider_rate_limit_window_seconds=settings.provider_rate_limit_window_seconds,
    )
    ticket = TicketRequest(
        subject=args.subject,
        body=args.body,
        session_id=session_id,
        idempotency_key=run_id,
        agent_run_id=run_id,
    )
    try:
        result = classifier.classify(ticket)
    except GuardrailValidationError as exc:
        traces = trace_store.list_by_agent_run_id(run_id)
        if not traces:
            raise
        trace = traces[-1]
        payload = _agent_run_payload(
            agent=agent,
            run_id=run_id,
            requested_session_id=requested_session_id,
            session_id=session_id,
            db_path=db_path,
            result=None,
            trace=trace,
            verbose=args.verbose,
            validation_errors=[str(exc)],
        )
        envelope = _agent_run_envelope(
            agent=agent,
            run_id=run_id,
            session_id=session_id,
            subject=args.subject,
            body=args.body,
            trace=trace,
            payload=payload,
        )
        agent_run_store.insert(envelope)
        payload["trace_envelope"] = envelope
        if args.json_output:
            _print_json(payload, file=sys.stderr)
        else:
            _print_text_error(_format_agent_run_summary(payload))
        return 1
    traces = trace_store.list_by_agent_run_id(run_id)
    trace = traces[-1]
    payload = _agent_run_payload(
        agent=agent,
        run_id=run_id,
        requested_session_id=requested_session_id,
        session_id=session_id,
        db_path=db_path,
        result=result,
        trace=trace,
        verbose=args.verbose,
    )
    envelope = _agent_run_envelope(
        agent=agent,
        run_id=run_id,
        session_id=session_id,
        subject=args.subject,
        body=args.body,
        trace=trace,
        payload=payload,
    )
    agent_run_store.insert(envelope)
    payload["trace_envelope"] = envelope
    if args.json_output:
        _print_json(payload)
        return 0
    _print_text(_format_agent_run_summary(payload))
    return 0


def agents_runs_list(args: argparse.Namespace) -> int:
    settings = load_settings()
    run_store = AgentRunStore(args.trace_db_path or settings.trace_db_path)
    _print_json({"agent_runs": run_store.list_recent(limit=args.limit)})
    return 0


def agents_runs_show(args: argparse.Namespace) -> int:
    settings = load_settings()
    run_store = AgentRunStore(args.trace_db_path or settings.trace_db_path)
    envelope = run_store.get(args.agent_run_id)
    if envelope is None:
        _print_error(
            {
                "error": {
                    "category": "not_found",
                    "message": f"Agent run not found: {args.agent_run_id}",
                    "likely_cause": "The run was not persisted in this trace database.",
                    "next_step": "Run `blacklight agents runs list` with the same --trace-db-path and retry with a listed agent_run_id.",
                }
            }
        )
        return 1
    _print_json({"agent_run": envelope})
    return 0


def prompts_list(_args: argparse.Namespace) -> int:
    prompts = PromptRegistry().list()
    _print_json(
        {
            "prompts": [
                {
                    "prompt_id": prompt.prompt_id,
                    "display_name": prompt.display_name,
                    "version": prompt.version,
                    "active": prompt.active,
                    "domain": prompt.domain,
                    "task_type": prompt.task_type,
                    "output_schema": prompt.output_schema,
                    "eval_fixture": prompt.eval_fixture,
                    "comparison_group": prompt.comparison_group,
                    "tags": prompt.tags,
                    "input_variables": prompt.input_variables,
                    "notes": prompt.notes,
                }
                for prompt in prompts
            ]
        }
    )
    return 0


def prompts_show(args: argparse.Namespace) -> int:
    prompt = PromptRegistry().get(args.prompt_id, version=args.version)
    _print_json(
        {
            "prompt_id": prompt.prompt_id,
            "display_name": prompt.display_name,
            "version": prompt.version,
            "active": prompt.active,
            "domain": prompt.domain,
            "task_type": prompt.task_type,
            "output_schema": prompt.output_schema,
            "eval_fixture": prompt.eval_fixture,
            "comparison_group": prompt.comparison_group,
            "tags": prompt.tags,
            "input_variables": prompt.input_variables,
            "notes": prompt.notes,
            "template": prompt.template,
        }
    )
    return 0


def trace_list(args: argparse.Namespace) -> int:
    settings = load_settings()
    trace_store = TraceStore(args.trace_db_path or settings.trace_db_path)
    _print_json({"traces": trace_store.list_recent(limit=args.limit)})
    return 0


def trace_show(args: argparse.Namespace) -> int:
    settings = load_settings()
    trace_store = TraceStore(args.trace_db_path or settings.trace_db_path)
    agent_run_store = AgentRunStore(args.trace_db_path or settings.trace_db_path)
    trace = trace_store.get_by_request_id(args.request_id)
    if trace is None:
        _print_error(trace_not_found_error(args.request_id).as_payload())
        return 1
    envelope = agent_run_store.get(trace["agent_run_id"]) if trace["agent_run_id"] else None
    _print_json({"trace": trace_domain_to_range_detail(trace, envelope)})
    return 0


def session_show(args: argparse.Namespace) -> int:
    settings = load_settings()
    trace_store = TraceStore(args.trace_db_path or settings.trace_db_path)
    traces = trace_store.list_by_session_id(args.session_id, limit=args.limit)
    if not traces:
        _print_error(session_not_found_error(args.session_id).as_payload())
        return 1
    trace_details = [trace_detail(trace) for trace in traces]
    _print_json(
        {
            "session_id": args.session_id,
            "summary": summarize_session(trace_details),
            "traces": trace_details,
        }
    )
    return 0


def seed_demo(args: argparse.Namespace) -> int:
    settings = load_settings()
    _print_json(seed_demo_data(args.trace_db_path or settings.trace_db_path))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="blacklight",
        description="Run the Blacklight Studio demo workflows.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    demo_parser = subparsers.add_parser(
        "demo",
        help="Run a guided mock-mode ticket-classifier demo.",
    )
    demo_parser.add_argument(
        "--verbose",
        action="store_true",
        help="Include runtime details and the full trace record.",
    )
    demo_parser.add_argument(
        "--session-id",
        default=DEMO_SESSION_ID,
        help="Session id used for the demo trace.",
    )
    demo_parser.add_argument(
        "--trace-db-path",
        default=None,
        help="SQLite trace database path. Defaults to TRACE_DB_PATH or traces.sqlite3.",
    )
    demo_parser.set_defaults(func=demo)

    classify_parser = subparsers.add_parser("classify", help="Classify a support ticket.")
    classify_parser.add_argument("--subject", required=True, help="Support ticket subject.")
    classify_parser.add_argument("--body", required=True, help="Support ticket body.")
    classify_parser.add_argument(
        "--session-id",
        default="cli",
        help="Session or user id used for per-session provider rate limiting.",
    )
    classify_parser.add_argument(
        "--idempotency-key",
        default=None,
        help="Optional caller-provided idempotency key for durable duplicate suppression.",
    )
    classify_parser.add_argument(
        "--trace-db-path",
        default=None,
        help="SQLite trace database path. Defaults to TRACE_DB_PATH or traces.sqlite3.",
    )
    classify_parser.set_defaults(func=classify)

    eval_parser = subparsers.add_parser("eval", help="Run and inspect deterministic ticket evals.")
    eval_parser.add_argument(
        "--session-id",
        default="eval",
        help="Session id stored with eval metrics so reports can be related to traces.",
    )
    eval_parser.add_argument(
        "--trace-db-path",
        default=None,
        help="SQLite metrics database path. Defaults to TRACE_DB_PATH or traces.sqlite3.",
    )
    eval_parser.add_argument(
        "--prompt-version",
        type=int,
        default=None,
        help="Prompt version to evaluate. Defaults to the active version.",
    )
    eval_subparsers = eval_parser.add_subparsers(dest="eval_command")
    eval_run_parser = eval_subparsers.add_parser("run", help="Run deterministic ticket evals.")
    eval_run_parser.add_argument(
        "--session-id",
        default="eval",
        help="Session id stored with eval metrics so reports can be related to traces.",
    )
    eval_run_parser.add_argument(
        "--trace-db-path",
        default=None,
        help="SQLite metrics database path. Defaults to TRACE_DB_PATH or traces.sqlite3.",
    )
    eval_run_parser.add_argument(
        "--prompt-version",
        type=int,
        default=None,
        help="Prompt version to evaluate. Defaults to the active version.",
    )
    eval_run_parser.set_defaults(func=eval_run)
    eval_compare_parser = eval_subparsers.add_parser(
        "compare",
        help="Compare deterministic eval reports across prompt versions.",
    )
    eval_compare_parser.add_argument(
        "--baseline-version",
        type=int,
        required=True,
        help="Baseline prompt version.",
    )
    eval_compare_parser.add_argument(
        "--candidate-version",
        type=int,
        required=True,
        help="Candidate prompt version.",
    )
    eval_compare_parser.add_argument(
        "--session-id",
        default="eval-compare",
        help="Session id included in generated comparison eval run ids.",
    )
    eval_compare_parser.set_defaults(func=eval_compare)
    eval_list_parser = eval_subparsers.add_parser("list", help="List persisted eval runs.")
    eval_list_parser.add_argument("--limit", type=int, default=10, help="Maximum eval runs to return.")
    eval_list_parser.add_argument(
        "--trace-db-path",
        default=None,
        help="SQLite metrics database path. Defaults to TRACE_DB_PATH or traces.sqlite3.",
    )
    eval_list_parser.set_defaults(func=eval_list)
    eval_show_parser = eval_subparsers.add_parser("show", help="Show one eval run with traces.")
    eval_show_parser.add_argument("eval_run_id", help="Eval run id to inspect.")
    eval_show_parser.add_argument(
        "--trace-db-path",
        default=None,
        help="SQLite metrics database path. Defaults to TRACE_DB_PATH or traces.sqlite3.",
    )
    eval_show_parser.set_defaults(func=eval_show)
    eval_parser.set_defaults(func=eval_run)

    metrics_parser = subparsers.add_parser("metrics", help="Print trace database metrics.")
    metrics_parser.add_argument(
        "--trace-db-path",
        default=None,
        help="SQLite trace database path. Defaults to TRACE_DB_PATH or traces.sqlite3.",
    )
    metrics_parser.set_defaults(func=metrics)

    health_parser = subparsers.add_parser("health", help="Print local runtime configuration.")
    health_parser.set_defaults(func=health)

    providers_parser = subparsers.add_parser("providers", help="Inspect provider readiness.")
    providers_subparsers = providers_parser.add_subparsers(
        dest="providers_command",
        required=True,
    )
    providers_list_parser = providers_subparsers.add_parser(
        "list",
        help="List supported providers and configuration state.",
    )
    providers_list_parser.set_defaults(func=providers_list)
    providers_status_parser = providers_subparsers.add_parser(
        "status",
        help="Show provider and local-model readiness.",
    )
    providers_status_parser.set_defaults(func=providers_status)

    local_model_parser = subparsers.add_parser(
        "local-model",
        help="Inspect local model runtime readiness.",
    )
    local_model_subparsers = local_model_parser.add_subparsers(
        dest="local_model_command",
        required=True,
    )
    local_model_status_parser = local_model_subparsers.add_parser(
        "status",
        help="Show local model installed/loading/ready/unavailable status.",
    )
    local_model_status_parser.set_defaults(func=local_model_status_command)

    seed_parser = subparsers.add_parser("seed", help="Load synthetic mock-mode demo data.")
    seed_subparsers = seed_parser.add_subparsers(dest="seed_command", required=True)
    seed_demo_parser = seed_subparsers.add_parser(
        "demo-data",
        help="Seed mock-mode runs, traces, evals, and prompt metadata.",
    )
    seed_demo_parser.add_argument(
        "--trace-db-path",
        default=None,
        help="SQLite trace database path. Defaults to TRACE_DB_PATH or traces.sqlite3.",
    )
    seed_demo_parser.set_defaults(func=seed_demo)

    agents_parser = subparsers.add_parser("agents", help="Inspect managed agent definitions.")
    agents_subparsers = agents_parser.add_subparsers(dest="agents_command", required=True)
    agents_list_parser = agents_subparsers.add_parser("list", help="List managed agents.")
    agents_list_parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Print stable structured JSON.",
    )
    agents_list_parser.set_defaults(func=agents_list)
    agents_show_parser = agents_subparsers.add_parser("show", help="Show one managed agent.")
    agents_show_parser.add_argument("agent_id", help="Agent id to inspect.")
    agents_show_parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Print stable structured JSON.",
    )
    agents_show_parser.set_defaults(func=agents_show)
    agents_run_parser = agents_subparsers.add_parser(
        "run",
        help="Run a managed agent through its backed workflow.",
    )
    agents_run_parser.add_argument("agent_id", help="Agent id to run.")
    agents_run_parser.add_argument("--subject", required=True, help="Support ticket subject.")
    agents_run_parser.add_argument("--body", required=True, help="Support ticket body.")
    agents_run_parser.add_argument(
        "--session-id",
        default=None,
        help="Session id used for the agent run trace. Defaults to the generated run ID.",
    )
    agents_run_parser.add_argument(
        "--trace-db-path",
        default=None,
        help="SQLite trace database path. Defaults to TRACE_DB_PATH or traces.sqlite3.",
    )
    agents_run_parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Print stable structured JSON.",
    )
    agents_run_parser.add_argument(
        "--verbose",
        action="store_true",
        help="Include domain-to-range evidence and full trace detail.",
    )
    agents_run_parser.set_defaults(func=agents_run)
    agents_runs_parser = agents_subparsers.add_parser(
        "runs",
        help="Inspect persisted managed-agent run envelopes.",
    )
    agents_runs_subparsers = agents_runs_parser.add_subparsers(
        dest="agents_runs_command",
        required=True,
    )
    agents_runs_list_parser = agents_runs_subparsers.add_parser(
        "list",
        help="List persisted managed-agent runs.",
    )
    agents_runs_list_parser.add_argument("--limit", type=int, default=10, help="Rows to return.")
    agents_runs_list_parser.add_argument(
        "--trace-db-path",
        default=None,
        help="SQLite trace database path. Defaults to TRACE_DB_PATH or traces.sqlite3.",
    )
    agents_runs_list_parser.set_defaults(func=agents_runs_list)
    agents_runs_show_parser = agents_runs_subparsers.add_parser(
        "show",
        help="Show a persisted managed-agent run envelope.",
    )
    agents_runs_show_parser.add_argument("agent_run_id", help="Agent run id to inspect.")
    agents_runs_show_parser.add_argument(
        "--trace-db-path",
        default=None,
        help="SQLite trace database path. Defaults to TRACE_DB_PATH or traces.sqlite3.",
    )
    agents_runs_show_parser.set_defaults(func=agents_runs_show)

    prompts_parser = subparsers.add_parser("prompts", help="Inspect prompt templates.")
    prompts_subparsers = prompts_parser.add_subparsers(dest="prompts_command", required=True)
    prompts_list_parser = prompts_subparsers.add_parser("list", help="List active prompt templates.")
    prompts_list_parser.set_defaults(func=prompts_list)
    prompts_show_parser = prompts_subparsers.add_parser("show", help="Show a prompt template.")
    prompts_show_parser.add_argument("prompt_id", help="Prompt id to inspect.")
    prompts_show_parser.add_argument("--version", type=int, default=None, help="Prompt version.")
    prompts_show_parser.set_defaults(func=prompts_show)

    def add_trace_commands(command_name: str) -> None:
        trace_parser = subparsers.add_parser(command_name, help="Inspect trace records.")
        trace_subparsers = trace_parser.add_subparsers(
            dest=f"{command_name}_command",
            required=True,
        )
        trace_list_parser = trace_subparsers.add_parser("list", help="List recent trace records.")
        trace_list_parser.add_argument(
            "--limit",
            type=int,
            default=10,
            help="Maximum traces to return.",
        )
        trace_list_parser.add_argument(
            "--trace-db-path",
            default=None,
            help="SQLite trace database path. Defaults to TRACE_DB_PATH or traces.sqlite3.",
        )
        trace_list_parser.set_defaults(func=trace_list)
        trace_show_parser = trace_subparsers.add_parser("show", help="Show one trace by request id.")
        trace_show_parser.add_argument("request_id", help="Request id to inspect.")
        trace_show_parser.add_argument(
            "--trace-db-path",
            default=None,
            help="SQLite trace database path. Defaults to TRACE_DB_PATH or traces.sqlite3.",
        )
        trace_show_parser.add_argument(
            "--json",
            action="store_true",
            dest="json_output",
            help="Print stable structured JSON.",
        )
        trace_show_parser.set_defaults(func=trace_show)

    add_trace_commands("trace")
    add_trace_commands("traces")

    session_parser = subparsers.add_parser("session", help="Inspect session trace history.")
    session_subparsers = session_parser.add_subparsers(dest="session_command", required=True)
    session_show_parser = session_subparsers.add_parser(
        "show",
        help="Show chronological trace history and aggregate metrics for a session.",
    )
    session_show_parser.add_argument("session_id", help="Session id to inspect.")
    session_show_parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Maximum session traces to return.",
    )
    session_show_parser.add_argument(
        "--trace-db-path",
        default=None,
        help="SQLite trace database path. Defaults to TRACE_DB_PATH or traces.sqlite3.",
    )
    session_show_parser.set_defaults(func=session_show)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Exception as exc:
        if not is_known_error(exc) and os.getenv("BLACKLIGHT_DEBUG_ERRORS") == "1":
            raise
        _print_error(describe_exception(exc).as_payload())
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
