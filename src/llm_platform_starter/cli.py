from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

from llm_platform_starter.errors import describe_exception, is_known_error, trace_not_found_error
from llm_platform_starter.evals.runner import run_ticket_classification_eval
from llm_platform_starter.examples.ticket_classifier import TicketClassifier
from llm_platform_starter.models import TicketRequest
from llm_platform_starter.observability.evaluations import EvalMetricStore
from llm_platform_starter.observability.idempotency import IdempotencyStore
from llm_platform_starter.observability.storage import TraceStore
from llm_platform_starter.prompts.registry import PromptRegistry
from llm_platform_starter.providers.factory import create_provider
from llm_platform_starter.settings import load_settings


def _print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2))


def _print_error(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2), file=sys.stderr)


def _trace_detail(trace: dict[str, Any]) -> dict[str, Any]:
    return {
        "request_id": trace["request_id"],
        "session_id": trace["session_id"],
        "eval_run_id": trace["eval_run_id"],
        "prompt_id": trace["prompt_id"],
        "prompt_version": trace["prompt_version"],
        "provider": trace["provider"],
        "model": trace["model"],
        "latency_ms": trace["latency_ms"],
        "input_tokens": trace["input_tokens"],
        "output_tokens": trace["output_tokens"],
        "estimated_cost_usd": trace["estimated_cost_usd"],
        "validation_passed": trace["validation_passed"],
        "guardrail_outcome": trace["guardrail_outcome"],
        "error_category": trace["error_category"],
        "created_at": trace["created_at"],
    }


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
            eval_store=eval_store,
            trace_store=trace_store,
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
                    "version": prompt.version,
                    "active": prompt.active,
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
            "version": prompt.version,
            "active": prompt.active,
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
    _print_json({"trace": _trace_detail(trace)})
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="llm-platform",
        description="Run the LLM platform starter demo workflows.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

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
    eval_run_parser.set_defaults(func=eval_run)
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
