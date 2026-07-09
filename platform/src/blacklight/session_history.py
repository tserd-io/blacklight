from __future__ import annotations

from typing import Any

SESSION_STATUS_FILTERS = {"all", "accepted", "needs_review", "rejected", "failed"}


def trace_detail(trace: dict[str, Any]) -> dict[str, Any]:
    return {
        "request_id": trace["request_id"],
        "session_id": trace["session_id"],
        "eval_run_id": trace["eval_run_id"],
        "agent_run_id": trace["agent_run_id"],
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


def trace_domain_to_range_detail(
    trace: dict[str, Any],
    envelope: dict[str, Any] | None = None,
) -> dict[str, Any]:
    detail = trace_detail(trace)
    if envelope is None:
        return {
            **detail,
            "domain_to_range": None,
        }
    return {
        **detail,
        "domain_to_range": {
            "agent_run": {
                "agent_run_id": envelope["agent_run_id"],
                "agent_id": envelope["agent_id"],
                "agent_version": envelope["agent_version"],
                "workflow_id": envelope["workflow_id"],
                "run_status": envelope["run_status"],
                "session_id": envelope["session_id"],
                "trace_request_id": envelope["trace_request_id"],
            },
            "domain": envelope["domain_snapshot"],
            "context": envelope["context_bundle"],
            "provider": envelope["provider_call"],
            "validation": envelope["validation"],
            "guardrails": envelope["guardrail"],
            "range": envelope["range_output"],
            "review": envelope["review"],
            "eval_evidence": envelope["eval_evidence"],
        },
    }


def trace_status(trace: dict[str, Any]) -> str:
    if trace["error_category"] is not None:
        return "failed"
    return trace["guardrail_outcome"]


def session_trace_detail(trace: dict[str, Any]) -> dict[str, Any]:
    detail = trace_detail(trace)
    status = trace_status(detail)
    return {
        **detail,
        "status": status,
        "review_outcome": detail["guardrail_outcome"],
        "failure_reason": detail["error_category"],
        "total_tokens": detail["input_tokens"] + detail["output_tokens"],
        "reviewable": status in {"needs_review", "rejected"},
    }


def summarize_session(traces: list[dict[str, Any]]) -> dict[str, Any]:
    request_count = len(traces)
    total_input_tokens = sum(trace["input_tokens"] for trace in traces)
    total_output_tokens = sum(trace["output_tokens"] for trace in traces)
    failure_count = sum(1 for trace in traces if trace["error_category"] is not None)
    review_count = sum(1 for trace in traces if trace["guardrail_outcome"] == "needs_review")
    validation_failure_count = sum(1 for trace in traces if not trace["validation_passed"])

    return {
        "request_count": request_count,
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "total_tokens": total_input_tokens + total_output_tokens,
        "total_estimated_cost_usd": round(
            sum(trace["estimated_cost_usd"] for trace in traces),
            8,
        ),
        "failure_count": failure_count,
        "failure_rate": round(failure_count / request_count, 4) if request_count else 0.0,
        "review_count": review_count,
        "validation_failure_count": validation_failure_count,
        "by_provider_model": group_session_traces(traces, ["provider", "model"]),
    }


def group_session_traces(traces: list[dict[str, Any]], keys: list[str]) -> list[dict[str, Any]]:
    groups: dict[tuple[Any, ...], dict[str, Any]] = {}
    for trace in traces:
        group_key = tuple(trace[key] for key in keys)
        group = groups.setdefault(
            group_key,
            {
                **{key: trace[key] for key in keys},
                "request_count": 0,
                "total_tokens": 0,
                "total_estimated_cost_usd": 0.0,
                "failure_count": 0,
                "review_count": 0,
            },
        )
        group["request_count"] += 1
        group["total_tokens"] += trace["input_tokens"] + trace["output_tokens"]
        group["total_estimated_cost_usd"] += trace["estimated_cost_usd"]
        if trace["error_category"] is not None:
            group["failure_count"] += 1
        if trace["guardrail_outcome"] == "needs_review":
            group["review_count"] += 1

    grouped = []
    for group in groups.values():
        request_count = group["request_count"]
        group["total_estimated_cost_usd"] = round(group["total_estimated_cost_usd"], 8)
        group["failure_rate"] = round(group["failure_count"] / request_count, 4)
        grouped.append(group)
    return sorted(grouped, key=lambda group: (-group["request_count"], group["provider"], group["model"]))


def filter_session_traces(
    traces: list[dict[str, Any]],
    status_filter: str,
) -> list[dict[str, Any]]:
    if status_filter not in SESSION_STATUS_FILTERS:
        expected = ", ".join(sorted(SESSION_STATUS_FILTERS))
        raise ValueError(f"Unknown session status filter: {status_filter}. Expected one of: {expected}.")
    if status_filter == "all":
        return traces
    return [trace for trace in traces if trace_status(trace) == status_filter]


def build_session_history(
    *,
    session_id: str,
    traces: list[dict[str, Any]],
    status_filter: str = "all",
) -> dict[str, Any]:
    trace_details = [session_trace_detail(trace) for trace in traces]
    filtered_traces = filter_session_traces(trace_details, status_filter)
    return {
        "session_id": session_id,
        "status_filter": status_filter,
        "summary": summarize_session(trace_details),
        "filtered_summary": summarize_session(filtered_traces),
        "traces": filtered_traces,
    }
