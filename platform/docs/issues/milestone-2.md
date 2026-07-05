# Milestone 2 Issue Tickets: Observability And Guardrails

Milestone 2 strengthens the platform signal around operational visibility, validation, and review routing.

## 1. Expand Trace Store Queries

Purpose:
Make the trace database useful for platform-level inspection rather than only single-call persistence.

Tasks:

- Add a query for recent traces.
- Add aggregate metrics by provider and model.
- Add failure rate.
- Add validation failure rate.
- Keep SQLite as the local MVP storage layer.

Acceptance criteria:

- `/metrics` includes aggregate request, latency, cost, and failure metrics.
- Trace store tests cover multiple rows.
- Metrics remain deterministic in tests.
- Query methods have clear return shapes.

Suggested labels:

- `enhancement`
- `observability`
- `mvp`

## 2. Improve Guardrail Outcomes

Purpose:
Represent validation as a routing decision, not only a boolean pass/fail result.

Tasks:

- Add status values: `accepted`, `needs_review`, and `rejected`.
- Keep Pydantic schema validation.
- Keep simple PII detection.
- Map invalid JSON or schema failures to `rejected`.
- Map PII or risky content to `needs_review`.
- Update tests and examples.

Acceptance criteria:

- PII input routes to `needs_review`.
- Invalid JSON routes to `rejected`.
- Valid non-sensitive output routes to `accepted`.
- Trace metadata captures the guardrail outcome.

Suggested labels:

- `enhancement`
- `guardrails`
- `observability`
- `mvp`

## 3. Add Public-Safe Synthetic Data Review

Purpose:
Ensure examples are safe to publish and easy to explain in interviews or portfolio review.

Tasks:

- Review fixtures for synthetic-only data.
- Add a public-safe data note to the README or docs.
- Avoid real company, customer, government, or proprietary process details.
- Add tests or review checklist coverage where practical.

Acceptance criteria:

- No realistic private identifiers are present in fixtures.
- README states examples are synthetic.
- Evals remain deterministic.
- The public-safe stance is visible without overexplaining.

Suggested labels:

- `docs`
- `guardrails`
- `mvp`

## 4. Final QA And Milestone Approval

Purpose:
Confirm Milestone 2 improves observability and guardrails without adding unnecessary complexity.

Tasks:

- Run tests and linting.
- Verify trace metrics across multiple calls.
- Verify guardrail routing for accepted, needs-review, and rejected outcomes.
- Review public-safe examples and docs.
- Confirm README and architecture docs still match implementation.
- Confirm no private planning files, trace DBs, or generated artifacts are tracked.

Acceptance criteria:

- `pytest` passes.
- `ruff check .` passes.
- Observability smoke checks pass.
- Guardrail outcome smoke checks pass.
- Milestone 2 completion notes are added to the roadmap or release notes.

Suggested labels:

- `qa`
- `observability`
- `guardrails`
- `release`
