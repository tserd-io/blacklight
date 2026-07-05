# Create Your Own Workflow

This project is designed to be extended. The built-in ticket classifier is the reference implementation; this guide shows how to add a new workflow that reuses the same provider, prompt, guardrail, trace, eval, CLI, and API layers.

Use this when you want the starter to become a platform scaffold for your own task instead of a one-off demo. You should be able to copy the ticket-classifier pattern, rename the domain pieces, and keep the platform behavior around reliability, observability, and evaluation.

The example below uses a synthetic public-safe task: **document intake triage**. The workflow reads a short synthetic document note and returns structured routing data for an internal review queue. It is only a guide; the concrete files in this repo still use the ticket-classification workflow as the working example.

## Target Shape

A workflow should have these pieces:

- a typed request and response schema
- one prompt template with metadata and input variables
- one workflow class or function that renders the prompt, calls the provider, validates output, and writes traces
- guardrail validation for parsing and routing outcomes
- synthetic eval fixtures and tests
- optional CLI/API entry points when the workflow should be demoed directly

The reusable platform pieces are already present. A new workflow mainly supplies the domain contract, prompt, validator, fixtures, and thin orchestration path.

## 1. Define The Workflow Contract

Start with the shape of the input and output. Existing schemas live in [src/llm_platform_starter/models.py](../src/llm_platform_starter/models.py).

For a new workflow, either add small shared models there or create a workflow-specific module such as:

```text
src/llm_platform_starter/examples/document_triage.py
```

For document intake triage, the request might include:

- `title`
- `body`
- `source_type`
- `session_id`
- `idempotency_key`

The response might include:

- `route`: `finance`, `legal`, `operations`, or `general`
- `priority`: `low`, `medium`, or `high`
- `confidence`
- `rationale`
- `needs_review`

Keep fields narrow and typed. The validator can only protect downstream code if the schema is explicit.

## 2. Add A Prompt Template

Prompt templates live in [src/llm_platform_starter/prompts/templates/](../src/llm_platform_starter/prompts/templates). The ticket example is [ticket_classifier.json](../src/llm_platform_starter/prompts/templates/ticket_classifier.json).

Create a new file such as:

```text
src/llm_platform_starter/prompts/templates/document_triage.json
```

Use metadata to make the prompt easy to inspect and evaluate:

```json
{
  "prompt_id": "document_triage",
  "display_name": "Document Intake Triage",
  "domain": "internal_operations",
  "task_type": "classification",
  "output_schema": "DocumentTriage",
  "eval_fixture": "document_triage.jsonl",
  "comparison_group": "document_intake_triage",
  "tags": ["documents", "routing", "synthetic"],
  "versions": [
    {
      "version": 1,
      "active": true,
      "notes": "Initial synthetic document-routing prompt.",
      "input_variables": ["title", "body", "source_type"],
      "template": "Classify this synthetic document for internal routing. Return only JSON with route, priority, confidence, rationale, and needs_review. Source type: $source_type\nTitle: $title\nBody: $body"
    }
  ]
}
```

Keep fixture names, output schema names, and comparison groups aligned. That lets evals and prompt comparison reports avoid comparing unrelated prompts.

## 3. Build The Workflow Path

Use [src/llm_platform_starter/examples/ticket_classifier.py](../src/llm_platform_starter/examples/ticket_classifier.py) as the working pattern.

A workflow should:

1. Load the prompt with `PromptRegistry().get("document_triage")`.
2. Render it with request fields.
3. Build a `ProviderRequest` with `prompt`, `model`, and metadata such as `request_id`, `session_id`, and `prompt_id`.
4. Call `complete_with_retries()` from [src/llm_platform_starter/providers/reliability.py](../src/llm_platform_starter/providers/reliability.py).
5. Validate the provider text with a guardrail function.
6. Write a `TraceRecord` through `TraceStore` from [src/llm_platform_starter/observability/storage.py](../src/llm_platform_starter/observability/storage.py).
7. Return the typed response object.

If the workflow can be retried by a caller, follow the idempotency pattern in `TicketClassifier`: derive a stable key from the workflow name, prompt version, and input content, then use [src/llm_platform_starter/observability/idempotency.py](../src/llm_platform_starter/observability/idempotency.py).

## 4. Add Validation And Guardrails

Validation functions live in [src/llm_platform_starter/guardrails/](../src/llm_platform_starter/guardrails). The ticket workflow uses [validation.py](../src/llm_platform_starter/guardrails/validation.py).

For a new workflow, create a parser that:

- parses provider output as JSON
- validates it against the workflow response model
- returns `accepted` when parsing and schema validation pass
- returns `needs_review` when the model or policy flags reviewable content
- returns `rejected` when JSON or schema validation fails

Keep public-safe checks simple at first. For example, a document triage workflow can mark `needs_review` when synthetic text includes placeholders such as `SSN`, `credit card`, or `password`, but the fixtures should not contain real private data.

## 5. Add Synthetic Eval Fixtures

Eval fixtures live in [src/llm_platform_starter/evals/fixtures/](../src/llm_platform_starter/evals/fixtures). The ticket fixture is `ticket_classification.jsonl`.

For document triage, add:

```text
src/llm_platform_starter/evals/fixtures/document_triage.jsonl
```

Each line should be a small public-safe JSON object:

```json
{"id":"invoice_notice","title":"Synthetic invoice received","body":"A fictional supplier sent a materials invoice for review.","source_type":"email","expected_route":"finance"}
```

Do not use real names, real addresses, real customers, real vendors, real contracts, or copied private documents. Use clearly fictional organizations, invented places, and short synthetic text.

## 6. Add An Eval Runner

The existing eval runner is [src/llm_platform_starter/evals/runner.py](../src/llm_platform_starter/evals/runner.py). For a second workflow, you can either:

- add a workflow-specific function such as `run_document_triage_eval()`
- or extract shared eval helpers once two workflows reveal real duplication

Keep the first version direct and readable. A good eval report should include:

- `eval_run_id`
- `session_id`
- `fixture_name`
- `prompt_id`
- `prompt_version`
- `provider`
- `model`
- `summary`
- `cases`

For each case, preserve the expected route, actual route, pass/fail status, schema validity, review flag, latency, token counts, estimated cost, retry count, and error category. This mirrors the ticket eval shape and keeps CLI/API reporting predictable.

## 7. Add Tests

Use the existing tests as a map:

- [tests/test_prompt_registry.py](../tests/test_prompt_registry.py): prompt metadata and rendering
- [tests/test_guardrails.py](../tests/test_guardrails.py): validation outcomes
- [tests/test_evals.py](../tests/test_evals.py): eval report shape and deterministic mock behavior
- [tests/test_tracing.py](../tests/test_tracing.py): trace records and metrics
- [tests/test_cli.py](../tests/test_cli.py): CLI behavior when the workflow gets a command
- [tests/test_public_safe_data.py](../tests/test_public_safe_data.py): obvious private-data pattern checks

At minimum, add tests that prove:

- the prompt renders with the expected variables
- the validator accepts valid JSON and rejects invalid JSON
- the workflow returns the expected typed response with the mock provider or a small fake provider
- a trace is written with the right `prompt_id`, `prompt_version`, provider, model, guardrail outcome, and error category
- evals are deterministic in mock mode
- synthetic fixtures do not contain obvious private-data patterns

## 8. Decide Whether To Expose CLI Or API

The existing CLI is [src/llm_platform_starter/cli.py](../src/llm_platform_starter/cli.py). The existing API is [src/llm_platform_starter/api.py](../src/llm_platform_starter/api.py).

Add a CLI command when the workflow should be easy to demo or run in CI. For example:

```bash
llm-platform document-triage --title "Synthetic invoice received" --body "A fictional supplier sent a materials invoice."
```

Add an API route when the workflow should be callable by an application. Keep request and response models typed, and reuse the same workflow class used by the CLI.

## Minimal Checklist

- Define request and response models.
- Add a prompt template with metadata, input variables, and one active version.
- Implement a workflow path that renders the prompt, calls the provider, validates output, writes traces, and returns a typed response.
- Add guardrail validation for accepted, needs-review, and rejected outcomes.
- Add public-safe JSONL eval fixtures.
- Add an eval runner or workflow-specific eval function.
- Add tests for prompts, validation, workflow behavior, tracing, evals, and fixture safety.
- Add CLI/API entry points only when the workflow needs a direct user-facing surface.
- Run `pytest` and `ruff check .`.

## Public-Safe Rule

Every example should be synthetic and safe to publish. Prefer fictional entities, invented places, and short task-focused snippets. Avoid real people, real customer data, real addresses, copied contracts, account identifiers, private emails, or production logs.
