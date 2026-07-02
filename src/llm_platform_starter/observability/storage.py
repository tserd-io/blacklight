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
                  request_id, prompt_id, prompt_version, provider, model, latency_ms,
                  input_tokens, output_tokens, estimated_cost_usd, validation_passed,
                  error_category
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.request_id,
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
                  COALESCE(AVG(CASE WHEN validation_passed = 0 THEN 1.0 ELSE 0.0 END), 0)
                FROM traces
                """
            ).fetchone()
        return {
            "request_count": row[0],
            "avg_latency_ms": round(row[1], 2),
            "total_estimated_cost_usd": round(row[2], 8),
            "validation_failure_rate": round(row[3], 4),
        }

    def list_recent(self, limit: int = 10) -> list[dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT
                  created_at, request_id, prompt_id, prompt_version, provider, model,
                  latency_ms, input_tokens, output_tokens, estimated_cost_usd,
                  validation_passed, error_category
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
                  created_at, request_id, prompt_id, prompt_version, provider, model,
                  latency_ms, input_tokens, output_tokens, estimated_cost_usd,
                  validation_passed, error_category
                FROM traces
                WHERE request_id = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (request_id,),
            ).fetchone()
        return self._row_to_dict(row) if row else None

    def _initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS traces (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                  request_id TEXT NOT NULL,
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

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
        payload = dict(row)
        payload["validation_passed"] = bool(payload["validation_passed"])
        return payload
