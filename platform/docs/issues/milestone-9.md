# Milestone 9 Issue Tickets: Formal Blacklight SDK

Milestone 9 turns Blacklight's internal Python modules into a stable, documented SDK surface. The goal is that a developer can embed Blacklight in another Python application without depending on internal module paths or losing the platform's control-plane metadata.

The SDK should preserve the same product promise as the CLI, API, and console:

- mock-provider-first usage
- explicit provider configuration
- traceable workflow and agent runs
- validation, guardrail, and review outcomes in returned objects
- stable typed result models
- no hidden live provider calls
- public-safe examples and tests

Published GitHub issues:

- [#124 Add Formal SDK Facade](https://github.com/tserd-io/blacklight/issues/124)
- [#125 Add SDK Workflow Runner](https://github.com/tserd-io/blacklight/issues/125)
- [#126 Add SDK Trace, Eval, And Provider Clients](https://github.com/tserd-io/blacklight/issues/126)
- [#127 Add SDK Managed-Agent Surfaces](https://github.com/tserd-io/blacklight/issues/127)
- [#128 Add SDK Documentation And Examples](https://github.com/tserd-io/blacklight/issues/128)
- [#130 Add SDK Contract Tests](https://github.com/tserd-io/blacklight/issues/130)
- [#129 Milestone 9 Final QA And Approval](https://github.com/tserd-io/blacklight/issues/129)

## Candidate. Add Formal SDK Facade

Purpose:
Create the public `blacklight.sdk` package and a top-level `Blacklight` client facade.

Tasks:

- Add `platform/src/blacklight/sdk/`.
- Export `Blacklight` from `blacklight.sdk`.
- Add `Blacklight.mock(...)` for no-key local usage.
- Add `Blacklight.from_settings(...)` for configured runtime usage.
- Add `Blacklight.from_provider(...)` for explicit provider injection.
- Keep the SDK as a facade over existing workflow, provider, trace, and eval code.
- Avoid exposing unstable internal storage helpers as public API.

Acceptance criteria:

- `from blacklight.sdk import Blacklight` works.
- `Blacklight.mock(trace_db_path="traces.sqlite3")` creates a usable client without environment setup.
- SDK construction does not require OpenAI, Ollama, Docker, or live provider credentials.
- Tests cover SDK import and mock client construction.
- Public API names are documented.

Suggested labels:

- `enhancement`
- `developer`
- `usability`
- `priority:p1`

## Candidate. Add SDK Workflow Runner

Purpose:
Let SDK users run the existing ticket-classifier workflow through a stable Python API.

Tasks:

- Add `client.workflows.list()`.
- Add `client.workflows.run_ticket_classifier(...)`.
- Add `client.workflows.run("ticket_classifier", input=...)`.
- Return a typed workflow result.
- Include output, trace ID, validation result, guardrail outcome, review state, provider, model, prompt version, latency, and estimated cost where available.
- Reuse the same workflow path as CLI/API.

Acceptance criteria:

- SDK can run the ticket-classifier workflow in mock mode.
- SDK result includes `trace_id`.
- SDK result includes validation and guardrail/review state.
- SDK result can be serialized for examples/tests.
- Tests prove SDK and CLI/API paths use the same underlying behavior.

Suggested labels:

- `enhancement`
- `developer`
- `workflow`
- `priority:p1`

## Candidate. Add SDK Trace, Eval, And Provider Clients

Purpose:
Expose the core inspection surfaces that make Blacklight a workflow control plane, not just a workflow runner.

Tasks:

- Add `client.traces.list(...)`.
- Add `client.traces.show(trace_id)`.
- Add `client.evals.run(...)`.
- Add `client.evals.list(...)`.
- Add `client.evals.show(eval_run_id)`.
- Add `client.evals.compare(...)` if the existing comparison API is stable enough.
- Add `client.providers.health()`.
- Add `client.providers.status()` or `client.providers.list()` using existing provider-readiness logic.

Acceptance criteria:

- SDK users can run a workflow, inspect its trace, and run or view eval evidence without leaving Python.
- Trace/eval/provider SDK calls use the existing storage and readiness logic.
- Missing trace/eval IDs return clear typed errors or documented exceptions.
- Tests cover mock-mode trace and eval access.

Suggested labels:

- `enhancement`
- `observability`
- `evals`
- `provider-gateway`
- `priority:p1`

## Candidate. Add SDK Managed-Agent Surfaces

Purpose:
Expose managed-agent inspection and agent-run execution through the SDK without flattening governance metadata.

Tasks:

- Add `client.agents.list()`.
- Add `client.agents.show("ticket_classifier_agent")`.
- Add `client.agents.run("ticket_classifier_agent", input=...)`.
- Return typed agent definitions and run results.
- Preserve domain and range fields.
- Preserve `context`, `insight`, `suggested_action`, and `final_action` in run result structures when available.
- Include run ID, trace ID, validation result, guardrail outcome, review/touch decision, and eval evidence links where available.

Acceptance criteria:

- SDK can inspect `ticket_classifier_agent`.
- SDK can run `ticket_classifier_agent` in mock mode.
- Agent SDK responses expose domain/range metadata.
- Agent SDK responses expose domain-to-range trace references.
- Tests cover accepted, rejected, and review-routed run outcomes where fixtures exist.

Suggested labels:

- `enhancement`
- `managed-agents`
- `developer`
- `priority:p1`

## Candidate. Add SDK Documentation And Examples

Purpose:
Make the SDK discoverable and easy to trust from the README and docs.

Tasks:

- Add an SDK section to the README or a dedicated SDK guide.
- Include a copy-pasteable mock-mode example.
- Include an example that runs a workflow and prints `trace_id`, validation status, and guardrail outcome.
- Include an agent example if agent-run SDK support lands in this milestone.
- Explain how SDK usage maps to equivalent CLI and API calls.
- Explain where secrets belong for live provider use.

Acceptance criteria:

- A developer can copy the SDK example and run it without a live provider key.
- Docs show the equivalent CLI command for the SDK example.
- Docs explain that `.env` is private and `user.env` is app-editable.
- Public examples use synthetic input only.

Suggested labels:

- `docs`
- `developer`
- `usability`
- `priority:p1`

## Candidate. Add SDK Contract Tests

Purpose:
Protect the SDK as a stable public surface before other applications depend on it.

Tasks:

- Add tests for SDK import paths.
- Add tests for `Blacklight.mock()`.
- Add tests for workflow run result fields.
- Add tests for trace/eval/provider SDK surfaces.
- Add tests for managed-agent SDK surfaces if included.
- Add a small public API compatibility check or snapshot where practical.
- Ensure default tests require no OpenAI key, Ollama runtime, Docker, or model downloads.

Acceptance criteria:

- SDK tests pass in mock mode.
- SDK tests run in normal CI without secrets.
- Breaking public SDK import paths fails tests.
- Result models include trace and guardrail/review metadata.

Suggested labels:

- `test`
- `developer`
- `ci`
- `priority:p1`

## Candidate. Milestone 9 Final QA And Approval

Purpose:
Verify that the SDK milestone is complete, documented, and safe to build on.

Tasks:

- Run linting.
- Run the full test suite.
- Run SDK import smoke checks.
- Run SDK mock workflow smoke checks.
- Run SDK trace/eval/provider smoke checks.
- Run SDK managed-agent smoke checks if included.
- Confirm no live provider key is required for normal tests.
- Confirm `.env` remains ignored and no secrets are committed.
- Confirm README/docs examples are public-safe and copy-pasteable.
- Confirm CLI/API/SDK parity is documented for the main example.

Acceptance criteria:

- All required checks pass or documented local limitations are recorded.
- SDK examples work in mock mode.
- Public docs do not claim live-provider support is required.
- Final approval confirms Milestone 9 is ready to close.

Suggested labels:

- `qa`
- `docs`
- `release`
- `priority:p0`
