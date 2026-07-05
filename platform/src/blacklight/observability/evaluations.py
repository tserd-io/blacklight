from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


class EvalMetricStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self._initialize()

    def insert_report(self, report: dict[str, Any]) -> None:
        summary = report["summary"]
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute(
                """
                DELETE FROM eval_cases
                WHERE eval_run_id = ?
                """,
                (report["eval_run_id"],),
            )
            conn.execute(
                """
                INSERT INTO eval_runs (
                  eval_run_id, session_id, fixture_name, prompt_id, prompt_version,
                  provider, model, case_count, accuracy, schema_validity_rate,
                  needs_review_rate, average_latency_ms, latency_p50_ms,
                  latency_p95_ms, total_input_tokens, total_output_tokens,
                  total_tokens, total_estimated_cost_usd, total_retries,
                  average_retries_per_case, error_rate, summary_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(eval_run_id) DO UPDATE SET
                  session_id = excluded.session_id,
                  fixture_name = excluded.fixture_name,
                  prompt_id = excluded.prompt_id,
                  prompt_version = excluded.prompt_version,
                  provider = excluded.provider,
                  model = excluded.model,
                  case_count = excluded.case_count,
                  accuracy = excluded.accuracy,
                  schema_validity_rate = excluded.schema_validity_rate,
                  needs_review_rate = excluded.needs_review_rate,
                  average_latency_ms = excluded.average_latency_ms,
                  latency_p50_ms = excluded.latency_p50_ms,
                  latency_p95_ms = excluded.latency_p95_ms,
                  total_input_tokens = excluded.total_input_tokens,
                  total_output_tokens = excluded.total_output_tokens,
                  total_tokens = excluded.total_tokens,
                  total_estimated_cost_usd = excluded.total_estimated_cost_usd,
                  total_retries = excluded.total_retries,
                  average_retries_per_case = excluded.average_retries_per_case,
                  error_rate = excluded.error_rate,
                  summary_json = excluded.summary_json
                """,
                (
                    report["eval_run_id"],
                    report["session_id"],
                    report["fixture_name"],
                    report["prompt_id"],
                    report["prompt_version"],
                    report["provider"],
                    report["model"],
                    summary["case_count"],
                    summary["accuracy"],
                    summary["schema_validity_rate"],
                    summary["needs_review_rate"],
                    summary["average_latency_ms"],
                    summary["latency_p50_ms"],
                    summary["latency_p95_ms"],
                    summary["total_input_tokens"],
                    summary["total_output_tokens"],
                    summary["total_tokens"],
                    summary["total_estimated_cost_usd"],
                    summary["total_retries"],
                    summary["average_retries_per_case"],
                    summary["error_rate"],
                    json.dumps(summary, sort_keys=True),
                ),
            )
            conn.executemany(
                """
                INSERT INTO eval_cases (
                  eval_run_id, session_id, case_id, trace_request_id,
                  expected_category, actual_category, passed, schema_valid,
                  needs_review, latency_ms, input_tokens, output_tokens,
                  total_tokens, estimated_cost_usd, retry_count, error_category,
                  case_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(eval_run_id, case_id) DO UPDATE SET
                  session_id = excluded.session_id,
                  trace_request_id = excluded.trace_request_id,
                  expected_category = excluded.expected_category,
                  actual_category = excluded.actual_category,
                  passed = excluded.passed,
                  schema_valid = excluded.schema_valid,
                  needs_review = excluded.needs_review,
                  latency_ms = excluded.latency_ms,
                  input_tokens = excluded.input_tokens,
                  output_tokens = excluded.output_tokens,
                  total_tokens = excluded.total_tokens,
                  estimated_cost_usd = excluded.estimated_cost_usd,
                  retry_count = excluded.retry_count,
                  error_category = excluded.error_category,
                  case_json = excluded.case_json
                """,
                [
                    (
                        report["eval_run_id"],
                        report["session_id"],
                        case["id"],
                        case["trace_request_id"],
                        case["expected_category"],
                        case["actual_category"],
                        int(case["passed"]),
                        int(case["schema_valid"]),
                        int(case["needs_review"]),
                        case["latency_ms"],
                        case["input_tokens"],
                        case["output_tokens"],
                        case["total_tokens"],
                        case["estimated_cost_usd"],
                        case["retry_count"],
                        case["error_category"],
                        json.dumps(case, sort_keys=True),
                    )
                    for case in report["cases"]
                ],
            )

    def list_runs(self, limit: int = 10) -> list[dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT
                  created_at, eval_run_id, session_id, fixture_name, prompt_id,
                  prompt_version, provider, model, case_count, accuracy,
                  schema_validity_rate, needs_review_rate, average_latency_ms,
                  latency_p50_ms, latency_p95_ms, total_input_tokens,
                  total_output_tokens, total_tokens, total_estimated_cost_usd,
                  total_retries, average_retries_per_case, error_rate
                FROM eval_runs
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_run(self, eval_run_id: str) -> dict[str, Any] | None:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT
                  eval_run_id, session_id, fixture_name, prompt_id, prompt_version,
                  provider, model, summary_json
                FROM eval_runs
                WHERE eval_run_id = ?
                """,
                (eval_run_id,),
            ).fetchone()
            if not row:
                return None
        return {
            "eval_run_id": row["eval_run_id"],
            "session_id": row["session_id"],
            "fixture_name": row["fixture_name"],
            "prompt_id": row["prompt_id"],
            "prompt_version": row["prompt_version"],
            "provider": row["provider"],
            "model": row["model"],
            "summary": json.loads(row["summary_json"]),
            "cases": self.list_cases(eval_run_id),
        }

    def list_cases(self, eval_run_id: str) -> list[dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            case_rows = conn.execute(
                """
                SELECT case_json
                FROM eval_cases
                WHERE eval_run_id = ?
                ORDER BY id
                """,
                (eval_run_id,),
            ).fetchall()
        return [json.loads(case["case_json"]) for case in case_rows]

    def _initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS eval_runs (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                  eval_run_id TEXT NOT NULL UNIQUE,
                  session_id TEXT NOT NULL,
                  fixture_name TEXT NOT NULL,
                  prompt_id TEXT NOT NULL,
                  prompt_version INTEGER NOT NULL,
                  provider TEXT NOT NULL,
                  model TEXT NOT NULL,
                  case_count INTEGER NOT NULL,
                  accuracy REAL NOT NULL,
                  schema_validity_rate REAL NOT NULL,
                  needs_review_rate REAL NOT NULL,
                  average_latency_ms REAL NOT NULL,
                  latency_p50_ms REAL NOT NULL,
                  latency_p95_ms REAL NOT NULL,
                  total_input_tokens INTEGER NOT NULL,
                  total_output_tokens INTEGER NOT NULL,
                  total_tokens INTEGER NOT NULL,
                  total_estimated_cost_usd REAL NOT NULL,
                  total_retries INTEGER NOT NULL,
                  average_retries_per_case REAL NOT NULL,
                  error_rate REAL NOT NULL,
                  summary_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS eval_cases (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                  eval_run_id TEXT NOT NULL,
                  session_id TEXT NOT NULL,
                  case_id TEXT NOT NULL,
                  trace_request_id TEXT NOT NULL,
                  expected_category TEXT NOT NULL,
                  actual_category TEXT,
                  passed INTEGER NOT NULL,
                  schema_valid INTEGER NOT NULL,
                  needs_review INTEGER NOT NULL,
                  latency_ms REAL NOT NULL,
                  input_tokens INTEGER NOT NULL,
                  output_tokens INTEGER NOT NULL,
                  total_tokens INTEGER NOT NULL,
                  estimated_cost_usd REAL NOT NULL,
                  retry_count INTEGER NOT NULL,
                  error_category TEXT,
                  case_json TEXT NOT NULL,
                  UNIQUE(eval_run_id, case_id),
                  UNIQUE(trace_request_id),
                  FOREIGN KEY(eval_run_id) REFERENCES eval_runs(eval_run_id)
                )
                """
            )
            self._dedupe_by_key(
                conn,
                table="eval_cases",
                key_columns=["eval_run_id", "case_id"],
            )
            self._dedupe_by_key(
                conn,
                table="eval_cases",
                key_columns=["trace_request_id"],
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_eval_runs_session_id
                ON eval_runs(session_id)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_eval_cases_session_id
                ON eval_cases(session_id)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_eval_cases_trace_request_id
                ON eval_cases(trace_request_id)
                """
            )
            conn.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_eval_cases_run_case
                ON eval_cases(eval_run_id, case_id)
                """
            )
            conn.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_eval_cases_trace_request_id_unique
                ON eval_cases(trace_request_id)
                """
            )

    @staticmethod
    def _dedupe_by_key(
        conn: sqlite3.Connection,
        *,
        table: str,
        key_columns: list[str],
    ) -> None:
        partition = ", ".join(key_columns)
        conn.execute(
            f"""
            DELETE FROM {table}
            WHERE id NOT IN (
              SELECT MAX(id)
              FROM {table}
              GROUP BY {partition}
            )
            """
        )
