from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


class AgentRunStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self._initialize()

    def insert(self, envelope: dict[str, Any]) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO agent_runs (
                  agent_run_id, session_id, trace_request_id, agent_id,
                  agent_version, workflow_id, run_status, review_state,
                  guardrail_outcome, review_reason, envelope_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(agent_run_id) DO UPDATE SET
                  session_id = excluded.session_id,
                  trace_request_id = excluded.trace_request_id,
                  agent_id = excluded.agent_id,
                  agent_version = excluded.agent_version,
                  workflow_id = excluded.workflow_id,
                  run_status = excluded.run_status,
                  review_state = excluded.review_state,
                  guardrail_outcome = excluded.guardrail_outcome,
                  review_reason = excluded.review_reason,
                  envelope_json = excluded.envelope_json
                """,
                (
                    envelope["agent_run_id"],
                    envelope["session_id"],
                    envelope["trace_request_id"],
                    envelope["agent_id"],
                    envelope["agent_version"],
                    envelope["workflow_id"],
                    envelope["run_status"],
                    envelope["review"]["state"],
                    envelope["guardrail"]["outcome"],
                    envelope["review"]["reason"],
                    json.dumps(envelope, sort_keys=True),
                ),
            )

    def get(self, agent_run_id: str) -> dict[str, Any] | None:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT envelope_json
                FROM agent_runs
                WHERE agent_run_id = ?
                """,
                (agent_run_id,),
            ).fetchone()
        return json.loads(row["envelope_json"]) if row else None

    def list_recent(self, limit: int = 10) -> list[dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT
                  created_at, agent_run_id, session_id, trace_request_id,
                  agent_id, agent_version, workflow_id, run_status,
                  review_state, guardrail_outcome, review_reason
                FROM agent_runs
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_by_session_id(self, session_id: str, limit: int = 50) -> list[dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT
                  created_at, agent_run_id, session_id, trace_request_id,
                  agent_id, agent_version, workflow_id, run_status,
                  review_state, guardrail_outcome, review_reason
                FROM agent_runs
                WHERE session_id = ?
                ORDER BY id ASC
                LIMIT ?
                """,
                (session_id, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def _initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_runs (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                  agent_run_id TEXT NOT NULL UNIQUE,
                  session_id TEXT NOT NULL,
                  trace_request_id TEXT NOT NULL,
                  agent_id TEXT NOT NULL,
                  agent_version INTEGER NOT NULL,
                  workflow_id TEXT NOT NULL,
                  run_status TEXT NOT NULL,
                  review_state TEXT NOT NULL,
                  guardrail_outcome TEXT NOT NULL,
                  review_reason TEXT NOT NULL DEFAULT '',
                  envelope_json TEXT NOT NULL
                )
                """
            )
            self._ensure_column(
                conn,
                table="agent_runs",
                column="review_reason",
                definition="TEXT NOT NULL DEFAULT ''",
            )
            conn.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_agent_runs_agent_run_id
                ON agent_runs(agent_run_id)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_agent_runs_session_id
                ON agent_runs(session_id)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_agent_runs_trace_request_id
                ON agent_runs(trace_request_id)
                """
            )

    @staticmethod
    def _ensure_column(
        conn: sqlite3.Connection,
        *,
        table: str,
        column: str,
        definition: str,
    ) -> None:
        columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        if column not in columns:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
