# Failure Modes

Important failure modes this project is designed to surface:

- Provider timeout or unavailable model
- Invalid JSON from a model
- Schema mismatch after a prompt or model change
- Low-confidence output that should route to review
- PII in source input or generated output
- Cost or latency regression
- Prompt version drift between development and production

The MVP handles a subset directly and documents the rest as production extensions.

Guardrail outcomes make those failures easier to inspect:

- `accepted`: JSON parsed, schema validation passed, and no review signal was found.
- `needs_review`: schema validation passed, but PII detection or the model's `needs_review` flag requires human review.
- `rejected`: JSON parsing or schema validation failed, so the workflow should not trust the output.

Trace records persist the guardrail outcome alongside validation status and error category, allowing diagnostics to separate hard failures from reviewable outputs.
