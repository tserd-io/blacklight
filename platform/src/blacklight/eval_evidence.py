from __future__ import annotations

from pathlib import Path
from typing import Any

from blacklight.prompts.registry import PromptRegistry


def build_eval_evidence(
    trace: dict[str, Any],
    *,
    agent_id: str | None = None,
    workflow_id: str | None = None,
    trace_db_path: str | Path | None = None,
) -> dict[str, Any]:
    prompt_id = trace["prompt_id"]
    prompt_version = trace["prompt_version"]
    eval_run_id = trace["eval_run_id"]
    fixture_name = _fixture_name(prompt_id, prompt_version)
    case_id = _case_id(trace["request_id"], eval_run_id)
    evidence = {
        "linked": eval_run_id is not None,
        "coverage": "specific_eval_run" if eval_run_id else "known_public_safe_suite",
        "suite_id": f"{prompt_id}:{fixture_name}",
        "suite_name": _suite_name(prompt_id, fixture_name),
        "fixture_name": fixture_name,
        "prompt_id": prompt_id,
        "prompt_version": prompt_version,
        "agent_id": agent_id,
        "workflow_id": workflow_id,
        "eval_run_id": eval_run_id,
        "case_id": case_id,
        "trace_request_id": trace["request_id"],
        "links": {
            "run_suite_api": "/api/console/evals/run",
            "evals_api": "/api/console/evals",
            "eval_console": "/console/evals",
        },
        "cli_commands": {
            "run_suite": _eval_run_command(trace_db_path),
        },
    }
    if eval_run_id:
        evidence["links"]["eval_api"] = f"/api/console/evals/{eval_run_id}"
        evidence["cli_commands"]["show_eval"] = _eval_show_command(eval_run_id, trace_db_path)
    return evidence


def _fixture_name(prompt_id: str, prompt_version: int) -> str:
    try:
        prompt = PromptRegistry().get(prompt_id, version=prompt_version)
    except ValueError:
        return "unknown"
    return prompt.eval_fixture or "ticket_classification.jsonl"


def _suite_name(prompt_id: str, fixture_name: str) -> str:
    readable_prompt = prompt_id.replace("_", " ")
    readable_fixture = fixture_name.removesuffix(".jsonl").replace("_", " ")
    return f"{readable_prompt.title()} public-safe fixture suite ({readable_fixture})"


def _case_id(request_id: str, eval_run_id: str | None) -> str | None:
    if not eval_run_id:
        return None
    prefix = f"{eval_run_id}:"
    if request_id.startswith(prefix):
        return request_id.removeprefix(prefix)
    return None


def _eval_run_command(trace_db_path: str | Path | None) -> str:
    command = "blacklight eval run"
    if trace_db_path:
        command = f"{command} --trace-db-path {trace_db_path}"
    return command


def _eval_show_command(eval_run_id: str, trace_db_path: str | Path | None) -> str:
    command = f"blacklight eval show {eval_run_id}"
    if trace_db_path:
        command = f"{command} --trace-db-path {trace_db_path}"
    return command
