from __future__ import annotations

from html import escape
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse

from llm_platform_starter.errors import GuardrailValidationError, describe_exception, session_not_found_error
from llm_platform_starter.examples.ticket_classifier import TicketClassifier
from llm_platform_starter.models import TicketClassification, TicketRequest
from llm_platform_starter.observability.idempotency import (
    IdempotencyInProgressError,
    IdempotencyStore,
)
from llm_platform_starter.observability.storage import TraceStore
from llm_platform_starter.providers.factory import ProviderConfigurationError, create_provider
from llm_platform_starter.providers.reliability import ProviderCallError
from llm_platform_starter.session_history import (
    build_session_history,
    session_trace_detail,
)
from llm_platform_starter.settings import load_settings

settings = load_settings()
trace_store = TraceStore(settings.trace_db_path)
idempotency_store = IdempotencyStore(settings.trace_db_path)
classifier: TicketClassifier | None = None
classifier_startup_error: ProviderConfigurationError | None = None


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
