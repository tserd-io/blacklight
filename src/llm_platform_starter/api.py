from __future__ import annotations

import uuid
from html import escape
from typing import Any
from urllib.parse import parse_qs

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel

from llm_platform_starter.errors import GuardrailValidationError, describe_exception, session_not_found_error
from llm_platform_starter.evals.runner import run_ticket_classification_eval
from llm_platform_starter.examples.ticket_classifier import TicketClassifier
from llm_platform_starter.models import TicketClassification, TicketRequest
from llm_platform_starter.observability.idempotency import (
    IdempotencyInProgressError,
    IdempotencyStore,
)
from llm_platform_starter.observability.evaluations import EvalMetricStore
from llm_platform_starter.observability.reviews import ReviewDecisionStore
from llm_platform_starter.observability.storage import TraceStore
from llm_platform_starter.providers.factory import ProviderConfigurationError, create_provider
from llm_platform_starter.providers.mock import MockProvider
from llm_platform_starter.providers.reliability import ProviderCallError
from llm_platform_starter.prompts.registry import PromptRegistry
from llm_platform_starter.session_history import (
    build_session_history,
    session_trace_detail,
)
from llm_platform_starter.settings import load_settings

settings = load_settings()
trace_store = TraceStore(settings.trace_db_path)
idempotency_store = IdempotencyStore(settings.trace_db_path)
eval_store = EvalMetricStore(settings.trace_db_path)
review_store = ReviewDecisionStore(settings.trace_db_path)
classifier: TicketClassifier | None = None
classifier_startup_error: ProviderConfigurationError | None = None

CONSOLE_NAV = [
    ("dashboard", "Dashboard", "/console"),
    ("workflows", "Workflows", "/console/workflows"),
    ("runs", "Runs", "/console/runs"),
    ("traces", "Traces", "/console/traces"),
    ("evals", "Evals", "/console/evals"),
    ("prompts", "Prompts", "/console/prompts"),
    ("providers", "Providers", "/console/providers"),
    ("review", "Review Queue", "/console/review"),
    ("settings", "Settings", "/console/settings"),
    ("docs", "Docs", "/console/docs"),
]


class ReviewDecisionRequest(BaseModel):
    decision: str
    reviewer: str = "business-reviewer"
    notes: str = ""


class ConsoleWorkflowRunRequest(BaseModel):
    subject: str = "Refund request"
    body: str = "Customer asks for a refund after duplicate billing."
    session_id: str = "console-api-demo"
    idempotency_key: str | None = None


class ConsoleEvalRunRequest(BaseModel):
    session_id: str = "console-api-eval"
    prompt_version: int | None = None


def _build_classifier() -> TicketClassifier:
    return TicketClassifier(
        provider=create_provider(settings),
        model=settings.model,
        trace_store=trace_store,
        idempotency_store=idempotency_store,
        provider_timeout_seconds=settings.provider_timeout_seconds,
        provider_max_retries=settings.provider_max_retries,
        provider_rate_limit_requests=settings.provider_rate_limit_requests,
        provider_rate_limit_window_seconds=settings.provider_rate_limit_window_seconds,
    )


try:
    classifier = _build_classifier()
except ProviderConfigurationError as exc:
    classifier_startup_error = exc

app = FastAPI(title="LLM Platform Starter", version="0.1.0")


def _label(value: Any) -> str:
    return str(value).replace("_", " ").title() if value is not None else "-"


def _money(value: float) -> str:
    return f"${value:.8f}"


def _not_found(session_id: str) -> HTTPException:
    return HTTPException(
        status_code=404,
        detail=session_not_found_error(session_id).as_payload()["error"],
    )


def _session_history_payload(session_id: str, status: str, limit: int) -> dict[str, Any]:
    traces = trace_store.list_by_session_id(session_id, limit=limit)
    if not traces:
        raise _not_found(session_id)
    try:
        payload = build_session_history(
            session_id=session_id,
            traces=traces,
            status_filter=status,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    for trace in payload["traces"]:
        if trace["reviewable"]:
            trace["review_url"] = f"/sessions/{session_id}/review/{trace['request_id']}"
    return payload


def _review_reason(trace: dict[str, Any]) -> str:
    if trace["guardrail_outcome"] == "needs_review":
        return "Guardrails routed this output to human review."
    if trace["guardrail_outcome"] == "rejected":
        return "Guardrails rejected this output before automation."
    return "Output requires review before downstream automation."


def _review_queue_payload(*, limit: int, include_decided: bool) -> dict[str, Any]:
    traces = trace_store.list_reviewable(limit=limit)
    items = []
    for trace in traces:
        decision = review_store.get(trace["request_id"])
        if decision and not include_decided:
            continue
        item = {
            **session_trace_detail(trace),
            "review_reason": _review_reason(trace),
            "decision": decision,
            "review_status": decision["decision"] if decision else "pending",
            "downstream_blocked": decision is None or decision["decision"] != "approved",
        }
        items.append(item)
    return {
        "items": items,
        "summary": {
            "item_count": len(items),
            "pending_count": sum(1 for item in items if item["decision"] is None),
            "approved_count": sum(1 for item in items if item["review_status"] == "approved"),
            "rejected_count": sum(1 for item in items if item["review_status"] == "rejected"),
            "needs_more_info_count": sum(
                1 for item in items if item["review_status"] == "needs_more_info"
            ),
            "blocked_count": sum(1 for item in items if item["downstream_blocked"]),
        },
    }


def _get_reviewable_trace(request_id: str) -> dict[str, Any]:
    trace = trace_store.get_by_request_id(request_id)
    if trace is None:
        raise HTTPException(status_code=404, detail="Trace not found.")
    detail = session_trace_detail(trace)
    if not detail["reviewable"]:
        raise HTTPException(status_code=404, detail="Trace is not reviewable.")
    return trace


def _record_review_decision(
    *,
    request_id: str,
    decision: str,
    reviewer: str,
    notes: str,
) -> dict[str, Any]:
    trace = _get_reviewable_trace(request_id)
    try:
        return review_store.upsert(
            request_id=request_id,
            session_id=trace["session_id"],
            decision=decision,
            reviewer=reviewer or "business-reviewer",
            notes=notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _cli_command(command: str) -> str:
    return f'<code>{escape(command)}</code>'


def _console_shell(*, active: str, title: str, body: str) -> HTMLResponse:
    nav = "\n".join(
        (
            f'<a class="nav-item {"active" if key == active else ""}" '
            f'href="{href}">{escape(label)}</a>'
        )
        for key, label, href in CONSOLE_NAV
    )
    return HTMLResponse(
        f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)} - Blacklight Studio</title>
  <style>
    body {{ margin: 0; font-family: Arial, sans-serif; color: #1f2933; background: #f6f8fb; }}
    .shell {{ display: grid; grid-template-columns: 220px 1fr; min-height: 100vh; }}
    .sidebar {{ background: #17202a; color: #fff; padding: 20px 14px; }}
    .brand {{ font-size: 18px; font-weight: 700; margin: 0 0 18px; }}
    .nav {{ display: grid; gap: 4px; }}
    .nav-item {{ color: #dce5ef; text-decoration: none; padding: 9px 10px; border-radius: 6px; }}
    .nav-item.active, .nav-item:hover {{ background: #2d3a49; color: #fff; }}
    main {{ padding: 28px 28px 44px; max-width: 1240px; }}
    h1 {{ font-size: 24px; margin: 0 0 4px; }}
    h2 {{ font-size: 17px; margin: 0 0 10px; }}
    .muted {{ color: #5d6878; font-size: 14px; margin: 0 0 18px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; margin: 16px 0; }}
    .panel {{ background: #fff; border: 1px solid #d8dee8; border-radius: 8px; padding: 14px; }}
    .panel p {{ margin: 6px 0 0; }}
    .metric {{ font-size: 24px; font-weight: 700; }}
    .toolbar {{ display: flex; flex-wrap: wrap; gap: 10px; margin: 16px 0; }}
    button, .button {{ border: 1px solid #243447; border-radius: 6px; background: #243447; color: #fff; padding: 8px 11px; text-decoration: none; cursor: pointer; }}
    .button.secondary {{ background: #fff; color: #243447; }}
    table {{ width: 100%; border-collapse: collapse; background: #fff; border: 1px solid #d8dee8; margin-top: 12px; }}
    th, td {{ border-bottom: 1px solid #e2e8f0; padding: 10px; text-align: left; vertical-align: top; font-size: 14px; }}
    th {{ background: #edf2f7; font-size: 12px; text-transform: uppercase; color: #526071; }}
    code {{ background: #eef2f6; border: 1px solid #d8dee8; border-radius: 6px; padding: 2px 5px; }}
    .status {{ display: inline-block; border-radius: 999px; padding: 4px 8px; font-size: 12px; background: #edf2f7; }}
    .status.failed, .status.rejected {{ background: #ffe8e8; color: #991b1b; }}
    .status.needs_review, .status.pending {{ background: #fff4d6; color: #8a5a00; }}
    .status.accepted, .status.approved {{ background: #def7ec; color: #046c4e; }}
    .empty {{ color: #64748b; text-align: center; }}
    a {{ color: #1d4ed8; }}
    @media (max-width: 820px) {{
      .shell {{ grid-template-columns: 1fr; }}
      .sidebar {{ position: static; }}
      .nav {{ grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); }}
      main {{ padding: 20px; }}
      table, thead, tbody, tr, th, td {{ display: block; }}
      thead {{ display: none; }}
      tr {{ border-bottom: 1px solid #d8dee8; }}
      td {{ border-bottom: 0; }}
      td::before {{ content: attr(data-label); display: block; color: #64748b; font-size: 12px; margin-bottom: 3px; }}
    }}
  </style>
</head>
<body>
  <div class="shell">
    <aside class="sidebar">
      <div class="brand">Blacklight Studio</div>
      <nav class="nav" aria-label="Console navigation">{nav}</nav>
    </aside>
    <main>{body}</main>
  </div>
</body>
</html>"""
    )


def _console_command_panel(command: str) -> str:
    return f'<div class="panel"><h2>CLI Equivalent</h2><p>{_cli_command(command)}</p></div>'


def _trace_db_arg() -> str:
    return f"--trace-db-path {settings.trace_db_path}"


def _prompt_payload(prompt_id: str, version: int | None = None) -> dict[str, Any]:
    try:
        prompt = PromptRegistry().get(prompt_id, version=version)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    version_arg = f" --version {prompt.version}" if version is not None else ""
    return {
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
        "cli": {
            "show": f"llm-platform prompts show {prompt.prompt_id}{version_arg}",
            "list": "llm-platform prompts list",
        },
    }


def _trace_payload(trace: dict[str, Any]) -> dict[str, Any]:
    detail = session_trace_detail(trace)
    payload = {
        **detail,
        "links": {
            "session_api": f"/api/sessions/{trace['session_id']}",
            "session_ui": f"/sessions/{trace['session_id']}",
        },
        "cli": {
            "show": f"llm-platform trace show {trace['request_id']} {_trace_db_arg()}",
            "session": f"llm-platform session show {trace['session_id']} {_trace_db_arg()}",
            "list": f"llm-platform trace list {_trace_db_arg()} --limit 10",
        },
    }
    if detail["reviewable"]:
        payload["links"]["review_ui"] = (
            f"/sessions/{trace['session_id']}/review/{trace['request_id']}"
        )
    if trace["eval_run_id"]:
        payload["links"]["eval_api"] = f"/api/console/evals/{trace['eval_run_id']}"
        payload["cli"]["eval"] = (
            f"llm-platform eval show {trace['eval_run_id']} {_trace_db_arg()}"
        )
    return payload


def _session_run_summaries(limit: int = 50) -> list[dict[str, Any]]:
    sessions: dict[str, dict[str, Any]] = {}
    for trace in trace_store.list_recent(limit=limit):
        session = sessions.setdefault(
            trace["session_id"],
            {
                "session_id": trace["session_id"],
                "request_count": 0,
                "latest_created_at": trace["created_at"],
                "failure_count": 0,
                "review_count": 0,
                "total_tokens": 0,
                "total_estimated_cost_usd": 0.0,
            },
        )
        session["request_count"] += 1
        session["failure_count"] += 1 if trace["error_category"] is not None else 0
        session["review_count"] += 1 if trace["guardrail_outcome"] == "needs_review" else 0
        session["total_tokens"] += trace["input_tokens"] + trace["output_tokens"]
        session["total_estimated_cost_usd"] += trace["estimated_cost_usd"]
    runs = []
    for session in sessions.values():
        session["total_estimated_cost_usd"] = round(session["total_estimated_cost_usd"], 8)
        session["cli"] = {
            "show": f"llm-platform session show {session['session_id']} {_trace_db_arg()}",
        }
        session["links"] = {
            "api": f"/api/console/runs/{session['session_id']}",
            "ui": f"/sessions/{session['session_id']}",
        }
        runs.append(session)
    return runs


def _workflow_payload(workflow_id: str = "ticket_classifier") -> dict[str, Any]:
    if workflow_id != "ticket_classifier":
        raise HTTPException(status_code=404, detail=f"Workflow not found: {workflow_id}")
    return {
        "workflow_id": workflow_id,
        "display_name": "Ticket Classifier",
        "description": "Classifies support-style work items with validation, tracing, and review routing.",
        "provider": settings.provider,
        "model": settings.model,
        "mock_mode_available": True,
        "sample_input": {
            "subject": "Refund request",
            "body": "Customer asks for a refund after duplicate billing.",
            "session_id": "console-api-demo",
        },
        "cli": {
            "run": (
                'llm-platform classify --subject "Refund request" '
                '--body "Customer asks for a refund after duplicate billing." '
                f"--session-id console-api-demo {_trace_db_arg()}"
            ),
            "demo": f"llm-platform demo --verbose {_trace_db_arg()}",
        },
        "links": {
            "run": f"/api/console/workflows/{workflow_id}/run",
            "traces": "/api/console/traces",
        },
    }


def _eval_run_payload(run: dict[str, Any]) -> dict[str, Any]:
    eval_run_id = run["eval_run_id"]
    return {
        **run,
        "links": {
            "api": f"/api/console/evals/{eval_run_id}",
            "session_api": f"/api/console/runs/{run['session_id']}",
            "session_ui": f"/sessions/{run['session_id']}",
        },
        "cli": {
            "show": f"llm-platform eval show {eval_run_id} {_trace_db_arg()}",
            "list": f"llm-platform eval list {_trace_db_arg()}",
        },
    }


def _provider_payload(provider: str) -> dict[str, Any]:
    provider = provider.lower()
    if provider not in {"mock", "openai", "custom"}:
        raise HTTPException(status_code=404, detail=f"Provider not found: {provider}")
    configured = {
        "mock": True,
        "openai": bool(settings.openai_api_key),
        "custom": bool(settings.custom_provider_path),
    }[provider]
    return {
        "provider": provider,
        "active": settings.provider == provider,
        "configured": configured,
        "ready": configured,
        "requires_live_credentials": provider != "mock",
        "model": settings.model if settings.provider == provider else None,
        "configuration_hint": {
            "mock": "Ready by default for demos and tests.",
            "openai": "Set LLM_PROVIDER=openai and OPENAI_API_KEY.",
            "custom": "Set LLM_PROVIDER=custom and LLM_CUSTOM_PROVIDER to an import path.",
        }[provider],
        "cli": {
            "health": "llm-platform health",
            "demo": f"llm-platform demo --verbose {_trace_db_arg()}",
        },
    }


def _settings_payload() -> dict[str, Any]:
    return {
        "provider": settings.provider,
        "model": settings.model,
        "trace_db_path": settings.trace_db_path,
        "openai_configured": bool(settings.openai_api_key),
        "custom_provider_configured": bool(settings.custom_provider_path),
        "provider_timeout_seconds": settings.provider_timeout_seconds,
        "provider_max_retries": settings.provider_max_retries,
        "provider_rate_limit_requests": settings.provider_rate_limit_requests,
        "provider_rate_limit_window_seconds": settings.provider_rate_limit_window_seconds,
        "cli": {"health": "llm-platform health"},
    }


def _dashboard_payload(limit: int = 5) -> dict[str, Any]:
    review_payload = _review_queue_payload(limit=100, include_decided=False)
    return {
        "dashboard": "console",
        "metrics": trace_store.metrics(),
        "recent_traces": [_trace_payload(trace) for trace in trace_store.list_recent(limit=limit)],
        "recent_eval_runs": [
            _eval_run_payload(run) for run in eval_store.list_runs(limit=limit)
        ],
        "review_queue": review_payload["summary"],
        "workflows": [_workflow_payload()],
        "providers": [_provider_payload(provider) for provider in ["mock", "openai", "custom"]],
        "settings": _settings_payload(),
        "links": {
            "console": "/console",
            "workflows": "/api/console/workflows",
            "runs": "/api/console/runs",
            "traces": "/api/console/traces",
            "evals": "/api/console/evals",
            "prompts": "/api/console/prompts",
            "providers": "/api/console/providers",
            "reviews": "/api/console/reviews",
            "settings": "/api/console/settings",
        },
        "cli": {
            "guided_demo": f"llm-platform demo --verbose {_trace_db_arg()}",
            "seed_demo_data": f"llm-platform seed demo-data {_trace_db_arg()}",
            "health": "llm-platform health",
        },
    }


def _render_console_dashboard() -> HTMLResponse:
    metrics_payload = trace_store.metrics()
    recent_traces = trace_store.list_recent(limit=5)
    eval_runs = eval_store.list_runs(limit=5)
    review_payload = _review_queue_payload(limit=100, include_decided=False)
    trace_rows = "\n".join(_console_trace_row(trace) for trace in recent_traces)
    if not trace_rows:
        trace_rows = '<tr><td colspan="5" class="empty">No traces yet.</td></tr>'
    eval_rows = "\n".join(_console_eval_row(run) for run in eval_runs)
    if not eval_rows:
        eval_rows = '<tr><td colspan="5" class="empty">No eval runs yet.</td></tr>'
    body = f"""
<h1>Dashboard</h1>
<p class="muted">Local console for workflow runs, traces, evals, prompts, providers, and review.</p>
<div class="toolbar">
  <form method="post" action="/console/run-demo"><button type="submit">Run Demo</button></form>
  <a class="button secondary" href="/console/traces">Recent Traces</a>
  <a class="button secondary" href="/console/evals">Recent Evals</a>
  <a class="button secondary" href="/reviews">Review Queue</a>
</div>
<section class="grid">
  <div class="panel"><h2>Requests</h2><div class="metric">{metrics_payload["request_count"]}</div></div>
  <div class="panel"><h2>Failure Rate</h2><div class="metric">{metrics_payload["failure_rate"]}</div></div>
  <div class="panel"><h2>Total Cost</h2><div class="metric">{_money(metrics_payload["total_estimated_cost_usd"])}</div></div>
  <div class="panel"><h2>Pending Review</h2><div class="metric">{review_payload["summary"]["pending_count"]}</div></div>
</section>
<section class="grid">
  {_console_command_panel("llm-platform demo --verbose")}
  {_console_command_panel("llm-platform seed demo-data --trace-db-path traces.sqlite3")}
</section>
<h2>Recent Traces</h2>
<table>
  <thead><tr><th>Time</th><th>Request</th><th>Session</th><th>Status</th><th>Inspect</th></tr></thead>
  <tbody>{trace_rows}</tbody>
</table>
<h2 style="margin-top:18px;">Recent Evals</h2>
<table>
  <thead><tr><th>Run</th><th>Session</th><th>Prompt</th><th>Accuracy</th><th>Inspect</th></tr></thead>
  <tbody>{eval_rows}</tbody>
</table>"""
    return _console_shell(active="dashboard", title="Dashboard", body=body)


def _console_trace_row(trace: dict[str, Any]) -> str:
    detail = session_trace_detail(trace)
    status = escape(detail["status"])
    session_id = escape(trace["session_id"])
    request_id = escape(trace["request_id"])
    inspect_href = (
        f"/sessions/{session_id}/review/{request_id}"
        if detail["reviewable"]
        else f"/sessions/{session_id}"
    )
    return f"""<tr>
  <td data-label="Time">{escape(trace["created_at"])}</td>
  <td data-label="Request"><code>{request_id}</code></td>
  <td data-label="Session"><a href="/sessions/{session_id}">{session_id}</a></td>
  <td data-label="Status"><span class="status {status}">{escape(_label(status))}</span></td>
  <td data-label="Inspect"><a href="{inspect_href}">Open</a></td>
</tr>"""


def _console_eval_row(run: dict[str, Any]) -> str:
    eval_run_id = escape(run["eval_run_id"])
    session_id = escape(run["session_id"])
    return f"""<tr>
  <td data-label="Run"><code>{eval_run_id}</code></td>
  <td data-label="Session"><a href="/sessions/{session_id}">{session_id}</a></td>
  <td data-label="Prompt">{escape(run["prompt_id"])} v{run["prompt_version"]}</td>
  <td data-label="Accuracy">{run["accuracy"]}</td>
  <td data-label="Inspect">{_cli_command(f"llm-platform eval show {run['eval_run_id']} --trace-db-path {settings.trace_db_path}")}</td>
</tr>"""


def _run_console_demo() -> dict[str, Any]:
    demo_classifier = TicketClassifier(
        provider=MockProvider(),
        model=settings.model,
        trace_store=trace_store,
        idempotency_store=idempotency_store,
        provider_timeout_seconds=settings.provider_timeout_seconds,
        provider_max_retries=settings.provider_max_retries,
        provider_rate_limit_requests=settings.provider_rate_limit_requests,
        provider_rate_limit_window_seconds=settings.provider_rate_limit_window_seconds,
    )
    result = demo_classifier.classify(
        TicketRequest(
            subject="Refund request",
            body="Customer asks for a refund after duplicate billing.",
            session_id="console-demo",
            idempotency_key=f"console-demo-{uuid.uuid4()}",
        )
    )
    trace = trace_store.list_by_session_id("console-demo", limit=500)[-1]
    return {"result": result.model_dump(mode="json"), "trace": trace}


def _render_console_demo_result(payload: dict[str, Any]) -> HTMLResponse:
    trace = payload["trace"]
    result = payload["result"]
    session_id = escape(trace["session_id"])
    request_id = escape(trace["request_id"])
    body = f"""
<h1>Demo Result</h1>
<p class="muted">ticket_classifier / mock provider</p>
<section class="grid">
  <div class="panel"><h2>Category</h2><div class="metric">{escape(result["category"])}</div></div>
  <div class="panel"><h2>Severity</h2><div class="metric">{escape(result["severity"])}</div></div>
  <div class="panel"><h2>Review</h2><div class="metric">{escape(str(result["needs_review"]))}</div></div>
</section>
<div class="toolbar">
  <a class="button" href="/sessions/{session_id}">Open Session</a>
  <a class="button secondary" href="/console/traces">Open Traces</a>
</div>
<section class="grid">
  <div class="panel"><h2>Trace</h2><p><code>{request_id}</code></p></div>
  {_console_command_panel("llm-platform demo --verbose")}
  {_console_command_panel(f"llm-platform trace show {trace['request_id']} --trace-db-path {settings.trace_db_path}")}
</section>"""
    return _console_shell(active="workflows", title="Demo Result", body=body)


def _render_console_workflows() -> HTMLResponse:
    body = f"""
<h1>Workflows</h1>
<p class="muted">Runnable workflow surfaces.</p>
<section class="grid">
  <div class="panel">
    <h2>ticket_classifier</h2>
    <p>Provider: {escape(settings.provider)}</p>
    <p>Model: {escape(settings.model)}</p>
    <div class="toolbar"><form method="post" action="/console/run-demo"><button type="submit">Run Demo</button></form></div>
  </div>
  {_console_command_panel('llm-platform classify --subject "Refund request" --body "Customer asks for a refund after duplicate billing." --session-id demo')}
</section>"""
    return _console_shell(active="workflows", title="Workflows", body=body)


def _render_console_runs() -> HTMLResponse:
    traces = trace_store.list_recent(limit=50)
    sessions: dict[str, dict[str, Any]] = {}
    for trace in traces:
        session = sessions.setdefault(
            trace["session_id"],
            {"session_id": trace["session_id"], "request_count": 0, "latest": trace["created_at"]},
        )
        session["request_count"] += 1
    rows = "\n".join(
        f"""<tr>
  <td data-label="Session"><a href="/sessions/{escape(item['session_id'])}">{escape(item['session_id'])}</a></td>
  <td data-label="Requests">{item["request_count"]}</td>
  <td data-label="Latest">{escape(item["latest"])}</td>
  <td data-label="CLI">{_cli_command(f"llm-platform session show {item['session_id']} --trace-db-path {settings.trace_db_path}")}</td>
</tr>"""
        for item in sessions.values()
    )
    if not rows:
        rows = '<tr><td colspan="4" class="empty">No runs yet.</td></tr>'
    body = f"""
<h1>Runs</h1>
<p class="muted">Session-level workflow history.</p>
<table>
  <thead><tr><th>Session</th><th>Requests</th><th>Latest</th><th>CLI</th></tr></thead>
  <tbody>{rows}</tbody>
</table>"""
    return _console_shell(active="runs", title="Runs", body=body)


def _render_console_traces() -> HTMLResponse:
    rows = "\n".join(_console_trace_row(trace) for trace in trace_store.list_recent(limit=25))
    if not rows:
        rows = '<tr><td colspan="5" class="empty">No traces yet.</td></tr>'
    body = f"""
<h1>Traces</h1>
<p class="muted">Recent provider calls and validation outcomes.</p>
<section class="grid">{_console_command_panel("llm-platform trace list --trace-db-path traces.sqlite3 --limit 10")}</section>
<table>
  <thead><tr><th>Time</th><th>Request</th><th>Session</th><th>Status</th><th>Inspect</th></tr></thead>
  <tbody>{rows}</tbody>
</table>"""
    return _console_shell(active="traces", title="Traces", body=body)


def _render_console_evals() -> HTMLResponse:
    rows = "\n".join(_console_eval_row(run) for run in eval_store.list_runs(limit=25))
    if not rows:
        rows = '<tr><td colspan="5" class="empty">No eval runs yet.</td></tr>'
    body = f"""
<h1>Evals</h1>
<p class="muted">Persisted regression reports.</p>
<section class="grid">
  {_console_command_panel("llm-platform eval run --trace-db-path traces.sqlite3 --session-id eval-demo")}
  {_console_command_panel("llm-platform eval list --trace-db-path traces.sqlite3")}
</section>
<table>
  <thead><tr><th>Run</th><th>Session</th><th>Prompt</th><th>Accuracy</th><th>Inspect</th></tr></thead>
  <tbody>{rows}</tbody>
</table>"""
    return _console_shell(active="evals", title="Evals", body=body)


def _render_console_prompts() -> HTMLResponse:
    prompts = PromptRegistry().list()
    rows = "\n".join(
        f"""<tr>
  <td data-label="Prompt">{escape(prompt.prompt_id)}</td>
  <td data-label="Version">{prompt.version}</td>
  <td data-label="Schema">{escape(prompt.output_schema)}</td>
  <td data-label="Group">{escape(prompt.comparison_group)}</td>
  <td data-label="CLI">{_cli_command(f"llm-platform prompts show {prompt.prompt_id}")}</td>
</tr>"""
        for prompt in prompts
    )
    body = f"""
<h1>Prompts</h1>
<p class="muted">Prompt registry metadata.</p>
<section class="grid">{_console_command_panel("llm-platform prompts list")}</section>
<table>
  <thead><tr><th>Prompt</th><th>Version</th><th>Schema</th><th>Group</th><th>CLI</th></tr></thead>
  <tbody>{rows}</tbody>
</table>"""
    return _console_shell(active="prompts", title="Prompts", body=body)


def _render_console_providers() -> HTMLResponse:
    body = f"""
<h1>Providers</h1>
<p class="muted">Runtime provider readiness.</p>
<section class="grid">
  <div class="panel"><h2>Provider</h2><div class="metric">{escape(settings.provider)}</div></div>
  <div class="panel"><h2>Model</h2><div class="metric">{escape(settings.model)}</div></div>
  <div class="panel"><h2>OpenAI Key</h2><div class="metric">{escape(str(bool(settings.openai_api_key)))}</div></div>
  <div class="panel"><h2>Custom Provider</h2><div class="metric">{escape(str(bool(settings.custom_provider_path)))}</div></div>
  {_console_command_panel("llm-platform health")}
</section>"""
    return _console_shell(active="providers", title="Providers", body=body)


def _render_console_review() -> HTMLResponse:
    payload = _review_queue_payload(limit=100, include_decided=True)
    body = f"""
<h1>Review Queue</h1>
<p class="muted">Business review status for guarded outputs.</p>
<section class="grid">
  <div class="panel"><h2>Items</h2><div class="metric">{payload["summary"]["item_count"]}</div></div>
  <div class="panel"><h2>Blocked</h2><div class="metric">{payload["summary"]["blocked_count"]}</div></div>
  <div class="panel"><h2>Pending</h2><div class="metric">{payload["summary"]["pending_count"]}</div></div>
  <div class="panel"><h2>Approved</h2><div class="metric">{payload["summary"]["approved_count"]}</div></div>
  <div class="panel"><h2>Queue</h2><p><a href="/reviews">Open review queue</a></p></div>
  {_console_command_panel("llm-platform trace list --trace-db-path traces.sqlite3 --limit 10")}
</section>"""
    return _console_shell(active="review", title="Review Queue", body=body)


def _render_console_settings() -> HTMLResponse:
    body = f"""
<h1>Settings</h1>
<p class="muted">Local runtime settings.</p>
<section class="grid">
  <div class="panel"><h2>Trace DB</h2><p><code>{escape(settings.trace_db_path)}</code></p></div>
  <div class="panel"><h2>Timeout</h2><div class="metric">{settings.provider_timeout_seconds}</div></div>
  <div class="panel"><h2>Retries</h2><div class="metric">{settings.provider_max_retries}</div></div>
  <div class="panel"><h2>Rate Limit</h2><p>{settings.provider_rate_limit_requests} / {settings.provider_rate_limit_window_seconds}s</p></div>
  {_console_command_panel("llm-platform health")}
</section>"""
    return _console_shell(active="settings", title="Settings", body=body)


def _render_console_docs() -> HTMLResponse:
    links = [
        ("Architecture", "/docs/architecture.md"),
        ("Provider Configuration", "/docs/provider-configuration.md"),
        ("Eval Methodology", "/docs/eval-methodology.md"),
        ("Create Your Own Workflow", "/docs/create-your-own-workflow.md"),
        ("Tradeoffs", "/docs/tradeoffs.md"),
    ]
    items = "\n".join(
        f'<div class="panel"><h2>{escape(label)}</h2><p><code>{escape(path)}</code></p></div>'
        for label, path in links
    )
    body = f"""
<h1>Docs And Recipes</h1>
<p class="muted">Local docs paths for implementation review.</p>
<section class="grid">{items}</section>"""
    return _console_shell(active="docs", title="Docs And Recipes", body=body)


def _filter_link(session_id: str, status: str, current_status: str, limit: int) -> str:
    selected = " selected" if status == current_status else ""
    href = f"/sessions/{escape(session_id)}?status={escape(status)}&limit={limit}"
    return f'<a class="filter{selected}" href="{href}">{escape(_label(status))}</a>'


def _render_session_history(payload: dict[str, Any], *, limit: int) -> str:
    session_id = escape(payload["session_id"])
    status_filter = payload["status_filter"]
    summary = payload["summary"]
    filtered_summary = payload["filtered_summary"]
    filters = " ".join(
        _filter_link(payload["session_id"], status, status_filter, limit)
        for status in ["all", "accepted", "needs_review", "rejected", "failed"]
    )
    rows = "\n".join(_render_timeline_row(payload["session_id"], trace) for trace in payload["traces"])
    if not rows:
        rows = '<tr><td colspan="8" class="empty">No traces match this filter.</td></tr>'

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Session {session_id} - LLM Platform Starter</title>
  <style>
    body {{ margin: 0; font-family: Arial, sans-serif; color: #1f2933; background: #f7f9fb; }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 28px 20px 40px; }}
    h1 {{ font-size: 24px; margin: 0 0 4px; }}
    .muted {{ color: #5d6878; font-size: 14px; margin: 0 0 18px; }}
    .summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; margin: 18px 0; }}
    .metric {{ background: #fff; border: 1px solid #d8dee8; border-radius: 8px; padding: 12px; }}
    .metric span {{ display: block; color: #64748b; font-size: 12px; margin-bottom: 5px; }}
    .metric strong {{ font-size: 18px; }}
    .filters {{ display: flex; flex-wrap: wrap; gap: 8px; margin: 20px 0 12px; }}
    .filter {{ border: 1px solid #b8c2d2; border-radius: 6px; color: #243447; padding: 7px 10px; text-decoration: none; background: #fff; font-size: 14px; }}
    .filter.selected {{ background: #243447; color: #fff; border-color: #243447; }}
    table {{ width: 100%; border-collapse: collapse; background: #fff; border: 1px solid #d8dee8; }}
    th, td {{ border-bottom: 1px solid #e2e8f0; padding: 10px; text-align: left; vertical-align: top; font-size: 14px; }}
    th {{ background: #edf2f7; font-size: 12px; text-transform: uppercase; color: #526071; }}
    .status {{ display: inline-block; border-radius: 999px; padding: 4px 8px; font-size: 12px; background: #edf2f7; }}
    .status.failed, .status.rejected {{ background: #ffe8e8; color: #991b1b; }}
    .status.needs_review {{ background: #fff4d6; color: #8a5a00; }}
    .status.accepted {{ background: #def7ec; color: #046c4e; }}
    .mono {{ font-family: Consolas, monospace; font-size: 13px; }}
    .empty {{ color: #64748b; text-align: center; }}
    a {{ color: #1d4ed8; }}
    @media (max-width: 760px) {{
      table, thead, tbody, tr, th, td {{ display: block; }}
      thead {{ display: none; }}
      tr {{ border-bottom: 1px solid #d8dee8; }}
      td {{ border-bottom: 0; }}
      td::before {{ content: attr(data-label); display: block; color: #64748b; font-size: 12px; margin-bottom: 3px; }}
    }}
  </style>
</head>
<body>
<main>
  <h1>Session {session_id}</h1>
  <p class="muted">Timeline of workflow runs from the trace database.</p>
  <section class="summary">
    <div class="metric"><span>Requests</span><strong>{summary["request_count"]}</strong></div>
    <div class="metric"><span>Visible</span><strong>{filtered_summary["request_count"]}</strong></div>
    <div class="metric"><span>Total Tokens</span><strong>{summary["total_tokens"]}</strong></div>
    <div class="metric"><span>Estimated Cost</span><strong>{_money(summary["total_estimated_cost_usd"])}</strong></div>
    <div class="metric"><span>Failures</span><strong>{summary["failure_count"]}</strong></div>
    <div class="metric"><span>Needs Review</span><strong>{summary["review_count"]}</strong></div>
  </section>
  <nav class="filters" aria-label="Session filters">{filters}</nav>
  <table>
    <thead>
      <tr>
        <th>Time</th><th>Request</th><th>Status</th><th>Provider</th>
        <th>Model</th><th>Cost</th><th>Review</th><th>Failure</th>
      </tr>
    </thead>
    <tbody>{rows}</tbody>
  </table>
</main>
</body>
</html>"""


def _render_timeline_row(session_id: str, trace: dict[str, Any]) -> str:
    review = escape(_label(trace["review_outcome"]))
    if trace["reviewable"]:
        review = (
            f'<a href="/sessions/{escape(session_id)}/review/{escape(trace["request_id"])}">'
            f"{review}</a>"
        )
    status = escape(trace["status"])
    failure_reason = escape(_label(trace["failure_reason"]))
    return f"""<tr>
  <td data-label="Time">{escape(trace["created_at"])}</td>
  <td data-label="Request" class="mono">{escape(trace["request_id"])}</td>
  <td data-label="Status"><span class="status {status}">{escape(_label(status))}</span></td>
  <td data-label="Provider">{escape(trace["provider"])}</td>
  <td data-label="Model">{escape(trace["model"])}</td>
  <td data-label="Cost">{_money(trace["estimated_cost_usd"])}</td>
  <td data-label="Review">{review}</td>
  <td data-label="Failure">{failure_reason}</td>
</tr>"""


def _render_review_page(session_id: str, trace: dict[str, Any]) -> str:
    detail_rows = "\n".join(
        f"<tr><th>{escape(_label(key))}</th><td>{escape(str(value))}</td></tr>"
        for key, value in trace.items()
        if key != "review_url"
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Review {escape(trace["request_id"])} - LLM Platform Starter</title>
  <style>
    body {{ margin: 0; font-family: Arial, sans-serif; color: #1f2933; background: #f7f9fb; }}
    main {{ max-width: 900px; margin: 0 auto; padding: 28px 20px 40px; }}
    h1 {{ font-size: 24px; margin: 0 0 4px; }}
    a {{ color: #1d4ed8; }}
    table {{ width: 100%; border-collapse: collapse; background: #fff; border: 1px solid #d8dee8; margin-top: 18px; }}
    th, td {{ border-bottom: 1px solid #e2e8f0; padding: 10px; text-align: left; vertical-align: top; }}
    th {{ width: 220px; background: #edf2f7; color: #526071; }}
  </style>
</head>
<body>
<main>
  <a href="/sessions/{escape(session_id)}">Back to session</a>
  <h1>Review Trace</h1>
  <table>{detail_rows}</table>
</main>
</body>
</html>"""


def _render_review_queue(payload: dict[str, Any], *, include_decided: bool, limit: int) -> str:
    summary = payload["summary"]
    rows = "\n".join(_render_review_queue_row(item) for item in payload["items"])
    if not rows:
        rows = '<tr><td colspan="9" class="empty">No reviewable outputs match this view.</td></tr>'
    include_checked = " checked" if include_decided else ""
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Business Review Queue - LLM Platform Starter</title>
  <style>
    body {{ margin: 0; font-family: Arial, sans-serif; color: #1f2933; background: #f7f9fb; }}
    main {{ max-width: 1280px; margin: 0 auto; padding: 28px 20px 40px; }}
    h1 {{ font-size: 24px; margin: 0 0 4px; }}
    .muted {{ color: #5d6878; font-size: 14px; margin: 0 0 18px; }}
    .summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; margin: 18px 0; }}
    .metric {{ background: #fff; border: 1px solid #d8dee8; border-radius: 8px; padding: 12px; }}
    .metric span {{ display: block; color: #64748b; font-size: 12px; margin-bottom: 5px; }}
    .metric strong {{ font-size: 18px; }}
    .toolbar {{ display: flex; align-items: center; gap: 10px; margin: 14px 0; }}
    .toolbar input[type="number"] {{ width: 72px; }}
    table {{ width: 100%; border-collapse: collapse; background: #fff; border: 1px solid #d8dee8; }}
    th, td {{ border-bottom: 1px solid #e2e8f0; padding: 10px; text-align: left; vertical-align: top; font-size: 14px; }}
    th {{ background: #edf2f7; font-size: 12px; text-transform: uppercase; color: #526071; }}
    .status {{ display: inline-block; border-radius: 999px; padding: 4px 8px; font-size: 12px; background: #edf2f7; }}
    .status.pending, .status.needs_more_info {{ background: #fff4d6; color: #8a5a00; }}
    .status.rejected {{ background: #ffe8e8; color: #991b1b; }}
    .status.approved {{ background: #def7ec; color: #046c4e; }}
    .blocked {{ color: #991b1b; font-weight: 700; }}
    .open {{ color: #046c4e; font-weight: 700; }}
    .mono {{ font-family: Consolas, monospace; font-size: 13px; }}
    .empty {{ color: #64748b; text-align: center; }}
    form.inline {{ display: grid; grid-template-columns: 1fr; gap: 6px; min-width: 190px; }}
    form.inline input, form.inline select {{ width: 100%; box-sizing: border-box; }}
    button {{ border: 1px solid #243447; border-radius: 6px; background: #243447; color: #fff; padding: 7px 10px; cursor: pointer; }}
    a {{ color: #1d4ed8; }}
    @media (max-width: 900px) {{
      table, thead, tbody, tr, th, td {{ display: block; }}
      thead {{ display: none; }}
      tr {{ border-bottom: 1px solid #d8dee8; }}
      td {{ border-bottom: 0; }}
      td::before {{ content: attr(data-label); display: block; color: #64748b; font-size: 12px; margin-bottom: 3px; }}
    }}
  </style>
</head>
<body>
<main>
  <h1>Business Review Queue</h1>
  <p class="muted">Reviewable guardrail outputs before they move into automated downstream work.</p>
  <section class="summary">
    <div class="metric"><span>Visible Items</span><strong>{summary["item_count"]}</strong></div>
    <div class="metric"><span>Pending</span><strong>{summary["pending_count"]}</strong></div>
    <div class="metric"><span>Approved</span><strong>{summary["approved_count"]}</strong></div>
    <div class="metric"><span>Rejected</span><strong>{summary["rejected_count"]}</strong></div>
    <div class="metric"><span>Needs More Info</span><strong>{summary["needs_more_info_count"]}</strong></div>
    <div class="metric"><span>Blocked</span><strong>{summary["blocked_count"]}</strong></div>
  </section>
  <form class="toolbar" method="get" action="/reviews">
    <label><input type="checkbox" name="include_decided" value="true"{include_checked}> Include decided</label>
    <label>Limit <input type="number" name="limit" min="1" max="500" value="{limit}"></label>
    <button type="submit">Apply</button>
  </form>
  <table>
    <thead>
      <tr>
        <th>Time</th><th>Request</th><th>Session</th><th>Reason</th><th>Model</th>
        <th>Review Status</th><th>Downstream</th><th>Decision</th><th>Action</th>
      </tr>
    </thead>
    <tbody>{rows}</tbody>
  </table>
</main>
</body>
</html>"""


def _render_review_queue_row(item: dict[str, Any]) -> str:
    request_id = escape(item["request_id"])
    session_id = escape(item["session_id"])
    decision = item["decision"]
    decision_text = "-"
    if decision:
        decision_text = (
            f"{escape(_label(decision['decision']))}<br>"
            f"<span class=\"muted\">{escape(decision['reviewer'])} at "
            f"{escape(decision['decided_at'])}</span>"
        )
        if decision["notes"]:
            decision_text += f"<br>{escape(decision['notes'])}"
    downstream = "Blocked" if item["downstream_blocked"] else "Allowed"
    downstream_class = "blocked" if item["downstream_blocked"] else "open"
    return f"""<tr>
  <td data-label="Time">{escape(item["created_at"])}</td>
  <td data-label="Request" class="mono"><a href="/sessions/{session_id}/review/{request_id}">{request_id}</a></td>
  <td data-label="Session">{session_id}</td>
  <td data-label="Reason">{escape(item["review_reason"])}</td>
  <td data-label="Model">{escape(item["provider"])} / {escape(item["model"])}</td>
  <td data-label="Review Status"><span class="status {escape(item["review_status"])}">{escape(_label(item["review_status"]))}</span></td>
  <td data-label="Downstream" class="{downstream_class}">{downstream}</td>
  <td data-label="Decision">{decision_text}</td>
  <td data-label="Action">
    <form class="inline" method="post" action="/reviews/{request_id}">
      <select name="decision" aria-label="Decision">
        <option value="approved">Approve</option>
        <option value="rejected">Reject</option>
        <option value="needs_more_info">Needs More Info</option>
      </select>
      <input name="reviewer" value="business-reviewer" aria-label="Reviewer">
      <input name="notes" placeholder="Notes" aria-label="Notes">
      <button type="submit">Record</button>
    </form>
  </td>
</tr>"""


def _error_response(exc: Exception, status_code: int) -> JSONResponse:
    return JSONResponse(status_code=status_code, content=describe_exception(exc).as_payload())


@app.exception_handler(ProviderConfigurationError)
def provider_configuration_error_handler(_request: Any, exc: ProviderConfigurationError) -> JSONResponse:
    return _error_response(exc, status_code=500)


@app.exception_handler(ProviderCallError)
def provider_call_error_handler(_request: Any, exc: ProviderCallError) -> JSONResponse:
    return _error_response(exc, status_code=503)


@app.exception_handler(IdempotencyInProgressError)
def idempotency_error_handler(_request: Any, exc: IdempotencyInProgressError) -> JSONResponse:
    return _error_response(exc, status_code=409)


@app.exception_handler(GuardrailValidationError)
def validation_error_handler(_request: Any, exc: GuardrailValidationError) -> JSONResponse:
    return _error_response(exc, status_code=422)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def root_console() -> RedirectResponse:
    return RedirectResponse(url="/console", status_code=307)


@app.get("/console", response_class=HTMLResponse)
def console_dashboard() -> HTMLResponse:
    return _render_console_dashboard()


@app.post("/console/run-demo", response_class=HTMLResponse)
def console_run_demo() -> HTMLResponse:
    return _render_console_demo_result(_run_console_demo())


@app.get("/console/workflows", response_class=HTMLResponse)
def console_workflows() -> HTMLResponse:
    return _render_console_workflows()


@app.get("/console/runs", response_class=HTMLResponse)
def console_runs() -> HTMLResponse:
    return _render_console_runs()


@app.get("/console/traces", response_class=HTMLResponse)
def console_traces() -> HTMLResponse:
    return _render_console_traces()


@app.get("/console/evals", response_class=HTMLResponse)
def console_evals() -> HTMLResponse:
    return _render_console_evals()


@app.get("/console/prompts", response_class=HTMLResponse)
def console_prompts() -> HTMLResponse:
    return _render_console_prompts()


@app.get("/console/providers", response_class=HTMLResponse)
def console_providers() -> HTMLResponse:
    return _render_console_providers()


@app.get("/console/review", response_class=HTMLResponse)
def console_review() -> HTMLResponse:
    return _render_console_review()


@app.get("/console/settings", response_class=HTMLResponse)
def console_settings() -> HTMLResponse:
    return _render_console_settings()


@app.get("/console/docs", response_class=HTMLResponse)
def console_docs() -> HTMLResponse:
    return _render_console_docs()


@app.get("/api/dashboard")
def console_dashboard_json(limit: int = Query(default=5, ge=1, le=50)) -> dict[str, Any]:
    return _dashboard_payload(limit=limit)


@app.get("/api/console/dashboard")
def console_dashboard_json_alias(limit: int = Query(default=5, ge=1, le=50)) -> dict[str, Any]:
    return _dashboard_payload(limit=limit)


@app.get("/api/console/workflows")
def console_workflows_json() -> dict[str, Any]:
    return {
        "workflows": [_workflow_payload()],
        "cli": {"list": "llm-platform demo --verbose"},
    }


@app.get("/api/console/workflows/{workflow_id}")
def console_workflow_json(workflow_id: str) -> dict[str, Any]:
    workflow = _workflow_payload(workflow_id)
    return {"workflow": workflow, "cli": workflow["cli"]}


@app.post("/api/console/workflows/{workflow_id}/run")
def console_workflow_run_json(
    workflow_id: str,
    run_request: ConsoleWorkflowRunRequest | None = None,
) -> dict[str, Any]:
    _workflow_payload(workflow_id)
    run_request = run_request or ConsoleWorkflowRunRequest()
    demo_classifier = TicketClassifier(
        provider=MockProvider(),
        model="mock-ticket-classifier",
        trace_store=trace_store,
        idempotency_store=idempotency_store,
        provider_timeout_seconds=settings.provider_timeout_seconds,
        provider_max_retries=settings.provider_max_retries,
        provider_rate_limit_requests=settings.provider_rate_limit_requests,
        provider_rate_limit_window_seconds=settings.provider_rate_limit_window_seconds,
    )
    result = demo_classifier.classify(
        TicketRequest(
            subject=run_request.subject,
            body=run_request.body,
            session_id=run_request.session_id,
            idempotency_key=run_request.idempotency_key or f"console-api-{uuid.uuid4()}",
        )
    )
    traces = trace_store.list_by_session_id(run_request.session_id, limit=500)
    trace = traces[-1]
    return {
        "workflow_id": workflow_id,
        "message": "Mock-mode workflow run completed without live provider credentials.",
        "input": run_request.model_dump(mode="json"),
        "result": result.model_dump(mode="json"),
        "trace": _trace_payload(trace),
        "cli": {
            "equivalent_run": (
                f'llm-platform classify --subject "{run_request.subject}" '
                f'--body "{run_request.body}" --session-id {run_request.session_id} '
                f"{_trace_db_arg()}"
            ),
            "trace": f"llm-platform trace show {trace['request_id']} {_trace_db_arg()}",
            "session": f"llm-platform session show {run_request.session_id} {_trace_db_arg()}",
        },
    }


@app.get("/api/console/runs")
def console_runs_json(limit: int = Query(default=50, ge=1, le=500)) -> dict[str, Any]:
    return {
        "runs": _session_run_summaries(limit=limit),
        "cli": {"show": f"llm-platform session show <session_id> {_trace_db_arg()}"},
    }


@app.get("/api/console/runs/{session_id}")
def console_run_json(
    session_id: str,
    status: str = Query(default="all"),
    limit: int = Query(default=50, ge=1, le=500),
) -> dict[str, Any]:
    payload = _session_history_payload(session_id=session_id, status=status, limit=limit)
    return {
        **payload,
        "cli": {
            "show": f"llm-platform session show {session_id} {_trace_db_arg()} --limit {limit}",
            "traces": f"llm-platform trace list {_trace_db_arg()} --limit {limit}",
        },
        "links": {"ui": f"/sessions/{session_id}"},
    }


@app.get("/api/console/traces")
def console_traces_json(limit: int = Query(default=25, ge=1, le=500)) -> dict[str, Any]:
    return {
        "traces": [_trace_payload(trace) for trace in trace_store.list_recent(limit=limit)],
        "cli": {"list": f"llm-platform trace list {_trace_db_arg()} --limit {limit}"},
    }


@app.get("/api/console/traces/{request_id}")
def console_trace_json(request_id: str) -> dict[str, Any]:
    trace = trace_store.get_by_request_id(request_id)
    if trace is None:
        raise HTTPException(status_code=404, detail=f"Trace not found: {request_id}")
    payload = _trace_payload(trace)
    return {"trace": payload, "cli": payload["cli"]}


@app.get("/api/console/evals")
def console_evals_json(limit: int = Query(default=25, ge=1, le=500)) -> dict[str, Any]:
    return {
        "eval_runs": [_eval_run_payload(run) for run in eval_store.list_runs(limit=limit)],
        "cli": {
            "run": f"llm-platform eval run {_trace_db_arg()} --session-id console-api-eval",
            "list": f"llm-platform eval list {_trace_db_arg()}",
        },
    }


@app.post("/api/console/evals/run")
def console_eval_run_json(eval_request: ConsoleEvalRunRequest | None = None) -> dict[str, Any]:
    eval_request = eval_request or ConsoleEvalRunRequest()
    report = run_ticket_classification_eval(
        provider=MockProvider(),
        model="mock-ticket-classifier",
        session_id=eval_request.session_id,
        prompt_version=eval_request.prompt_version,
        eval_store=eval_store,
        trace_store=trace_store,
        timeout_seconds=settings.provider_timeout_seconds,
        max_retries=settings.provider_max_retries,
    )
    return {
        "message": "Mock-mode eval completed without live provider credentials.",
        "eval_run": report,
        "traces": [
            _trace_payload(trace)
            for trace in trace_store.list_by_eval_run_id(report["eval_run_id"])
        ],
        "cli": {
            "run": (
                f"llm-platform eval run {_trace_db_arg()} "
                f"--session-id {eval_request.session_id}"
            ),
            "show": f"llm-platform eval show {report['eval_run_id']} {_trace_db_arg()}",
        },
    }


@app.get("/api/console/evals/{eval_run_id}")
def console_eval_json(eval_run_id: str) -> dict[str, Any]:
    run = eval_store.get_run(eval_run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Eval run not found: {eval_run_id}")
    eval_run = _eval_run_payload(run)
    return {
        "eval_run": eval_run,
        "traces": [_trace_payload(trace) for trace in trace_store.list_by_eval_run_id(eval_run_id)],
        "cli": eval_run["cli"],
    }


@app.get("/api/console/prompts")
def console_prompts_json() -> dict[str, Any]:
    return {
        "prompts": [
            _prompt_payload(prompt.prompt_id)
            for prompt in PromptRegistry().list()
        ],
        "cli": {"list": "llm-platform prompts list"},
    }


@app.get("/api/console/prompts/{prompt_id}")
def console_prompt_json(
    prompt_id: str,
    version: int | None = Query(default=None),
) -> dict[str, Any]:
    prompt = _prompt_payload(prompt_id, version=version)
    return {"prompt": prompt, "cli": prompt["cli"]}


@app.get("/api/console/providers")
def console_providers_json() -> dict[str, Any]:
    return {
        "providers": [_provider_payload(provider) for provider in ["mock", "openai", "custom"]],
        "active_provider": settings.provider,
        "cli": {"health": "llm-platform health"},
    }


@app.post("/api/console/providers/{provider_name}/test")
def console_provider_test_json(provider_name: str) -> dict[str, Any]:
    provider = _provider_payload(provider_name)
    return {
        "provider": provider,
        "test": {
            "status": "ready" if provider["ready"] else "not_configured",
            "live_call_performed": False,
            "message": (
                "Mock provider is ready for local demos."
                if provider_name == "mock"
                else "Configuration metadata checked; no live provider call was made."
            ),
        },
        "cli": {"health": "llm-platform health"},
    }


@app.get("/api/console/reviews")
def console_reviews_json(
    include_decided: bool = Query(default=False),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any]:
    return {
        **_review_queue_payload(limit=limit, include_decided=include_decided),
        "cli": {"traces": f"llm-platform trace list {_trace_db_arg()} --limit {limit}"},
        "links": {"ui": "/reviews"},
    }


@app.get("/api/console/settings")
def console_settings_json() -> dict[str, Any]:
    return _settings_payload()


@app.post("/classify-ticket")
def classify_ticket(
    ticket: TicketRequest,
    x_session_id: str | None = Header(default=None),
    idempotency_key: str | None = Header(default=None),
) -> TicketClassification:
    if classifier_startup_error is not None:
        raise classifier_startup_error
    if classifier is None:
        raise ProviderConfigurationError("Provider classifier is not configured.")
    if x_session_id and not ticket.session_id:
        ticket = ticket.model_copy(update={"session_id": x_session_id})
    if idempotency_key and not ticket.idempotency_key:
        ticket = ticket.model_copy(update={"idempotency_key": idempotency_key})
    return classifier.classify(ticket)


@app.get("/metrics")
def metrics() -> dict[str, Any]:
    return trace_store.metrics()


@app.get("/api/reviews")
def review_queue_json(
    include_decided: bool = Query(default=False),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any]:
    return _review_queue_payload(limit=limit, include_decided=include_decided)


@app.post("/api/reviews/{request_id}")
def review_decision_json(request_id: str, decision_request: ReviewDecisionRequest) -> dict[str, Any]:
    decision = _record_review_decision(
        request_id=request_id,
        decision=decision_request.decision,
        reviewer=decision_request.reviewer,
        notes=decision_request.notes,
    )
    return {
        "decision": decision,
        "downstream_blocked": decision["decision"] != "approved",
    }


@app.get("/reviews", response_class=HTMLResponse)
def review_queue_page(
    include_decided: bool = Query(default=False),
    limit: int = Query(default=100, ge=1, le=500),
) -> HTMLResponse:
    payload = _review_queue_payload(limit=limit, include_decided=include_decided)
    return HTMLResponse(
        _render_review_queue(payload, include_decided=include_decided, limit=limit)
    )


@app.post("/reviews/{request_id}")
async def review_decision_page(request_id: str, request: Request) -> RedirectResponse:
    form = parse_qs((await request.body()).decode("utf-8"))
    decision = form.get("decision", [""])[0]
    reviewer = form.get("reviewer", ["business-reviewer"])[0]
    notes = form.get("notes", [""])[0]
    _record_review_decision(
        request_id=request_id,
        decision=decision,
        reviewer=reviewer,
        notes=notes,
    )
    return RedirectResponse(url="/reviews?include_decided=true", status_code=303)


@app.get("/api/sessions/{session_id}")
def session_history_json(
    session_id: str,
    status: str = Query(default="all"),
    limit: int = Query(default=50, ge=1, le=500),
) -> dict[str, Any]:
    return _session_history_payload(session_id=session_id, status=status, limit=limit)


@app.get("/sessions/{session_id}", response_class=HTMLResponse)
def session_history_page(
    session_id: str,
    status: str = Query(default="all"),
    limit: int = Query(default=50, ge=1, le=500),
) -> HTMLResponse:
    payload = _session_history_payload(session_id=session_id, status=status, limit=limit)
    return HTMLResponse(_render_session_history(payload, limit=limit))


@app.get("/sessions/{session_id}/review/{request_id}", response_class=HTMLResponse)
def session_review_page(session_id: str, request_id: str) -> HTMLResponse:
    trace = trace_store.get_by_request_id(request_id)
    if trace is None or trace["session_id"] != session_id:
        raise _not_found(session_id)
    detail = session_trace_detail(trace)
    if not detail["reviewable"]:
        raise HTTPException(status_code=404, detail="Trace is not reviewable.")
    return HTMLResponse(_render_review_page(session_id, detail))
