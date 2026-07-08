# Release Notes

## v0.1.0 - CLI-Ready MVP

This release prepares `blacklight` as a CLI-ready, developer-operable portfolio project. It demonstrates the shared platform layer around an LLM workflow without requiring live provider credentials, private data, or a frontend.

### Included

- `blacklight` CLI entry point for health checks, classification, evals, metrics, prompts, traces, and session history
- FastAPI service for the ticket-classification workflow
- deterministic mock provider for local development, CI, and public-safe demos
- optional OpenAI provider and custom provider import path for real provider experiments
- prompt registry with versioned JSON templates and comparison metadata
- Pydantic validation and guardrail routing into `accepted`, `needs_review`, and `rejected`
- retry, timeout, per-session rate limiting, and durable SQLite idempotency support
- SQLite trace storage with latency, tokens, estimated cost, provider/model, validation, guardrail, failure, session, and eval-run fields
- persisted eval run and case metrics linked back to trace records
- Dockerfile for API smoke testing in mock mode
- documentation for architecture, provider configuration, eval methodology, failure modes, tradeoffs, cost ownership, and workflow extension
- public-safe synthetic examples and fixtures

### Operating Defaults

- Default provider: `mock`
- Default model: `mock-ticket-classifier`
- Default trace database: `traces.sqlite3`
- No API key required for quickstart, tests, CI, Docker smoke checks, or mock-mode CLI/API use

### Verification Targets

The release branch should pass:

```bash
pip install -e ".[dev,api]"
ruff check .
pytest
blacklight health
blacklight eval run --trace-db-path traces.sqlite3 --session-id release-smoke
```

Docker smoke testing is supported when Docker is available:

```bash
docker build -t blacklight .
docker run --rm -p 8000:8000 blacklight
curl http://127.0.0.1:8000/health
```

### Out Of Scope

- business-user desktop UI
- required local model runtime
- live provider smoke tests in default CI
- production auth, RBAC, and multi-tenant policy controls
- managed trace storage, warehouse export, or OpenTelemetry integration
- v0.1 tag creation before final release approval

### Tagging Note

Create the `v0.1.0` tag only after final QA and release approval confirm that tests, linting, CLI/API/eval smoke checks, Docker smoke checks where available, public docs, and GitHub Actions are ready.

### Final QA Record

Milestone 4 final QA was run on July 5, 2026 for the CLI-ready release branch.

Passed checks:

- `ruff check .`
- `pytest`
- `blacklight health`
- `blacklight classify --trace-db-path .tmp\milestone4-final-qa.sqlite3 --session-id m4-final-cli`
- `blacklight eval run --trace-db-path .tmp\milestone4-final-qa.sqlite3 --session-id m4-final-eval`
- `blacklight metrics --trace-db-path .tmp\milestone4-final-qa.sqlite3`
- `blacklight session show m4-final-cli --trace-db-path .tmp\milestone4-final-qa.sqlite3`
- FastAPI `/health` smoke check
- FastAPI `/classify-ticket` smoke check
- internal Markdown link scan
- `git diff --check`
- `plans/` ignore check
- GitHub Actions CI on the release branch

Documented limitation:

- Docker was not available on the local QA machine, so Docker image and Ollama runtime smoke checks were not run locally. The release includes Docker and Ollama configuration for environments where Docker is installed.

Tag status:

- `v0.1.0` was not created during this branch QA pass. Create the tag only after final human approval.

### Milestone 5 Final QA Record

Milestone 5 final QA was run on July 5, 2026 for the self-explaining console and guided-demo branch.

Passed checks:

- `ruff check .`
- `pytest`
- `blacklight health`
- `blacklight seed demo-data --trace-db-path .tmp\milestone5-final-qa.sqlite3`
- `blacklight demo --verbose --trace-db-path .tmp\milestone5-final-qa.sqlite3 --session-id m5-final-demo`
- `blacklight session show m5-final-demo --trace-db-path .tmp\milestone5-final-qa.sqlite3`
- `blacklight trace show seed-demo:billing-success --trace-db-path .tmp\milestone5-final-qa.sqlite3`
- `blacklight eval show seed-demo-eval --trace-db-path .tmp\milestone5-final-qa.sqlite3`
- `blacklight prompts show ticket_classifier`
- focused console API tests for dashboard state, workflow run, console surfaces, and CLI affordances
- `git diff --check`

Confirmed behavior:

- First-run guided demo works in mock mode.
- Seeded demo state creates linked workflow runs, traces, eval cases, and prompt versions.
- Dashboard, workflow, run, trace, eval, prompt, provider, review queue, and settings API payloads expose copy-friendly CLI equivalents.
- No live provider key is required for the default console/demo path; `blacklight health` reported `provider=mock`, `openai_configured=false`, and `custom_provider_configured=false`.

Documented limitation:

- Browser click-through was verified through console/API regression coverage rather than a live browser automation pass on this branch.

### Milestone 6 Final QA Record

Milestone 6 final QA was run on July 6, 2026 for the business-user productization branch.

Passed checks:

- `ruff check .`
- `pytest`
- `blacklight health`
- `blacklight demo --trace-db-path .tmp\milestone6-final-qa.sqlite3 --session-id m6-final-demo`
- `blacklight local-model status`
- FastAPI console smoke checks for `/api/console/first-run`, `/api/console/dashboard`, and `/api/console/local-model`
- tracked-file hygiene scan for private env files, generated caches, SQLite traces, local model artifacts, and private plans
- `git diff --check`

Confirmed behavior:

- App-shell packaging assumptions are captured in `packaging/app-shell.json` and covered by regression tests.
- First-run setup explains demo, hosted provider, and local model choices without requiring a user to edit environment files.
- Hosted provider keys remain private environment settings rather than app-editable `user.env` values.
- Local model management reports runtime readiness, installed-model state, fallback status, and recovery commands without bundling model weights.
- Console, CLI, API, eval, trace, and review surfaces remain covered by the regression suite.

Documented limitation:

- Live Docker/Ollama model installation was not required for this QA pass. The branch verifies local model configuration and status behavior while leaving model downloads as an opt-in environment-specific step.

### Milestone 7 Final QA Record

Milestone 7 final QA was run on July 8, 2026 for the managed-agents foundation branch.

Passed checks:

- `ruff check .`
- `pytest`
- `git diff --check`
- `blacklight agents list`
- `blacklight agents show ticket_classifier_agent`
- `blacklight agents show ticket_classifier_agent --json`
- `blacklight health`
- FastAPI TestClient smoke checks for `/api/agents`, `/api/agents/ticket_classifier_agent`, `/console/agents`, and `/console/agents/ticket_classifier_agent`

Confirmed behavior:

- `ticket_classifier_agent` loads as the first packaged managed agent.
- CLI output shows domain, governed range, prompt versions, review requirements, guardrail enforcement, and domain-to-range traceability.
- API profile payload exposes domain, `governed_range`, related workflow, prompt versions, eval links, trace links, review policy, domain-to-range trace contract, and CLI commands.
- Console profile surfaces link to prompts, evals, traces, review queue, workflows, and demo run.
- Docs explain workflow vs managed agent vs future graph node, inspectable-before-editable design, graph-readiness, non-goals, and safety constraints.
- Default runtime remains `provider=mock`, with `openai_configured=false` and no live provider key required.

Documented limitation:

- Milestone 7 remains intentionally read-only. Agent editing, promotion, graph execution, and managed-agent run behavior are deferred to later milestones.
