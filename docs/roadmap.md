# Roadmap

## MVP

- Provider gateway
- Mock provider
- Prompt registry
- Ticket-classification example
- Pydantic guardrails
- SQLite traces
- Eval runner
- Tests
- CI

## Milestone 1 Completion

Milestone 1 is complete as a runnable MVP. The project now supports:

- `llm-platform` CLI entry points for classification, evals, metrics, health, prompts, and traces
- configurable provider creation for mock, OpenAI, and user-owned providers
- retry, timeout, per-session rate limiting, idempotency, and provider failure tracing
- richer eval reports with persisted run/case metrics and per-case trace links
- deterministic mock-mode tests and smoke-checkable API/CLI workflows

## Milestone 2 Completion

Milestone 2 is complete as an observability and guardrail hardening pass. The project now supports:

- expanded trace queries and metrics by provider, model, provider/model pair, and guardrail outcome
- persisted eval summaries, per-case diagnostics, session IDs, and trace links for run review
- guardrail routing outcomes for accepted, needs-review, and rejected model outputs
- public-safe synthetic fixtures with a lightweight regression check for obvious private identifiers
- passing test, lint, observability smoke, and guardrail outcome smoke checks

## Next

- Complete the public [issue ticket packages](issues/index.md):
  - [Milestone 3: Portfolio-Grade Documentation](issues/milestone-3.md)
  - [Milestone 4: Packaging And Release](issues/milestone-4.md)
- Add prompt version comparison report
- Add architecture screenshots or terminal examples to the README
- Add a lightweight Dockerfile

## Later

- Add Azure OpenAI provider
- Add OpenTelemetry export
- Add human-review queue example
- Add RAG policy-question example
- Add deployment notes for container platforms
