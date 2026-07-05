import importlib

from fastapi.testclient import TestClient

from llm_platform_starter import api
from llm_platform_starter.errors import GuardrailValidationError
from llm_platform_starter.models import GuardrailOutcome, TraceRecord
from llm_platform_starter.observability.storage import TraceStore
from llm_platform_starter.providers.factory import ProviderConfigurationError
from llm_platform_starter.providers.reliability import ProviderCallError


class ValidationFailureClassifier:
    def classify(self, _ticket):
        raise GuardrailValidationError("missing required field: category")


class ProviderFailureClassifier:
    def classify(self, _ticket):
        raise ProviderCallError(
            "Provider call failed after 3 attempt(s): timed out",
            category="provider_timeout",
            attempts=3,
        )


def test_metrics_endpoint_returns_expanded_trace_metrics(tmp_path):
    original_trace_store = api.trace_store
    store = TraceStore(tmp_path / "traces.sqlite3")
    store.insert(
        TraceRecord(
            request_id="request-1",
            session_id="session-a",
            prompt_id="ticket_classifier",
            prompt_version=1,
            provider="mock",
            model="mock-ticket-classifier",
            latency_ms=10,
            input_tokens=10,
            output_tokens=5,
            estimated_cost_usd=0.0,
            validation_passed=False,
            guardrail_outcome=GuardrailOutcome.rejected,
            error_category="validation_error",
        )
    )
    api.trace_store = store

    try:
        response = TestClient(api.app).get("/metrics")
    finally:
        api.trace_store = original_trace_store

    payload = response.json()

    assert response.status_code == 200
    assert payload["request_count"] == 1
    assert payload["failure_rate"] == 1.0
    assert payload["validation_failure_rate"] == 1.0
    assert payload["by_provider"][0]["provider"] == "mock"
    assert payload["by_model"][0]["model"] == "mock-ticket-classifier"
    assert payload["by_provider_model"][0]["provider"] == "mock"
    assert payload["by_guardrail_outcome"][0]["guardrail_outcome"] == "rejected"


def test_classify_endpoint_returns_structured_validation_errors():
    original_classifier = api.classifier
    original_startup_error = api.classifier_startup_error
    api.classifier = ValidationFailureClassifier()
    api.classifier_startup_error = None

    try:
        response = TestClient(api.app).post(
            "/classify-ticket",
            json={"subject": "Refund", "body": "Duplicate charge"},
        )
    finally:
        api.classifier = original_classifier
        api.classifier_startup_error = original_startup_error

    payload = response.json()

    assert response.status_code == 422
    assert payload["error"]["category"] == "validation_error"
    assert payload["error"]["message"] == "missing required field: category"
    assert "schema" in payload["error"]["likely_cause"]
    assert "provider output" in payload["error"]["next_step"]


def test_classify_endpoint_returns_structured_provider_errors():
    original_classifier = api.classifier
    original_startup_error = api.classifier_startup_error
    api.classifier = ProviderFailureClassifier()
    api.classifier_startup_error = None

    try:
        response = TestClient(api.app).post(
            "/classify-ticket",
            json={"subject": "Refund", "body": "Duplicate charge"},
        )
    finally:
        api.classifier = original_classifier
        api.classifier_startup_error = original_startup_error

    payload = response.json()

    assert response.status_code == 503
    assert payload["error"]["category"] == "provider_timeout"
    assert "Provider call failed" in payload["error"]["message"]
    assert "timeout" in payload["error"]["likely_cause"]
    assert "provider credentials" in payload["error"]["next_step"]


def test_classify_endpoint_returns_structured_configuration_errors():
    original_classifier = api.classifier
    original_startup_error = api.classifier_startup_error
    api.classifier = None
    api.classifier_startup_error = ProviderConfigurationError("OPENAI_API_KEY is required.")

    try:
        response = TestClient(api.app).post(
            "/classify-ticket",
            json={"subject": "Refund", "body": "Duplicate charge"},
        )
    finally:
        api.classifier = original_classifier
        api.classifier_startup_error = original_startup_error

    payload = response.json()

    assert response.status_code == 500
    assert payload["error"]["category"] == "configuration_error"
    assert payload["error"]["message"] == "OPENAI_API_KEY is required."
    assert "Provider settings" in payload["error"]["likely_cause"]
    assert "llm-platform health" in payload["error"]["next_step"]


def test_api_import_keeps_app_available_when_provider_configuration_fails(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    try:
        reloaded_api = importlib.reload(api)
        response = TestClient(reloaded_api.app).post(
            "/classify-ticket",
            json={"subject": "Refund", "body": "Duplicate charge"},
        )
    finally:
        monkeypatch.setenv("LLM_PROVIDER", "mock")
        importlib.reload(api)

    payload = response.json()

    assert response.status_code == 500
    assert payload["error"]["category"] == "configuration_error"
    assert "OPENAI_API_KEY" in payload["error"]["message"]
