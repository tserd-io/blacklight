from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from llm_platform_starter.models import TraceRecord


class TraceStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self._initialize()

    def insert(self, record: TraceRecord) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO traces (
                  request_id, session_id, eval_run_id, prompt_id, prompt_version,
                  provider, model, latency_ms, input_tokens, output_tokens,
                  estimated_cost_usd, validation_passed, error_category
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(request_id) DO UPDATE SET
                  session_id = excluded.session_id,
                  eval_run_id = excluded.eval_run_id,
                  prompt_id = excluded.prompt_id,
                  prompt_version = excluded.prompt_version,
                  provider = excluded.provider,
                  model = excluded.model,
                  latency_ms = excluded.latency_ms,
                  input_tokens = excluded.input_tokens,
                  output_tokens = excluded.output_tokens,
                  estimated_cost_usd = excluded.estimated_cost_usd,
                  validation_passed = excluded.validation_passed,
                  error_category = excluded.error_category
                """,
                (
                    record.request_id,
                    record.session_id,
                    record.eval_run_id,
                    record.prompt_id,
                    record.prompt_version,
                    record.provider,
                    record.model,
                    record.latency_ms,
                    record.input_tokens,
                    record.output_tokens,
                    record.estimated_cost_usd,
                    int(record.validation_passed),
                    record.error_category,
                ),
            )

    def metrics(self) -> dict[str, float | int]:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                """
                SELECT
                  COUNT(*),
                  COALESCE(AVG(latency_ms), 0),
                  COALESCE(SUM(estimated_cost_usd), 0),
                  COALESCE(AVG(CASE WHEN error_category IS NOT NULL THEN 1.0 ELSE 0.0 END), 0),
                  COALESCE(AVG(CASE WHEN validation_passed = 0 THEN 1.0 ELSE 0.0 END), 0)
                FROM traces
                """
            ).fetchone()
        return {
            "request_count": row[0],
            "avg_latency_ms": round(row[1], 2),
            "total_estimated_cost_usd": round(row[2], 8),
            "failure_rate": round(row[3], 4),
            "validation_failure_rate": round(row[4], 4),
            "by_provider": self._group_metrics(["provider"]),
            "by_model": self._group_metrics(["model"]),
            "by_provider_model": self._group_metrics(["provider", "model"]),
        }

    def list_recent(self, limit: int = 10) -> list[dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT
                  created_at, request_id, session_id, eval_run_id, prompt_id,
                  prompt_version, provider, model, latency_ms, input_tokens,
                  output_tokens, estimated_cost_usd, validation_passed, error_category
                FROM traces
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def get_by_request_id(self, request_id: str) -> dict[str, Any] | None:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT
                  created_at, request_id, session_id, eval_run_id, prompt_id,
                  prompt_version, provider, model, latency_ms, input_tokens,
                  output_tokens, estimated_cost_usd, validation_passed, error_category
                FROM traces
                WHERE request_id = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (request_id,),
            ).fetchone()
        return self._row_to_dict(row) if row else None

    def list_by_eval_run_id(self, eval_run_id: str) -> list[dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT
                  created_at, request_id, session_id, eval_run_id, prompt_id,
                  prompt_version, provider, model, latency_ms, input_tokens,
                  output_tokens, estimated_cost_usd, validation_passed, error_category
                FROM traces
                WHERE eval_run_id = ?
                ORDER BY id
                """,
                (eval_run_id,),
            ).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def list_by_session_id(self, session_id: str, limit: int = 50) -> list[dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT
                  created_at, request_id, session_id, eval_run_id, prompt_id,
                  prompt_version, provider, model, latency_ms, input_tokens,
                  output_tokens, estimated_cost_usd, validation_passed, error_category
                FROM traces
                WHERE session_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (session_id, limit),
            ).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def _initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS traces (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                  request_id TEXT NOT NULL,
                  session_id TEXT NOT NULL DEFAULT 'anonymous',
                  eval_run_id TEXT,
                  prompt_id TEXT NOT NULL,
                  prompt_version INTEGER NOT NULL,
                  provider TEXT NOT NULL,
                  model TEXT NOT NULL,
                  latency_ms REAL NOT NULL,
                  input_tokens INTEGER NOT NULL,
                  output_tokens INTEGER NOT NULL,
                  estimated_cost_usd REAL NOT NULL,
                  validation_passed INTEGER NOT NULL,
                  error_category TEXT
                )
                """
            )
            self._ensure_column(
                conn,
                table="traces",
                column="session_id",
                definition="TEXT NOT NULL DEFAULT 'anonymous'",
            )
            self._ensure_column(
                conn,
                table="traces",
                column="eval_run_id",
                definition="TEXT",
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_traces_eval_run_id
                ON traces(eval_run_id)
                """
            )
            self._dedupe_by_key(conn, table="traces", key_columns=["request_id"])
            conn.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_traces_request_id
                ON traces(request_id)
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

    def _group_metrics(self, columns: list[str]) -> list[dict[str, Any]]:
        select_columns = ", ".join(columns)
        group_columns = ", ".join(columns)
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                f"""
                SELECT
                  {select_columns},
                  COUNT(*) AS request_count,
                  COALESCE(AVG(latency_ms), 0) AS avg_latency_ms,
                  COALESCE(SUM(estimated_cost_usd), 0) AS total_estimated_cost_usd,
                  COALESCE(AVG(CASE WHEN error_category IS NOT NULL THEN 1.0 ELSE 0.0 END), 0)
                    AS failure_rate,
                  COALESCE(AVG(CASE WHEN validation_passed = 0 THEN 1.0 ELSE 0.0 END), 0)
                    AS validation_failure_rate
                FROM traces
                GROUP BY {group_columns}
                ORDER BY request_count DESC, {group_columns}
                """
            ).fetchall()
        return [self._metric_row_to_dict(row) for row in rows]

    @staticmethod
    def _ensure_column(
        conn: sqlite3.Connection,
        *,
        table: str,
        column: str,
        definition: str,
    ) -> None:
        columns = {
            row[1]
            for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
        }
        if column not in columns:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
        payload = dict(row)
        payload["validation_passed"] = bool(payload["validation_passed"])
        return payload

    @staticmethod
    def _metric_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
        payload = dict(row)
        payload["avg_latency_ms"] = round(payload["avg_latency_ms"], 2)
        payload["total_estimated_cost_usd"] = round(payload["total_estimated_cost_usd"], 8)
        payload["failure_rate"] = round(payload["failure_rate"], 4)
        payload["validation_failure_rate"] = round(payload["validation_failure_rate"], 4)
        return payload
