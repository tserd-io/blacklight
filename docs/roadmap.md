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

## Milestone 3 Completion

Milestone 3 is complete as a portfolio-grade documentation pass. The project now supports:

- a README that explains the platform story, quickstart, CLI/API examples, eval output, trace metrics, provider configuration, and production extension path
- strengthened architecture docs with component responsibilities, request lifecycle, mock-provider rationale, and production plug-in points
- tradeoff and failure-mode docs that frame MVP choices, deferred work, backend options, operating risks, mitigations, and production extensions
- a create-your-own-workflow guide that shows how to extend the starter beyond the ticket-classifier reference implementation
- public issue-ticket packages that separate CLI-ready release work from later business-user app productization
- passing test, lint, documented command smoke, API smoke, public-safe data, and internal doc-link checks

## Milestone 4 Completion

Milestone 4 is complete as a CLI-ready package and release-preparation pass. The project now supports:

- Docker API packaging for mock-mode smoke testing
- GitHub Actions CI that runs linting and tests without provider secrets
- v0.1.0 release notes for the CLI-ready MVP
- operational cost and ownership guidance for regular live runs
- session history trace review from the CLI
- optional Ollama local-runtime configuration through the custom provider path
- final QA checks for tests, linting, CLI smoke, API smoke, eval smoke, docs links, ignored private plans, and GitHub Actions

Docker was not available on the local QA machine, so Docker and Ollama runtime smoke checks are recorded as a local limitation rather than a passed local check. The `v0.1.0` tag should be created only after final human approval.

## Next

- Complete the public [issue ticket packages](issues/index.md):
  - [Milestone 5: Business-User App Productization](issues/milestone-5.md)
- Add architecture screenshots or terminal examples to the README

## Later

- Add Azure OpenAI provider
- Add OpenTelemetry export
- Add RAG policy-question example
- Add deployment notes for container platforms
- Explore a packaged desktop app with an installer, app icon, first-run setup, local model management, and hosted-provider fallback
