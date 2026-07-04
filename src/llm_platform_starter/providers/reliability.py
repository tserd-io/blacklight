from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError
from collections import deque
from threading import Lock
import time
import uuid
from collections.abc import Callable

from llm_platform_starter.models import ProviderRequest, ProviderResponse
from llm_platform_starter.providers.base import LLMProvider

IDEMPOTENCY_KEY_METADATA = "idempotency_key"


class ProviderCallError(RuntimeError):
    def __init__(self, message: str, category: str, attempts: int) -> None:
        super().__init__(message)
        self.category = category
        self.attempts = attempts


class ProviderEmptyResponseError(RuntimeError):
    pass


class SlidingWindowRateLimiter:
    def __init__(
        self,
        *,
        max_requests: int,
        window_seconds: float,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if max_requests < 1:
            raise ValueError("max_requests must be at least 1")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be greater than 0")
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.monotonic = monotonic
        self.sleep = sleep
        self._timestamps: deque[float] = deque()
        self._lock = Lock()

    def acquire(self) -> None:
        while True:
            with self._lock:
                now = self.monotonic()
                self._prune(now)
                if len(self._timestamps) < self.max_requests:
                    self._timestamps.append(now)
                    return
                wait_seconds = self.window_seconds - (now - self._timestamps[0])

            self.sleep(max(wait_seconds, 0))

    def _prune(self, now: float) -> None:
        while self._timestamps and now - self._timestamps[0] >= self.window_seconds:
            self._timestamps.popleft()


class KeyedRateLimiter:
    def __init__(
        self,
        *,
        max_requests: int,
        window_seconds: float,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.monotonic = monotonic
        self.sleep = sleep
        self._limiters: dict[str, SlidingWindowRateLimiter] = {}
        self._lock = Lock()

    def acquire(self, key: str) -> None:
        self.limiter_for(key).acquire()

    def limiter_for(self, key: str) -> SlidingWindowRateLimiter:
        with self._lock:
            if key not in self._limiters:
                self._limiters[key] = SlidingWindowRateLimiter(
                    max_requests=self.max_requests,
                    window_seconds=self.window_seconds,
                    monotonic=self.monotonic,
                    sleep=self.sleep,
                )
            return self._limiters[key]


def complete_with_retries(
    provider: LLMProvider,
    request: ProviderRequest,
    *,
    timeout_seconds: float,
    max_retries: int,
    rate_limiter: SlidingWindowRateLimiter | None = None,
) -> ProviderResponse:
    attempts = max_retries + 1
    last_error: BaseException | None = None
    last_category = "provider_error"
    idempotent_request = ensure_idempotency_key(request)

    for attempt in range(1, attempts + 1):
        try:
            if rate_limiter:
                rate_limiter.acquire()
            response = _complete_with_timeout(
                provider,
                idempotent_request,
                timeout_seconds=timeout_seconds,
            )
            _raise_for_empty_response(response)
            return response
        except TimeoutError as exc:
            last_error = exc
            last_category = "provider_timeout"
        except ProviderEmptyResponseError as exc:
            last_error = exc
            last_category = "provider_empty_response"
        except Exception as exc:
            last_error = exc
            last_category = "provider_error"

        if attempt == attempts:
            raise ProviderCallError(
                f"Provider call failed after {attempts} attempt(s): {last_error}",
                category=last_category,
                attempts=attempts,
            ) from last_error

    raise AssertionError("unreachable")


def ensure_idempotency_key(request: ProviderRequest) -> ProviderRequest:
    if request.metadata.get(IDEMPOTENCY_KEY_METADATA):
        return request
    key = request.metadata.get("request_id") or str(uuid.uuid4())
    return request.model_copy(
        update={
            "metadata": {
                **request.metadata,
                IDEMPOTENCY_KEY_METADATA: key,
            }
        }
    )


def _complete_with_timeout(
    provider: LLMProvider,
    request: ProviderRequest,
    *,
    timeout_seconds: float,
) -> ProviderResponse:
    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(provider.complete, request)
    try:
        return future.result(timeout=timeout_seconds)
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def _raise_for_empty_response(response: ProviderResponse) -> None:
    text = response.text
    if text is None or not str(text).strip():
        raise ProviderEmptyResponseError("Provider returned empty response text.")
