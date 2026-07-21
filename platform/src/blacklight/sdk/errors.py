from __future__ import annotations

from typing import Self

from pydantic import BaseModel

from blacklight.errors import ErrorDetail


class SDKNotFoundError(ValueError):
    """Raised when an SDK lookup target is not present in the configured store."""


class TypedError(BaseModel):
    category: str
    message: str
    likely_cause: str
    next_step: str

    @classmethod
    def from_detail(cls, detail: ErrorDetail) -> Self:
        return cls(
            category=detail.category,
            message=detail.message,
            likely_cause=detail.likely_cause,
            next_step=detail.next_step,
        )


def storage_error_detail(exc: Exception) -> ErrorDetail:
    return ErrorDetail(
        category="storage_error",
        message=str(exc) or exc.__class__.__name__,
        likely_cause="Blacklight could not open or write to the configured trace database.",
        next_step="Check TRACE_DB_PATH, directory permissions, and whether another process is holding the SQLite database open.",
    )
