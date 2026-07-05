from __future__ import annotations

import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator


@dataclass(frozen=True)
class TraceTimer:
    request_id: str
    latency_ms: float


@contextmanager
def trace_timer(request_id: str | None = None) -> Iterator[dict[str, str]]:
    context = {"request_id": request_id or str(uuid.uuid4())}
    started = time.perf_counter()
    yield context
    context["latency_ms"] = str(round((time.perf_counter() - started) * 1000, 2))
