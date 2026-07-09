import json

import pytest
from pydantic import ValidationError

from blacklight.agents import AgentDefinition, AgentRegistry


def test_agent_registry_loads_ticket_classifier_agent():
    agent = AgentRegistry().get("ticket_classifier_agent")

    assert agent.agent_id == "ticket_classifier_agent"
    assert agent.version == 1
    assert agent.workflow_id == "ticket_classifier"
    assert agent.domain.retrieval_surface == [
        "approved static sample support-ticket context",
        "public-safe synthetic eval fixtures",
    ]
    assert "ticket subject" in agent.domain.context_inputs
    assert "ticket body" in agent.domain.context_inputs
    assert agent.domain.tools == []
    assert "mock-provider-first" in agent.domain.provider_policy
    assert agent.domain.prompt_ids == ["ticket_classifier"]
    assert agent.domain.prompt_versions["ticket_classifier"] == [1, 2]
    assert "no side-effecting tool calls" in agent.domain.limits
    assert "no external retrieval" in agent.domain.limits
    assert "read-only classification output metadata" in agent.governed_range.touch_surface
    assert agent.governed_range.output_schema == "TicketClassification"
    assert "trace contract references" in agent.governed_range.output_expectations
    assert agent.governed_range.allowed_side_effects == []
    assert any("needs_review=true" in item for item in agent.governed_range.review_requirements)
    assert "Pydantic schema validation" in agent.governed_range.guardrail_enforcement
    assert "domain_boundary" in agent.trace_contract.required_steps
    assert "review_export_touch_decision" in agent.trace_contract.required_steps
    assert "eval_evidence" in agent.trace_contract.required_steps
    assert "agent_id" in agent.trace_contract.evidence_fields
    assert "agent_run_id" in agent.trace_contract.evidence_fields
    assert "eval_run_id" in agent.trace_contract.eval_evidence


def test_agent_registry_lists_static_definitions():
    agents = AgentRegistry().list()

    assert [agent.agent_id for agent in agents] == ["ticket_classifier_agent"]


def test_agent_registry_get_optional_returns_none_for_missing_agent():
    registry = AgentRegistry()

    assert registry.get_optional("ticket_classifier_agent").agent_id == "ticket_classifier_agent"
    assert registry.get_optional("missing_agent") is None


def test_agent_registry_validates_custom_definition_directory(tmp_path):
    definition = AgentRegistry().get("ticket_classifier_agent").model_dump(mode="json")
    definition["agent_id"] = "custom_ticket_agent"
    definition_path = tmp_path / "custom_ticket_agent.json"
    definition_path.write_text(json.dumps(definition), encoding="utf-8")

    agent = AgentRegistry(tmp_path).get("custom_ticket_agent")

    assert agent.agent_id == "custom_ticket_agent"
    assert agent.workflow_id == "ticket_classifier"


def test_agent_definition_rejects_missing_trace_contract_step():
    definition = AgentRegistry().get("ticket_classifier_agent").model_dump(mode="json")
    definition["trace_contract"]["required_steps"].remove("guardrail_decision")

    with pytest.raises(ValidationError, match="guardrail_decision"):
        AgentDefinition.model_validate(definition)


def test_agent_definition_requires_prompt_versions_for_each_prompt_id():
    definition = AgentRegistry().get("ticket_classifier_agent").model_dump(mode="json")
    definition["domain"]["prompt_versions"] = {}

    with pytest.raises(ValidationError, match="ticket_classifier"):
        AgentDefinition.model_validate(definition)


def test_agent_definition_rejects_unknown_prompt_version_keys():
    definition = AgentRegistry().get("ticket_classifier_agent").model_dump(mode="json")
    definition["domain"]["prompt_versions"]["unknown_prompt"] = [1]

    with pytest.raises(ValidationError, match="unknown_prompt"):
        AgentDefinition.model_validate(definition)


def test_agent_definition_requires_positive_prompt_versions():
    definition = AgentRegistry().get("ticket_classifier_agent").model_dump(mode="json")
    definition["domain"]["prompt_versions"]["ticket_classifier"] = [0]

    with pytest.raises(ValidationError, match="invalid version"):
        AgentDefinition.model_validate(definition)
