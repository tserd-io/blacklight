# Milestone 4 Issue Tickets: Packaging And Release

Milestone 4 prepares the project for public presentation and a clean v0.1 release.

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
Create a clean publish point for the portfolio project.

Tasks:

- Confirm README quickstart.
- Confirm tests and linting.
- Confirm ignored private plans.
- Add release notes.
- Tag the release.

Acceptance criteria:

- Working tree contains only intended public files.
- `plans/` is ignored.
- Release notes describe the MVP clearly.
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
