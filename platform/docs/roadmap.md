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

- `blacklight` CLI entry points for classification, evals, metrics, health, prompts, and traces
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

## Milestone 5 Completion

Milestone 5 is complete as a self-explaining console and guided-demo pass. The project now supports:

- a local console dashboard for workflows, runs, traces, evals, prompts, providers, review queue, settings, and docs
- a mock-mode guided demo path that runs without live provider credentials
- seeded synthetic demo state with linked workflow runs, traces, eval cases, prompt versions, and reviewable outputs
- dashboard -> workflow -> run -> trace -> eval inspection paths through the console API and browser pages
- copy-friendly CLI equivalent commands in console API payloads for major actions
- app-managed `user.env` settings updates that stay separate from private operator-owned `.env` files
- final QA checks for linting, tests, guided demo smoke, seeded demo smoke, console API path coverage, and CLI-equivalent command parsing

Milestone 5 final QA was run on July 5, 2026. The smoke path confirmed the default `mock` provider works with `openai_configured=false` and no live provider key.

## Milestone 6 Completion

Milestone 6 is complete as a business-user productization approval pass. The project now supports:

- web-first app shell packaging guidance, with the browser web app as the enterprise default and an optional Windows/Linux desktop shell for local/private use
- app and installer icon source assets, startup/readiness routes, first-run modes, and provider-key bypass assumptions captured in `packaging/app-shell.json`
- a first-run provider setup path for demo mode, hosted provider mode, and local model mode
- local model status and fallback guidance that keeps provider secrets in private environment settings and keeps model weights out of the repo
- business-user console surfaces for dashboard, workflow runs, session history, traces, evals, prompts, providers, settings, local model status, first-run setup, and review queue
- final QA checks for linting, tests, app-shell packaging tests, first-run setup tests, local model behavior, guided demo smoke, console API smoke, CLI health, tracked-file hygiene, and whitespace checks

Milestone 6 final QA was run on July 6, 2026. Docker and live Ollama runtime smoke checks remain environment-dependent; the local QA pass verified configuration, status reporting, and recovery guidance without downloading model weights or requiring live provider credentials.

## Milestone 7 Completion

Milestone 7 is complete as a managed-agent foundation pass. The project now supports:

- a packaged `ticket_classifier_agent` definition with explicit domain, governed range, and trace contract fields
- read-only `blacklight agents list` and `blacklight agents show ticket_classifier_agent` CLI inspection
- read-only `/api/agents` and `/api/agents/ticket_classifier_agent` profile payloads
- read-only `/console/agents` and `/console/agents/ticket_classifier_agent` browser profile surfaces
- documentation for workflow vs agent vs future graph node, domain/range contracts, traceability, graph-readiness, non-goals, and safety constraints
- final QA checks for linting, tests, agent CLI smoke, agent API smoke, console profile smoke, docs accuracy, and no-live-key default behavior

Milestone 7 final QA was run on July 8, 2026. The smoke path confirmed managed-agent inspection works in mock mode with `openai_configured=false` and no live provider key.

## Next

- Prepare the productization branch for pull-request review and approval
- Decide whether the next release should stay CLI/package focused or include the web-first console and app-shell documentation
- Add architecture screenshots or terminal examples to the README

## Later

- Add Azure OpenAI provider
- Add OpenTelemetry export
- Add RAG policy-question example
- Add deployment notes for container platforms
- Add scheduled or release-gated Windows/macOS CLI smoke checks
- Add managed enterprise deployment controls for the browser web app
- Package the optional desktop shell with signing, update, installer, and fleet-managed desktop deployment hardening
