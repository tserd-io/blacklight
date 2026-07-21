from __future__ import annotations

from pathlib import Path
import sqlite3

import pytest

from blacklight.examples.ticket_classifier import TicketClassifier
from blacklight.models import ProviderRequest, ProviderResponse, TicketRequest
from blacklight.observability.agent_runs import AgentRunStore
from blacklight.observability.storage import TraceStore
from blacklight.providers.base import LLMProvider
from blacklight.providers.mock import MockProvider
from blacklight.sdk import agents as sdk_agents
from blacklight.sdk import client as sdk_client
from blacklight.sdk import workflows as sdk_workflows
from blacklight.sdk import Blacklight, SDKNotFoundError, TypedError
from blacklight.settings import Settings


def test_sdk_exports_blacklight():
    assert Blacklight.__name__ == "Blacklight"


def test_blacklight_mock_constructs_without_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("LLM_PROVIDER", "injected")
    monkeypatch.setenv("LLM_PROVIDER_ADAPTER", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("API_KEY", raising=False)

    client = Blacklight.mock(trace_db_path=tmp_path / "traces.sqlite3")

    assert client.provider_source == "mock"
    assert client.provider_name == "mock"
    assert client.model == "mock-ticket-classifier"
    assert client.trace_db_path == str(tmp_path / "traces.sqlite3")


def test_blacklight_from_settings_uses_configured_runtime(tmp_path):
    client = Blacklight.from_settings(
        Settings(
            provider="mock",
            model="mock-sdk-model",
            trace_db_path=str(tmp_path / "settings.sqlite3"),
        )
    )

    assert client.provider_source == "mock"
    assert client.provider_name == "mock"
    assert client.model == "mock-sdk-model"
    assert client.trace_db_path == str(tmp_path / "settings.sqlite3")


def test_blacklight_from_settings_can_load_user_env(tmp_path):
    user_env_path = tmp_path / "user.env"
    user_env_path.write_text(
        "\n".join(
            [
                "LLM_PROVIDER=mock",
                "LLM_MODEL=mock-from-user-env",
                f"TRACE_DB_PATH={tmp_path / 'user-env.sqlite3'}",
            ]
        ),
        encoding="utf-8",
    )

    client = Blacklight.from_settings(user_env_path=user_env_path)

    assert client.provider_name == "mock"
    assert client.provider_source == "mock"
    assert client.model == "mock-from-user-env"
    assert client.trace_db_path == str(tmp_path / "user-env.sqlite3")


def test_blacklight_from_provider_uses_explicit_provider(tmp_path):
    provider = MockProvider()

    client = Blacklight.from_provider(
        provider,
        model="explicit-model",
        trace_db_path=tmp_path / "provider.sqlite3",
    )

    assert client.provider_source == "injected"
    assert client.provider_name == "mock"
    assert client.model == "explicit-model"
    assert client.trace_db_path == str(tmp_path / "provider.sqlite3")


def test_blacklight_from_provider_rejects_non_provider():
    with pytest.raises(TypeError, match="LLMProvider"):
        Blacklight.from_provider(object(), model="bad")  # type: ignore[arg-type]


def test_blacklight_from_provider_accepts_provider_subclasses(tmp_path):
    class CustomProvider(MockProvider):
        name = "custom-sdk-provider"

    provider: LLMProvider = CustomProvider()

    client = Blacklight.from_provider(
        provider,
        model="custom-model",
        trace_db_path=Path(tmp_path / "custom.sqlite3"),
    )

    assert client.provider_name == "custom-sdk-provider"
    assert client.provider_source == "injected"
    assert client.model == "custom-model"


def test_blacklight_from_settings_marks_non_mock_as_injected(monkeypatch):
    class CustomProvider(MockProvider):
        name = "settings-custom-provider"

    provider = CustomProvider()
    monkeypatch.setattr(sdk_client, "create_provider", lambda _settings: provider)

    client = Blacklight.from_settings(
        Settings(
            provider="injected",
            provider_adapter="custom",
            custom_provider_path="my_app.providers:Provider",
            model="settings-custom-model",
        )
    )

    assert client.provider_source == "injected"
    assert client.provider_name == "settings-custom-provider"


def test_blacklight_workflows_list_ticket_classifier(tmp_path):
    client = Blacklight.mock(trace_db_path=tmp_path / "workflows.sqlite3")

    workflows = client.workflows.list()

    assert [workflow.workflow_id for workflow in workflows] == ["ticket_classifier"]
    assert workflows[0].input_model == "TicketRequest"
    assert workflows[0].output_model == "TicketClassification"


def test_blacklight_workflow_run_ticket_classifier_mock_mode(tmp_path):
    trace_db_path = tmp_path / "workflow-run.sqlite3"
    client = Blacklight.mock(trace_db_path=trace_db_path)

    result = client.workflows.run_ticket_classifier(
        subject="Invoice refund request",
        body="The customer was charged twice and needs a refund.",
        session_id="sdk-session",
    )

    assert result.workflow_id == "ticket_classifier"
    assert result.run_status == "completed"
    assert result.output is not None
    assert result.output.category.value == "billing"
    assert result.trace_id == result.trace.trace_id
    assert result.trace.session_id == "sdk-session"
    assert result.trace.agent_run_id == result.workflow_run_id
    assert result.validation.passed is True
    assert result.validation.guardrail_outcome == "accepted"
    assert result.review.state == "accepted"
    assert result.provider == "mock"
    assert result.model == "mock-ticket-classifier"
    assert result.prompt_id == TicketClassifier.prompt_id
    assert result.prompt_version >= 1
    assert result.latency_ms >= 0
    assert result.estimated_cost_usd >= 0

    trace = TraceStore(trace_db_path).get_by_request_id(result.trace_id)
    assert trace is not None
    assert trace["agent_run_id"] == result.workflow_run_id
    assert trace["prompt_id"] == TicketClassifier.prompt_id


def test_blacklight_workflow_run_ticket_classifier_needs_review(tmp_path):
    client = Blacklight.mock(trace_db_path=tmp_path / "needs-review.sqlite3")

    result = client.workflows.run_ticket_classifier(
        subject="Fraud warning",
        body="The customer says their credit card was used without approval.",
        session_id="review-session",
    )

    assert result.run_status == "completed"
    assert result.output is not None
    assert result.output.needs_review is True
    assert result.trace.session_id == "review-session"
    assert result.validation.passed is False
    assert result.validation.guardrail_outcome == "needs_review"
    assert result.validation.errors == []
    assert result.review.state == "needs_review"
    assert result.review.required is True
    assert result.review.routing_decision == "block_downstream_touch"
    assert result.guardrail["outcome"] == "needs_review"


def test_blacklight_workflow_run_generic_dispatch_accepts_ticket_request(tmp_path):
    client = Blacklight.mock(trace_db_path=tmp_path / "generic-run.sqlite3")

    result = client.workflows.run(
        "ticket_classifier",
        input=TicketRequest(
            subject="Login loop",
            body="The user hits an API error after signing in.",
        ),
    )

    assert result.output is not None
    assert result.output.category.value == "technical"
    assert result.trace.session_id == result.workflow_run_id


def test_blacklight_workflow_run_generic_dispatch_accepts_mapping(tmp_path):
    client = Blacklight.mock(trace_db_path=tmp_path / "mapping-run.sqlite3")

    result = client.workflows.run(
        "ticket_classifier",
        input={
            "subject": "Password reset",
            "body": "The user lost account access.",
            "session_id": "mapping-session",
        },
    )

    assert result.output is not None
    assert result.output.category.value == "account"
    assert result.trace.session_id == "mapping-session"


def test_blacklight_workflow_run_rejects_unknown_workflow(tmp_path):
    client = Blacklight.mock(trace_db_path=tmp_path / "unknown-run.sqlite3")

    with pytest.raises(ValueError, match="Unsupported workflow_id"):
        client.workflows.run(
            "not_a_workflow",
            input={"subject": "Hello", "body": "World"},
        )


def test_blacklight_workflow_run_raises_for_invalid_input_shape(tmp_path):
    client = Blacklight.mock(trace_db_path=tmp_path / "invalid-input.sqlite3")

    with pytest.raises(ValueError):
        client.workflows.run(
            "ticket_classifier",
            input={"subject": "Missing body"},
        )


def test_blacklight_workflow_result_is_serializable(tmp_path):
    client = Blacklight.mock(trace_db_path=tmp_path / "serializable.sqlite3")

    result = client.workflows.run_ticket_classifier(
        subject="Billing question",
        body="Can you explain this payment?",
    )

    payload = result.model_dump(mode="json")
    assert payload["trace"]["trace_id"] == result.trace_id
    assert payload["output"]["category"] == "billing"


def test_blacklight_workflow_uses_same_classifier_behavior_as_direct_path(tmp_path):
    subject = "Invoice refund request"
    body = "The customer was charged twice and needs a refund."
    client = Blacklight.mock(trace_db_path=tmp_path / "sdk.sqlite3")
    direct_classifier = TicketClassifier(provider=MockProvider(), model=client.model)

    sdk_result = client.workflows.run_ticket_classifier(subject=subject, body=body)
    direct_result = direct_classifier.classify(TicketRequest(subject=subject, body=body))

    assert sdk_result.output == direct_result


def test_blacklight_workflow_returns_failed_result_for_guardrail_validation(tmp_path):
    class InvalidJsonProvider(LLMProvider):
        name = "invalid-json"

        def complete(self, request: ProviderRequest) -> ProviderResponse:
            return ProviderResponse(
                text="not-json",
                provider=self.name,
                model=request.model,
                input_tokens=1,
                output_tokens=1,
            )

    client = Blacklight.from_provider(
        InvalidJsonProvider(),
        model="invalid-model",
        trace_db_path=tmp_path / "validation.sqlite3",
    )

    result = client.workflows.run_ticket_classifier(
        subject="Billing question",
        body="Can you explain this payment?",
    )

    assert result.run_status == "failed"
    assert result.output is None
    assert result.validation.passed is False
    assert result.validation.guardrail_outcome == "rejected"
    assert result.validation.errors
    assert result.review.state == "rejected"
    assert result.trace_id
    assert result.error is not None
    assert result.error.category == "validation_error"


def test_blacklight_workflow_returns_failed_result_for_provider_failure(tmp_path):
    class BrokenProvider(LLMProvider):
        name = "broken-provider"

        def complete(self, request: ProviderRequest) -> ProviderResponse:
            raise RuntimeError("Provider endpoint is unavailable.")

    client = Blacklight.from_provider(
        BrokenProvider(),
        model="broken-model",
        trace_db_path=tmp_path / "provider-failure.sqlite3",
    )

    result = client.workflows.run_ticket_classifier(
        subject="Billing question",
        body="Can you explain this payment?",
    )

    assert result.run_status == "failed"
    assert result.output is None
    assert result.trace_id
    assert result.trace is not None
    assert result.trace.agent_run_id == result.workflow_run_id
    assert result.validation.passed is False
    assert result.validation.guardrail_outcome == "rejected"
    assert result.validation.error_category == "provider_error"
    assert result.review.state == "rejected"
    assert result.error is not None
    assert result.error.category == "provider_error"
    assert "provider credentials" in result.error.next_step


def test_blacklight_workflow_returns_failed_result_for_storage_setup_failure(
    monkeypatch,
    tmp_path,
):
    class BrokenTraceStore:
        def __init__(self, _db_path: str) -> None:
            raise sqlite3.OperationalError("unable to open database file")

    monkeypatch.setattr(sdk_workflows, "TraceStore", BrokenTraceStore)
    client = Blacklight.mock(trace_db_path=tmp_path / "missing" / "traces.sqlite3")

    result = client.workflows.run_ticket_classifier(
        subject="Billing question",
        body="Can you explain this payment?",
    )

    assert result.run_status == "failed"
    assert result.output is None
    assert result.trace is None
    assert result.trace_id is None
    assert result.validation.passed is False
    assert result.validation.error_category == "storage_error"
    assert result.review.state == "rejected"
    assert result.error is not None
    assert result.error.category == "storage_error"
    assert "trace database" in result.error.likely_cause
    assert "TRACE_DB_PATH" in result.error.next_step


def test_blacklight_agents_list_and_show_ticket_classifier(tmp_path):
    client = Blacklight.mock(trace_db_path=tmp_path / "agents.sqlite3")

    agents = client.agents.list()
    profile = client.agents.show("ticket_classifier_agent")

    assert [agent.agent_id for agent in agents.agents] == ["ticket_classifier_agent"]
    assert agents.agents[0].workflow_id == "ticket_classifier"
    assert agents.agents[0].output_schema == "TicketClassification"
    assert agents.agents[0].prompt_ids == [TicketClassifier.prompt_id]
    assert profile.agent.agent_id == "ticket_classifier_agent"
    assert profile.domain["prompt_ids"] == [TicketClassifier.prompt_id]
    assert profile.governed_range["output_schema"] == "TicketClassification"
    assert "domain_boundary" in profile.trace_contract["required_steps"]


def test_blacklight_agents_show_missing_agent_raises_typed_error(tmp_path):
    client = Blacklight.mock(trace_db_path=tmp_path / "missing-agent.sqlite3")

    with pytest.raises(SDKNotFoundError, match="Agent not found"):
        client.agents.show("missing_agent")


def test_blacklight_agents_run_ticket_classifier_persists_agent_run(tmp_path):
    trace_db_path = tmp_path / "agent-run.sqlite3"
    client = Blacklight.mock(trace_db_path=trace_db_path)

    result = client.agents.run(
        "ticket_classifier_agent",
        input={
            "subject": "Invoice refund request",
            "body": "The customer was charged twice and needs a refund.",
            "session_id": "sdk-agent-session",
            "context": {"source": "sdk-test"},
            "insight": "Synthetic billing signal.",
            "suggested_action": {"queue": "billing"},
            "final_action": {"status": "not_exported"},
        },
    )

    assert result.run_status == "completed"
    assert result.payload["agent_run"]["agent_id"] == "ticket_classifier_agent"
    assert result.payload["output"]["category"] == "billing"
    assert result.payload["trace"]["agent_run_id"] == result.agent_run_id
    assert result.trace_id == result.envelope["trace_id"]
    assert result.envelope["domain_snapshot"]["prompt_ids"] == [TicketClassifier.prompt_id]
    assert result.envelope["range_output"]["output"]["category"] == "billing"
    assert result.envelope["run_context"]["context"] == {"source": "sdk-test"}
    assert result.run_context["suggested_action"] == {"queue": "billing"}
    assert result.domain_to_range is not None
    assert result.domain_to_range["agent_run"]["agent_run_id"] == result.agent_run_id
    assert result.domain_to_range["agent_run"]["session_id"] == "sdk-agent-session"
    assert result.domain_to_range["run_context"]["insight"] == "Synthetic billing signal."
    assert result.domain_to_range["review"]["state"] == "accepted"

    stored_run = AgentRunStore(trace_db_path).get(result.agent_run_id)
    assert stored_run is not None
    assert stored_run["trace_id"] == result.trace_id
    assert stored_run["session_id"] == "sdk-agent-session"
    assert stored_run["run_context"]["final_action"] == {"status": "not_exported"}


def test_blacklight_agents_run_ticket_classifier_needs_review(tmp_path):
    client = Blacklight.mock(trace_db_path=tmp_path / "agent-review.sqlite3")

    result = client.agents.run(
        "ticket_classifier_agent",
        input={
            "subject": "Fraud warning",
            "body": "The customer says their credit card was used without approval.",
            "session_id": "sdk-agent-review",
        },
    )

    assert result.run_status == "completed"
    assert result.payload["validation"]["passed"] is False
    assert result.payload["validation"]["guardrail_outcome"] == "needs_review"
    assert result.payload["review"]["state"] == "needs_review"
    assert result.envelope["guardrail"]["outcome"] == "needs_review"
    assert result.envelope["review"]["touch_decision"] == "block_downstream_touch"
    assert result.domain_to_range is not None
    assert result.domain_to_range["review"]["state"] == "needs_review"


def test_blacklight_agents_run_returns_failed_result_for_guardrail_validation(tmp_path):
    class InvalidJsonProvider(LLMProvider):
        name = "invalid-json"

        def complete(self, request: ProviderRequest) -> ProviderResponse:
            return ProviderResponse(
                text="not-json",
                provider=self.name,
                model=request.model,
                input_tokens=1,
                output_tokens=1,
            )

    client = Blacklight.from_provider(
        InvalidJsonProvider(),
        model="invalid-model",
        trace_db_path=tmp_path / "agent-validation.sqlite3",
    )

    result = client.agents.run(
        "ticket_classifier_agent",
        input={
            "subject": "Billing question",
            "body": "Can you explain this payment?",
        },
    )

    assert result.run_status == "failed"
    assert result.error is not None
    assert isinstance(result.error, TypedError)
    assert result.error.category == "validation_error"
    assert result.payload["output"] is None
    assert result.payload["validation"]["passed"] is False
    assert result.payload["validation"]["guardrail_outcome"] == "rejected"
    assert result.envelope["review"]["state"] == "rejected"
    assert result.domain_to_range is not None
    assert result.domain_to_range["range"]["output"] is None


def test_blacklight_agents_run_returns_failed_result_for_storage_setup_failure(
    monkeypatch,
    tmp_path,
):
    class BrokenTraceStore:
        def __init__(self, _db_path: str) -> None:
            raise sqlite3.OperationalError("unable to open database file")

    monkeypatch.setattr(sdk_agents, "TraceStore", BrokenTraceStore)
    client = Blacklight.mock(trace_db_path=tmp_path / "missing" / "traces.sqlite3")

    result = client.agents.run(
        "ticket_classifier_agent",
        input={
            "subject": "Billing question",
            "body": "Can you explain this payment?",
            "session_id": "sdk-agent-storage",
            "context": {"source": "storage-test"},
        },
    )

    assert result.run_status == "failed"
    assert result.trace_id is None
    assert result.envelope is None
    assert result.domain_to_range is None
    assert result.run_context == {"context": {"source": "storage-test"}}
    assert result.payload["run_context"] == {"context": {"source": "storage-test"}}
    assert result.payload["trace"]["trace_db_path"] == str(
        tmp_path / "missing" / "traces.sqlite3"
    )
    assert result.error is not None
    assert result.error.category == "storage_error"
    assert "trace database" in result.error.likely_cause
    assert result.payload["domain"]["prompt_ids"] == [TicketClassifier.prompt_id]
    assert result.payload["governed_range"]["output_schema"] == "TicketClassification"
    assert "domain_boundary" in result.payload["trace_contract"]["required_steps"]


def test_blacklight_agents_run_returns_failed_result_for_agent_run_write_failure(
    monkeypatch,
    tmp_path,
):
    class BrokenAgentRunStore:
        def __init__(self, _db_path: str) -> None:
            pass

        def insert(self, _envelope: dict[str, object]) -> None:
            raise sqlite3.OperationalError("unable to write agent run envelope")

    monkeypatch.setattr(sdk_agents, "AgentRunStore", BrokenAgentRunStore)
    client = Blacklight.mock(trace_db_path=tmp_path / "agent-run-write.sqlite3")

    result = client.agents.run(
        "ticket_classifier_agent",
        input={
            "subject": "Invoice refund request",
            "body": "The customer was charged twice and needs a refund.",
            "session_id": "sdk-agent-write-failure",
            "insight": "Synthetic billing signal.",
        },
    )

    assert result.run_status == "failed"
    assert result.trace_id is not None
    assert result.envelope is not None
    assert result.domain_to_range is not None
    assert result.domain_to_range["run_context"]["insight"] == "Synthetic billing signal."
    assert result.payload["trace_envelope"]["trace_id"] == result.trace_id
    assert result.error is not None
    assert result.error.category == "storage_error"


def test_blacklight_traces_list_and_show_workflow_trace(tmp_path):
    client = Blacklight.mock(trace_db_path=tmp_path / "trace-client.sqlite3")
    workflow = client.workflows.run_ticket_classifier(
        subject="Invoice refund request",
        body="The customer was charged twice and needs a refund.",
        session_id="sdk-trace-session",
    )

    traces = client.traces.list(limit=5)
    detail = client.traces.show(workflow.trace_id)

    assert [trace["request_id"] for trace in traces.traces] == [workflow.trace_id]
    assert detail.trace["request_id"] == workflow.trace_id
    assert detail.trace["session_id"] == "sdk-trace-session"
    assert detail.eval_evidence["prompt_id"] == TicketClassifier.prompt_id
    assert detail.eval_evidence["linked"] is False


def test_blacklight_traces_show_missing_trace_raises_typed_error(tmp_path):
    client = Blacklight.mock(trace_db_path=tmp_path / "missing-trace.sqlite3")

    with pytest.raises(SDKNotFoundError, match="Trace not found"):
        client.traces.show("missing-trace")


def test_blacklight_evals_run_list_and_show_mock_mode(tmp_path):
    client = Blacklight.mock(trace_db_path=tmp_path / "eval-client.sqlite3")

    run = client.evals.run(session_id="sdk-eval", eval_run_id="sdk-eval-run")
    runs = client.evals.list(limit=5)
    detail = client.evals.show("sdk-eval-run")

    assert run.report["eval_run_id"] == "sdk-eval-run"
    assert run.report["session_id"] == "sdk-eval"
    assert run.report["summary"]["case_count"] > 0
    assert [item["eval_run_id"] for item in runs.eval_runs] == ["sdk-eval-run"]
    assert detail.eval_run["eval_run_id"] == "sdk-eval-run"
    assert len(detail.eval_run["cases"]) == run.report["summary"]["case_count"]
    assert len(detail.traces) == run.report["summary"]["case_count"]
    assert detail.traces[0]["eval_evidence"]["linked"] is True
    assert detail.traces[0]["eval_evidence"]["eval_run_id"] == "sdk-eval-run"


def test_blacklight_evals_show_missing_eval_raises_typed_error(tmp_path):
    client = Blacklight.mock(trace_db_path=tmp_path / "missing-eval.sqlite3")

    with pytest.raises(SDKNotFoundError, match="Eval run not found"):
        client.evals.show("missing-eval")


def test_blacklight_evals_compare_prompt_versions(tmp_path):
    client = Blacklight.mock(trace_db_path=tmp_path / "eval-compare.sqlite3")

    comparison = client.evals.compare(
        baseline_version=1,
        candidate_version=2,
        session_id="sdk-compare",
    )

    assert comparison.comparison["prompt_id"] == TicketClassifier.prompt_id
    assert comparison.comparison["baseline"]["prompt_version"] == 1
    assert comparison.comparison["candidate"]["prompt_version"] == 2
    assert "accuracy" in comparison.comparison["summary_deltas"]


def test_blacklight_evals_compare_requires_factory_for_injected_provider(tmp_path):
    client = Blacklight.from_provider(
        MockProvider(),
        model="mock-ticket-classifier",
        trace_db_path=tmp_path / "injected-compare.sqlite3",
    )

    with pytest.raises(ValueError, match="provider_factory"):
        client.evals.compare(baseline_version=1, candidate_version=2)


def test_blacklight_evals_compare_accepts_factory_for_injected_provider(tmp_path):
    client = Blacklight.from_provider(
        MockProvider(),
        model="mock-ticket-classifier",
        trace_db_path=tmp_path / "factory-compare.sqlite3",
    )

    comparison = client.evals.compare(
        baseline_version=1,
        candidate_version=2,
        provider_factory=MockProvider,
    )

    assert comparison.comparison["baseline"]["provider"] == "mock"
    assert comparison.comparison["candidate"]["provider"] == "mock"


def test_blacklight_providers_health_list_and_status(tmp_path):
    client = Blacklight.mock(trace_db_path=tmp_path / "providers.sqlite3")

    health = client.providers.health()
    providers = client.providers.list()
    status = client.providers.status()

    assert health.provider == "mock"
    assert health.model == "mock-ticket-classifier"
    assert health.provider_key_configured is False
    assert providers.active_provider == "mock"
    assert providers.providers[0]["name"] == "mock"
    assert providers.providers[0]["configured"] is True
    assert status.runtime.provider == "mock"
    assert status.providers["mock"]["ready"] is True
    assert "fallback" in status.local_model


def test_blacklight_providers_status_can_skip_local_probe(tmp_path):
    client = Blacklight.mock(trace_db_path=tmp_path / "providers-no-probe.sqlite3")

    status = client.providers.status(include_local_probe=False)

    assert status.local_model["status"] == "not_probed"
    assert status.local_model["ready"] is None
    assert "not probed" in status.local_model["status_message"]
