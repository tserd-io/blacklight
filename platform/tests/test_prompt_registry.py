from llm_platform_starter.prompts.registry import PromptRegistry


def test_prompt_registry_loads_and_renders_active_prompt():
    prompt = PromptRegistry().get("ticket_classifier")

    rendered = prompt.render(subject="API error", body="Export fails.")

    assert prompt.version == 1
    assert prompt.display_name == "Support Ticket Classifier"
    assert prompt.comparison_group == "support_ticket_classification"
    assert prompt.output_schema == "TicketClassification"
    assert prompt.eval_fixture == "ticket_classification.jsonl"
    assert "support" in prompt.tags
    assert "API error" in rendered
    assert "Export fails." in rendered


def test_prompt_registry_loads_inactive_version_by_number():
    prompt = PromptRegistry().get("ticket_classifier", version=2)

    assert prompt.version == 2
    assert prompt.active is False
    assert prompt.comparison_group == "support_ticket_classification"
