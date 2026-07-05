from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from typing import Any

from llm_platform_starter.demo_seed import seed_demo_data
from llm_platform_starter.errors import (
    describe_exception,
    is_known_error,
    session_not_found_error,
    trace_not_found_error,
)
from llm_platform_starter.evals.runner import (
    compare_ticket_classification_prompt_versions,
    run_ticket_classification_eval,
)
from llm_platform_starter.examples.ticket_classifier import TicketClassifier
from llm_platform_starter.models import TicketRequest
from llm_platform_starter.observability.evaluations import EvalMetricStore
from llm_platform_starter.observability.idempotency import IdempotencyStore
from llm_platform_starter.observability.storage import TraceStore
from llm_platform_starter.prompts.registry import PromptRegistry
from llm_platform_starter.providers.factory import create_provider
from llm_platform_starter.providers.mock import MockProvider
from llm_platform_starter.session_history import summarize_session, trace_detail
from llm_platform_starter.settings import load_settings

DEMO_SUBJECT = "Refund request"
DEMO_BODY = "Customer asks for a refund after duplicate billing."
DEMO_SESSION_ID = "demo"
DEMO_MODEL = "mock-ticket-classifier"


def _print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2))


def _print_error(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2), file=sys.stderr)


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
            "llm-platform",
            "trace",
            "show",
            trace["request_id"],
            "--trace-db-path",
            db_path,
        ]
    )
    session_command = _command_string(
        [
            "llm-platform",
            "session",
            "show",
            session_id,
            "--trace-db-path",
            db_path,
        ]
    )
    eval_command = _command_string(
        [
            "llm-platform",
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
            "llm-platform",
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
    _print_json(
        {
            "provider": settings.provider,
            "model": settings.model,
            "trace_db_path": settings.trace_db_path,
            "openai_configured": bool(settings.openai_api_key),
            "custom_provider_configured": bool(settings.custom_provider_path),
            "provider_timeout_seconds": settings.provider_timeout_seconds,
            "provider_max_retries": settings.provider_max_retries,
            "provider_rate_limit_requests": settings.provider_rate_limit_requests,
            "provider_rate_limit_window_seconds": settings.provider_rate_limit_window_seconds,
        }
    )
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
    trace = trace_store.get_by_request_id(args.request_id)
    if trace is None:
        _print_error(trace_not_found_error(args.request_id).as_payload())
        return 1
    _print_json({"trace": trace_detail(trace)})
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
        prog="llm-platform",
        description="Run the LLM platform starter demo workflows.",
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
        if not is_known_error(exc) and os.getenv("LLM_PLATFORM_DEBUG_ERRORS") == "1":
            raise
        _print_error(describe_exception(exc).as_payload())
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
