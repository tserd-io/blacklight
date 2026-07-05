# Milestone 4 Issue Tickets: CLI-Ready Package And Release

Milestone 4 prepares the project as a CLI-ready, developer-operable package. The goal is that a technical user can install it, run `llm-platform`, configure providers, inspect traces and evals, and understand the operating cost/risk profile without needing a frontend.

Business-user frontend work is intentionally deferred to Milestone 5 so the release does not blur CLI/package readiness with desktop-product scope.

## 1. Add Dockerfile

Purpose:
Make the FastAPI service easy to run in a container without requiring live model-provider credentials.

Tasks:

- Add a minimal Python Dockerfile.
- Install the package and API dependencies.
- Run FastAPI with uvicorn.
- Document local build and run commands.
- Keep mock mode as the default.

Acceptance criteria:

- Container starts the API.
- `/health` returns `ok`.
- No API key is required for mock mode.
- Docker instructions are documented.

Suggested labels:

- `developer-experience`
- `release`
- `mvp`

## 2. Final CI Cleanup

Purpose:
Ensure the published project has a trustworthy build signal.

Tasks:

- Run tests in GitHub Actions.
- Run ruff in GitHub Actions.
- Keep dependency installation simple.
- Confirm CI does not require secrets.

Acceptance criteria:

- CI passes on push and pull request.
- CI runs tests and linting.
- CI uses mock mode and requires no live API keys.

Suggested labels:

- `ci`
- `release`
- `mvp`

## 3. Prepare v0.1 Release

Purpose:
Create a clean publish point for the CLI-ready portfolio project.

Tasks:

- Confirm README quickstart.
- Confirm tests and linting.
- Confirm ignored private plans.
- Add release notes.
- Tag the release.

Acceptance criteria:

- Working tree contains only intended public files.
- `plans/` is ignored.
- Release notes describe the CLI-ready MVP clearly.
- v0.1 tag is created after final approval.

Suggested labels:

- `release`
- `docs`
- `mvp`

## 4. Final QA And Release Approval

Purpose:
Perform the final public-readiness review before tagging or promoting the project.

Tasks:

- Run full tests and linting.
- Run CLI smoke checks.
- Run API smoke checks.
- Run eval smoke checks.
- Run Docker smoke check if Docker is available.
- Review README, docs, and issue packages for accuracy.
- Confirm no secrets, trace DBs, generated artifacts, or private plans are tracked.
- Confirm GitHub Actions passes.

Acceptance criteria:

- `pytest` passes.
- `ruff check .` passes.
- CLI, API, and eval smoke checks pass.
- Docker smoke check passes or a documented local limitation is recorded.
- CI passes on the release branch or main.
- Final approval is recorded before v0.1 is tagged.

Suggested labels:

- `qa`
- `release`
- `mvp`

## Candidate. Add Provider Configuration Smoke Tests

Purpose:
Verify that the provider factory works against real provider configurations without making live provider access required for CI.

Tasks:

- Add opt-in smoke tests for `mock`, `openai`, and `custom` provider configuration paths.
- Add an opt-in smoke test path for local LLM endpoints, such as Ollama, LM Studio, llama.cpp, vLLM, or a private localhost service.
- Gate live provider tests behind explicit environment flags.
- Document required environment variables for each smoke-test mode.
- Ensure default CI still runs with mock mode only and requires no secrets or local model runtime.
- Record skipped smoke-test reasons clearly when required configuration is absent.

Acceptance criteria:

- Mock provider smoke tests run in normal CI.
- OpenAI smoke tests run only when an explicit flag and API key are present.
- Custom provider smoke tests can target a real import path via `LLM_CUSTOM_PROVIDER`.
- Local endpoint smoke tests can target a real local runtime without changing application code.
- Skipped live-config tests are reported clearly and do not fail CI.
- Provider smoke-test instructions are documented.

Suggested labels:

- `qa`
- `provider-gateway`
- `developer-experience`
- `release`

## Candidate. Add Operational Cost And Ownership Guide

Purpose:
Show that the project owner can reason about the operational decisions and costs behind automating LLM workflows, not only the implementation.

Tasks:

- Add a cost and ownership guide for regular live analysis.
- Use an example operating profile of 5 live-analysis runs per day.
- Explain hosted-provider costs using tokens, model pricing, retries, eval runs, and failed calls.
- Explain local/on-prem costs using hardware, depreciation, electricity, maintenance, utilization, and support burden.
- Compare hosted API, local/on-prem provider, and local fallback choices.
- Explain how trace fields support measured cost and operational review.
- Keep mock mode clearly separate from real provider cost.

Acceptance criteria:

- A reader can estimate the cost of 5 live-analysis runs per day.
- Hosted and local/on-prem cost models are both covered.
- The guide explains when local fallback is shippable and when it adds support risk.
- The guide demonstrates ownership of automation risk, budget, provider choice, and escalation decisions.

Suggested labels:

- `docs`
- `release`
- `architecture`
- `observability`

## Candidate. Add Session History Trace View

Purpose:
Make the CLI-ready package easier to operate by letting users inspect what happened during a session over time.

Tasks:

- Add a command such as `llm-platform session show <session_id>`.
- List traces for the session in chronological order.
- Include provider, model, prompt version, latency, tokens, cost, guardrail outcome, validation status, and error category.
- Include a session summary with request count, total tokens, total estimated cost, failure rate, review count, and provider/model breakdown.
- Document how session history differs from prompt comparison: prompt comparison is for eval regression, session history is for operational review.

Acceptance criteria:

- A user can inspect all trace records for a session from the CLI.
- The view includes per-request detail and aggregate session summary.
- The command works with mock-mode SQLite traces and no live API keys.
- Tests cover ordering, aggregation, review/failure counts, and missing-session behavior.

Suggested labels:

- `observability`
- `usability`
- `developer`
- `release`

## Candidate. Add Ollama Local Runtime Configuration

Purpose:
Make the local-model path easier to test by providing a repo-owned Ollama runtime configuration without making Ollama, Docker, GPU access, or model downloads required for CI.

Tasks:

- Add a Docker Compose configuration for running Ollama locally.
- Add or document a bundled Ollama provider adapter that uses the existing `custom` provider path.
- Document how to pull a local model such as `llama3.1`.
- Document the environment variables needed to point `llm-platform` at the local Ollama endpoint.
- Keep `mock` as the default provider for quickstart and CI.
- Add opt-in smoke-test guidance for a real Ollama runtime.
- Clarify that model weights and runtime downloads are local developer artifacts, not files committed to the repo.

Acceptance criteria:

- A developer can start Ollama from repo instructions.
- A developer can configure `LLM_PROVIDER=custom` and use the bundled Ollama adapter.
- No default tests, CI jobs, Docker API smoke checks, or quickstart commands require Ollama.
- The docs explain how local Ollama differs from hosted APIs, local fallback, and mock mode.
- The issue can be extended later into real local-endpoint smoke tests with explicit environment flags.

Suggested labels:

- `provider-gateway`
- `developer-experience`
- `local-models`
- `release`
