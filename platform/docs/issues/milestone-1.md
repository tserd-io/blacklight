# Milestone 1 Issue Tickets: Runnable MVP

Milestone 1 focuses on making the project easy to run, inspect, and trust from a fresh clone. These tickets are scoped so each can be implemented independently.

## 1. Add CLI Entry Points For Platform Workflows

Purpose:
Expose the platform through simple commands, not only Python modules, so the MVP workflow is easy to demonstrate and inspect.

Tasks:

- Add a console script in `pyproject.toml`.
- Add `blacklight classify`.
- Add `blacklight eval`.
- Add `blacklight metrics`.
- Add `blacklight health`.
- Add `blacklight prompts list`.
- Add `blacklight prompts show`.
- Add `blacklight trace list`.
- Add `blacklight trace show`.
- Keep command output JSON-friendly.

Acceptance criteria:

- `blacklight classify --subject "Refund" --body "Duplicate charge"` returns valid JSON.
- `blacklight eval` returns an eval summary.
- `blacklight metrics` works against the configured SQLite trace DB.
- `blacklight health` reports local runtime configuration without requiring live API keys.
- `blacklight prompts list` and `blacklight prompts show ticket_classifier` expose prompt registry metadata.
- `blacklight trace list` and `blacklight trace show <request_id>` expose recent trace records from SQLite.
- Tests cover the CLI commands without requiring live API keys.

Suggested labels:

- `enhancement`
- `developer-experience`
- `mvp`

## 2. Add Provider Factory

Purpose:
Make provider selection explicit, configurable, and production-shaped.

Tasks:

- Add a provider factory module.
- Support `mock` by default.
- Support `openai` only when configured.
- Support user-owned providers through a custom import path.
- Raise clear errors for unknown providers or missing API key.
- Update API and example flows to use the factory where appropriate.

Acceptance criteria:

- Tests cover mock provider creation.
- Tests cover custom provider creation.
- Tests cover unsupported provider errors.
- OpenAI provider is never required for CI.
- Configuration remains simple for local mock-mode usage.

Suggested labels:

- `enhancement`
- `provider-gateway`
- `mvp`

## 3. Add Retry And Timeout Wrapper

Purpose:
Show minimal platform reliability behavior around provider calls without turning the MVP into a large framework.

Tasks:

- Add basic retry and timeout settings.
- Add configurable per-session rate limiting.
- Wrap provider calls with retry handling.
- Reuse an idempotency key across retry attempts.
- Cache completed workflow results by idempotency key.
- Retry null, empty, or whitespace-only provider outputs before validation.
- Track provider failure categories in traces.
- Keep the mock provider deterministic.
- Document the reliability behavior in the README or tradeoffs doc.

Acceptance criteria:

- Failed provider calls record trace metadata when possible.
- Unit tests cover retry exhaustion.
- Timeout/retry defaults are visible in settings.
- Rate limit defaults are visible in settings.
- Retry attempts preserve provider request idempotency metadata.
- Repeated completed requests can return cached results without calling the provider.
- Exhausted null or empty provider outputs are traced as `provider_empty_response`.
- README explains this as a minimal reliability pattern.

Suggested labels:

- `enhancement`
- `provider-gateway`
- `observability`
- `mvp`

## 4. Improve Eval Report

Purpose:
Make evals feel like platform regression tooling rather than a one-off script.

Tasks:

- Add schema validity rate.
- Add needs-review rate.
- Add latency average and percentile metrics.
- Add token usage and estimated cost metrics.
- Add retry count and error category diagnostics.
- Add category-level accuracy breakdown.
- Store eval run and per-case metrics in SQLite with session identifiers.
- Add eval history inspection commands.
- Add JSON report output.
- Preserve per-case results.

Acceptance criteria:

- `blacklight eval` prints a JSON report with one `summary` object and per-case results.
- Summary includes accuracy, schema validity, review rate, latency, token usage, estimated cost, retry, error, and category breakdown metrics.
- Eval report includes per-case quality, latency, token, cost, retry, and error diagnostics.
- Eval metrics can be related to trace records by `session_id`, and per-case records include a future trace join key.
- `blacklight eval list` and `blacklight eval show <eval_run_id>` expose persisted eval history and related traces.
- Tests validate the report shape.
- Eval execution remains deterministic with the mock provider.

Suggested labels:

- `enhancement`
- `evals`
- `mvp`

## 5. Final QA And Milestone Approval

Purpose:
Confirm Milestone 1 is complete, coherent, and ready to build on before starting the next milestone.

Tasks:

- Run the full test suite.
- Run linting.
- Verify CLI commands work from a fresh editable install.
- Verify API health and ticket-classification flow.
- Verify eval report output is deterministic.
- Review README quickstart against the implemented commands.
- Confirm no private planning files, generated caches, trace DBs, or secrets are tracked.

Acceptance criteria:

- `pytest` passes.
- `ruff check .` passes.
- CLI smoke checks pass.
- API smoke checks pass.
- Git status contains only intended public files.
- Milestone 1 completion notes are added to the roadmap or release notes.

Suggested labels:

- `qa`
- `mvp`
- `release`
