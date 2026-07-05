from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

REVIEW_DECISIONS = {"approved", "rejected", "needs_more_info"}


class ReviewDecisionStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self._initialize()

    def upsert(
        self,
        *,
        request_id: str,
        session_id: str,
        decision: str,
        reviewer: str = "business-reviewer",
        notes: str = "",
    ) -> dict[str, Any]:
        if decision not in REVIEW_DECISIONS:
            expected = ", ".join(sorted(REVIEW_DECISIONS))
            raise ValueError(f"Unknown review decision: {decision}. Expected one of: {expected}.")
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute(
                """
                INSERT INTO review_decisions (
                  request_id, session_id, decision, reviewer, notes
                )
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(request_id) DO UPDATE SET
                  session_id = excluded.session_id,
                  decision = excluded.decision,
                  reviewer = excluded.reviewer,
                  notes = excluded.notes,
                  decided_at = CURRENT_TIMESTAMP
                """,
                (request_id, session_id, decision, reviewer, notes),
            )
            row = conn.execute(
                """
                SELECT request_id, session_id, decision, reviewer, notes, decided_at
                FROM review_decisions
                WHERE request_id = ?
                """,
                (request_id,),
            ).fetchone()
        return dict(row)

    def get(self, request_id: str) -> dict[str, Any] | None:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT request_id, session_id, decision, reviewer, notes, decided_at
                FROM review_decisions
                WHERE request_id = ?
                """,
                (request_id,),
            ).fetchone()
        return dict(row) if row else None

    def list_recent(self, limit: int = 50) -> list[dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT request_id, session_id, decision, reviewer, notes, decided_at
                FROM review_decisions
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def _initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS review_decisions (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  request_id TEXT NOT NULL,
                  session_id TEXT NOT NULL,
                  decision TEXT NOT NULL,
                  reviewer TEXT NOT NULL DEFAULT 'business-reviewer',
                  notes TEXT NOT NULL DEFAULT '',
                  decided_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_review_decisions_request_id
                ON review_decisions(request_id)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_review_decisions_session_id
                ON review_decisions(session_id)
                """
            )
