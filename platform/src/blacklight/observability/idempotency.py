from __future__ import annotations

import sqlite3
from pathlib import Path

from blacklight.models import TicketClassification


class IdempotencyInProgressError(RuntimeError):
    pass


class IdempotencyStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self._initialize()

    def get_ticket_classification(self, key: str) -> TicketClassification | None:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                """
                SELECT response_json
                FROM idempotency_records
                WHERE idempotency_key = ? AND status = 'completed'
                """,
                (key,),
            ).fetchone()
        return TicketClassification.model_validate_json(row[0]) if row else None

    def claim(self, key: str, request_fingerprint: str) -> bool:
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO idempotency_records (
                      idempotency_key, request_fingerprint, status
                    )
                    VALUES (?, ?, 'in_progress')
                    """,
                    (key, request_fingerprint),
                )
            return True
        except sqlite3.IntegrityError:
            return False

    def status(self, key: str) -> str | None:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                """
                SELECT status
                FROM idempotency_records
                WHERE idempotency_key = ?
                """,
                (key,),
            ).fetchone()
        return row[0] if row else None

    def complete_ticket_classification(
        self,
        key: str,
        result: TicketClassification,
    ) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                UPDATE idempotency_records
                SET status = 'completed',
                    response_json = ?,
                    completed_at = CURRENT_TIMESTAMP
                WHERE idempotency_key = ?
                """,
                (result.model_dump_json(), key),
            )

    def fail(self, key: str) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                DELETE FROM idempotency_records
                WHERE idempotency_key = ? AND status = 'in_progress'
                """,
                (key,),
            )

    def _initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS idempotency_records (
                  idempotency_key TEXT PRIMARY KEY,
                  request_fingerprint TEXT NOT NULL,
                  status TEXT NOT NULL,
                  response_json TEXT,
                  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                  completed_at TEXT
                )
                """
            )
