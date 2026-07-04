import json
import time

import pytest

from llm_platform_starter.examples.ticket_classifier import TicketClassifier
from llm_platform_starter.models import ProviderRequest, ProviderResponse, TicketRequest
from llm_platform_starter.observability.idempotency import (
    IdempotencyInProgressError,
    IdempotencyStore,
)
from llm_platform_starter.observability.storage import TraceStore
from llm_platform_starter.providers.base import LLMProvider
from llm_platform_starter.providers.reliability import (
    IDEMPOTENCY_KEY_METADATA,
    KeyedRateLimiter,
    ProviderCallError,
    complete_with_retries,
)


def ticket_payload(category: str = "billing") -> str:
    return json.dumps(
        {
            "category": category,
            "severity": "medium",
            "confidence": 0.9,
            "rationale": "Fixture response.",
            "needs_review": False,
        }
    )


class FailsThenSucceedsProvider(LLMProvider):
    name = "fails-then-succeeds"

    def __init__(self) -> None:
        self.calls = 0
        self.idempotency_keys: list[str] = []

    def complete(self, request: ProviderRequest) -> ProviderResponse:
        self.calls += 1
        self.idempotency_keys.append(request.metadata[IDEMPOTENCY_KEY_METADATA])
        if self.calls == 1:
            raise RuntimeError("temporary provider failure")
        return ProviderResponse(
            text=ticket_payload(),
            provider=self.name,
            model=request.model,
        )


class AlwaysFailsProvider(LLMProvider):
    name = "always-fails"

    def __init__(self) -> None:
        self.calls = 0

    def complete(self, request: ProviderRequest) -> ProviderResponse:
        self.calls += 1
        raise RuntimeError("provider unavailable")


class EmptyThenSucceedsProvider(LLMProvider):
    name = "empty-then-succeeds"

    def __init__(self, first_text: str | None = "") -> None:
        self.calls = 0
        self.first_text = first_text

    def complete(self, request: ProviderRequest) -> ProviderResponse:
        self.calls += 1
        if self.calls == 1:
            if self.first_text is None:
                return ProviderResponse.model_construct(
                    text=None,
                    provider=self.name,
                    model=request.model,
                    input_tokens=0,
                    output_tokens=0,
                    cost_usd=0.0,
                    latency_ms=0,
                    metadata={},
                )
            return ProviderResponse(
                text=self.first_text,
                provider=self.name,
                model=request.model,
            )
        return ProviderResponse(
            text=ticket_payload(),
            provider=self.name,
            model=request.model,
        )


class AlwaysEmptyProvider(LLMProvider):
    name = "always-empty"

    def __init__(self) -> None:
        self.calls = 0

    def complete(self, request: ProviderRequest) -> ProviderResponse:
        self.calls += 1
        return ProviderResponse(
            text="   ",
            provider=self.name,
            model=request.model,
        )


class SlowProvider(LLMProvider):
    name = "slow-provider"

    def __init__(self) -> None:
        self.calls = 0

    def complete(self, request: ProviderRequest) -> ProviderResponse:
        self.calls += 1
        time.sleep(0.05)
        return ProviderResponse(
            text=ticket_payload(),
            provider=self.name,
            model=request.model,
        )


class CountingProvider(LLMProvider):
    name = "counting-provider"

    def __init__(self, category: str = "billing") -> None:
        self.calls = 0
        self.category = category

    def complete(self, request: ProviderRequest) -> ProviderResponse:
        self.calls += 1
        return ProviderResponse(
            text=ticket_payload(category=self.category),
            provider=self.name,
            model=request.model,
        )


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def test_provider_call_retries_transient_failure():
    provider = FailsThenSucceedsProvider()

    response = complete_with_retries(
        provider,
        ProviderRequest(prompt="Refund", model="test-model"),
        timeout_seconds=1,
        max_retries=1,
    )

    assert provider.calls == 2
    assert response.provider == "fails-then-succeeds"
    assert len(set(provider.idempotency_keys)) == 1


def test_provider_call_reuses_request_id_as_idempotency_key():
    provider = FailsThenSucceedsProvider()

    complete_with_retries(
        provider,
        ProviderRequest(
            prompt="Refund",
            model="test-model",
            metadata={"request_id": "request-123"},
        ),
        timeout_seconds=1,
        max_retries=1,
    )

    assert provider.idempotency_keys == ["request-123", "request-123"]


def test_rate_limiter_waits_after_session_limit_is_reached():
    clock = FakeClock()
    limiter = KeyedRateLimiter(
        max_requests=3,
        window_seconds=10,
        monotonic=clock.monotonic,
        sleep=clock.sleep,
    )

    limiter.acquire("user-1")
    limiter.acquire("user-1")
    limiter.acquire("user-1")
    limiter.acquire("user-1")

    assert clock.sleeps == [10]


def test_rate_limiter_isolated_by_session_id():
    clock = FakeClock()
    limiter = KeyedRateLimiter(
        max_requests=3,
        window_seconds=10,
        monotonic=clock.monotonic,
        sleep=clock.sleep,
    )

    limiter.acquire("user-1")
    limiter.acquire("user-1")
    limiter.acquire("user-1")
    limiter.acquire("user-2")

    assert clock.sleeps == []


def test_provider_call_raises_after_retry_exhaustion():
    provider = AlwaysFailsProvider()

    with pytest.raises(ProviderCallError) as exc_info:
        complete_with_retries(
            provider,
            ProviderRequest(prompt="Refund", model="test-model"),
            timeout_seconds=1,
            max_retries=2,
        )

    assert provider.calls == 3
    assert exc_info.value.category == "provider_error"
    assert exc_info.value.attempts == 3


@pytest.mark.parametrize("first_text", ["", "   ", None])
def test_provider_call_retries_empty_response_text(first_text):
    provider = EmptyThenSucceedsProvider(first_text=first_text)

    response = complete_with_retries(
        provider,
        ProviderRequest(prompt="Refund", model="test-model"),
        timeout_seconds=1,
        max_retries=1,
    )

    assert provider.calls == 2
    assert response.text == ticket_payload()


def test_provider_call_raises_empty_response_category_after_retry_exhaustion():
    provider = AlwaysEmptyProvider()

    with pytest.raises(ProviderCallError) as exc_info:
        complete_with_retries(
            provider,
            ProviderRequest(prompt="Refund", model="test-model"),
            timeout_seconds=1,
            max_retries=2,
        )

    assert provider.calls == 3
    assert exc_info.value.category == "provider_empty_response"
    assert exc_info.value.attempts == 3


def test_ticket_classifier_traces_provider_failure_after_retry_exhaustion(tmp_path):
    store = TraceStore(tmp_path / "traces.sqlite3")
    provider = AlwaysFailsProvider()
    classifier = TicketClassifier(
        provider=provider,
        model="test-model",
        trace_store=store,
        provider_timeout_seconds=1,
        provider_max_retries=1,
    )

    with pytest.raises(ProviderCallError):
        classifier.classify(TicketRequest(subject="Refund", body="Duplicate charge."))

    traces = store.list_recent()

    assert provider.calls == 2
    assert traces[0]["provider"] == "always-fails"
    assert traces[0]["model"] == "test-model"
    assert traces[0]["validation_passed"] is False
    assert traces[0]["error_category"] == "provider_error"


def test_ticket_classifier_traces_empty_provider_output_after_retry_exhaustion(tmp_path):
    store = TraceStore(tmp_path / "traces.sqlite3")
    provider = AlwaysEmptyProvider()
    classifier = TicketClassifier(
        provider=provider,
        model="test-model",
        trace_store=store,
        provider_timeout_seconds=1,
        provider_max_retries=1,
    )

    with pytest.raises(ProviderCallError):
        classifier.classify(TicketRequest(subject="Refund", body="Duplicate charge."))

    traces = store.list_recent()

    assert provider.calls == 2
    assert traces[0]["provider"] == "always-empty"
    assert traces[0]["model"] == "test-model"
    assert traces[0]["validation_passed"] is False
    assert traces[0]["error_category"] == "provider_empty_response"


def test_ticket_classifier_traces_provider_timeout(tmp_path):
    store = TraceStore(tmp_path / "traces.sqlite3")
    classifier = TicketClassifier(
        provider=SlowProvider(),
        model="test-model",
        trace_store=store,
        provider_timeout_seconds=0.001,
        provider_max_retries=0,
    )

    with pytest.raises(ProviderCallError):
        classifier.classify(TicketRequest(subject="Refund", body="Duplicate charge."))

    traces = store.list_recent()

    assert traces[0]["provider"] == "slow-provider"
    assert traces[0]["error_category"] == "provider_timeout"


def test_ticket_classifier_applies_rate_limit_by_session_id():
    clock = FakeClock()
    limiter = KeyedRateLimiter(
        max_requests=3,
        window_seconds=10,
        monotonic=clock.monotonic,
        sleep=clock.sleep,
    )
    classifier = TicketClassifier(
        provider=FailsThenSucceedsProvider(),
        model="test-model",
        provider_timeout_seconds=1,
        provider_max_retries=0,
        provider_rate_limiter=limiter,
    )

    with pytest.raises(ProviderCallError):
        classifier.classify(TicketRequest(subject="Refund", body="Duplicate charge.", session_id="u1"))
    classifier.provider = FailsThenSucceedsProvider()
    with pytest.raises(ProviderCallError):
        classifier.classify(TicketRequest(subject="Refund", body="Duplicate charge.", session_id="u1"))
    classifier.provider = FailsThenSucceedsProvider()
    with pytest.raises(ProviderCallError):
        classifier.classify(TicketRequest(subject="Refund", body="Duplicate charge.", session_id="u1"))
    classifier.provider = FailsThenSucceedsProvider()
    with pytest.raises(ProviderCallError):
        classifier.classify(TicketRequest(subject="Refund", body="Duplicate charge.", session_id="u1"))

    assert clock.sleeps == [10]


def test_ticket_classifier_reuses_durable_idempotency_result_across_instances(tmp_path):
    db_path = tmp_path / "traces.sqlite3"
    idempotency_store = IdempotencyStore(db_path)
    first_provider = CountingProvider(category="billing")
    first_classifier = TicketClassifier(
        provider=first_provider,
        model="test-model",
        idempotency_store=idempotency_store,
    )

    first = first_classifier.classify(
        TicketRequest(
            subject="Refund",
            body="Duplicate charge.",
            session_id="session-a",
            idempotency_key="ticket-123",
        )
    )

    second_provider = CountingProvider(category="technical")
    second_classifier = TicketClassifier(
        provider=second_provider,
        model="test-model",
        idempotency_store=IdempotencyStore(db_path),
    )
    second = second_classifier.classify(
        TicketRequest(
            subject="Refund",
            body="Duplicate charge.",
            session_id="session-a",
            idempotency_key="ticket-123",
        )
    )

    assert first.category.value == "billing"
    assert second.category.value == "billing"
    assert first_provider.calls == 1
    assert second_provider.calls == 0


def test_ticket_classifier_rejects_duplicate_in_progress_idempotency_key(tmp_path):
    db_path = tmp_path / "traces.sqlite3"
    store = IdempotencyStore(db_path)
    store.claim("ticket-123", request_fingerprint="fingerprint")
    provider = CountingProvider()
    classifier = TicketClassifier(
        provider=provider,
        model="test-model",
        idempotency_store=store,
    )

    with pytest.raises(IdempotencyInProgressError):
        classifier.classify(
            TicketRequest(
                subject="Refund",
                body="Duplicate charge.",
                session_id="session-a",
                idempotency_key="ticket-123",
            )
        )

    assert provider.calls == 0
