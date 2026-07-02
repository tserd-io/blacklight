from __future__ import annotations

import argparse
import json
from typing import Any

from llm_platform_starter.evals.runner import run_ticket_classification_eval
from llm_platform_starter.examples.ticket_classifier import TicketClassifier
from llm_platform_starter.models import TicketRequest
from llm_platform_starter.observability.storage import TraceStore
from llm_platform_starter.prompts.registry import PromptRegistry
from llm_platform_starter.providers.factory import create_provider
from llm_platform_starter.settings import load_settings


def _print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2))


def classify(args: argparse.Namespace) -> int:
    settings = load_settings()
    trace_store = TraceStore(args.trace_db_path or settings.trace_db_path)
    classifier = TicketClassifier(
        provider=create_provider(settings),
        model=settings.model,
        trace_store=trace_store,
    )
    result = classifier.classify(TicketRequest(subject=args.subject, body=args.body))
    _print_json(result.model_dump(mode="json"))
    return 0


def eval_command(_args: argparse.Namespace) -> int:
    _print_json(run_ticket_classification_eval())
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
    _print_json({"trace": trace})
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
        "--trace-db-path",
        default=None,
        help="SQLite trace database path. Defaults to TRACE_DB_PATH or traces.sqlite3.",
    )
    classify_parser.set_defaults(func=classify)

    eval_parser = subparsers.add_parser("eval", help="Run deterministic ticket evals.")
    eval_parser.set_defaults(func=eval_command)

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

    trace_parser = subparsers.add_parser("trace", help="Inspect trace records.")
    trace_subparsers = trace_parser.add_subparsers(dest="trace_command", required=True)
    trace_list_parser = trace_subparsers.add_parser("list", help="List recent trace records.")
    trace_list_parser.add_argument("--limit", type=int, default=10, help="Maximum traces to return.")
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

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
