from __future__ import annotations


class SDKNotFoundError(ValueError):
    """Raised when an SDK lookup target is not present in the configured store."""
