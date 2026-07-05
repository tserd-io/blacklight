# Release Notes

## v0.1.0 - CLI-Ready MVP

This release prepares `llm-platform-starter` as a CLI-ready, developer-operable portfolio project. It demonstrates the shared platform layer around an LLM workflow without requiring live provider credentials, private data, or a frontend.

### Included

- `llm-platform` CLI entry point for health checks, classification, evals, metrics, prompts, traces, and session history
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
llm-platform health
llm-platform eval run --trace-db-path traces.sqlite3 --session-id release-smoke
```

Docker smoke testing is supported when Docker is available:

```bash
docker build -t llm-platform-starter .
docker run --rm -p 8000:8000 llm-platform-starter
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
- `llm-platform health`
- `llm-platform classify --trace-db-path .tmp\milestone4-final-qa.sqlite3 --session-id m4-final-cli`
- `llm-platform eval run --trace-db-path .tmp\milestone4-final-qa.sqlite3 --session-id m4-final-eval`
- `llm-platform metrics --trace-db-path .tmp\milestone4-final-qa.sqlite3`
- `llm-platform session show m4-final-cli --trace-db-path .tmp\milestone4-final-qa.sqlite3`
- FastAPI `/health` smoke check
- FastAPI `/classify-ticket` smoke check
- Docker image build for `llm-platform-starter`
- Docker container `/health` smoke check
- internal Markdown link scan
- `git diff --check`
- `plans/` ignore check
- GitHub Actions CI on the release branch

Documented limitation:

- Ollama runtime smoke testing was not run as part of this release gate because it requires downloading local model weights. The release includes Ollama configuration and provider adapter support for opt-in local-model testing.

Tag status:

- `v0.1.0` was not created during this branch QA pass. Create the tag only after final human approval.
