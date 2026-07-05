# Failure Modes

LLM workflows fail in ways that ordinary request/response services often hide: malformed model output, prompt drift, provider instability, cost surprises, and unsafe automation. This project keeps those risks visible through validation, guardrail outcomes, traces, evals, and CLI/API error formatting.

The MVP does not eliminate every failure. It shows where each failure would surface and what a production system would add next.

## Guardrail Outcomes

Guardrail outcomes separate trusted automation from reviewable or rejected outputs:

- `accepted`: JSON parsed, schema validation passed, and no review signal was found.
- `needs_review`: schema validation passed, but PII detection or the model's `needs_review` flag requires human review.
- `rejected`: JSON parsing or schema validation failed, so the workflow should not trust the output.

Trace records persist the guardrail outcome alongside validation status, error category, provider, model, token counts, cost estimate, session ID, and eval run ID. That lets diagnostics distinguish hard failures from reviewable outputs.

## Operational Failure Modes

### Provider timeout or unavailable model

Signal:

- provider call raises a timeout or provider error
- trace `error_category` is `provider_timeout` or `provider_error`
- CLI/API returns a structured provider error

Current mitigation:

- provider calls use timeout and retry settings
- final failures are traced when a trace store is configured
- health output exposes provider configuration

Production extension:

- provider-specific circuit breakers
- fallback providers or fallback models
- alerting on failure rate by provider/model
- queue-based retry with dead-letter handling

### Empty, null, or malformed provider output

Signal:

- provider returns empty text or invalid JSON
- validation fails before a typed response can be trusted
- trace `error_category` is `provider_empty_response` or `validation_error`
- guardrail outcome is `rejected`

Current mitigation:

- empty provider output is retried
- Pydantic validation rejects schema mismatches
- CLI/API errors include likely cause and next step

Production extension:

- provider output sampling for debugging
- prompt/schema compatibility checks before deployment
- stricter provider response contracts
- reviewer or operator queue for repeated malformed outputs

### Schema mismatch after prompt or model changes

Signal:

- eval schema validity rate drops
- validation errors appear in per-case eval diagnostics
- trace validation status flips from passed to failed

Current mitigation:

- deterministic eval fixtures run through the same prompt/provider/guardrail path as the workflow
- prompt versions are recorded in eval reports and trace records
- prompt comparison reports require matching comparison group, output schema, and fixture

Production extension:

- deployment gates based on eval thresholds
- prompt approval workflow
- model/prompt compatibility matrix
- automatic rollback when schema validity regresses

### Reviewable content routed as automation

Signal:

- output contains PII-like content or model marks `needs_review`
- guardrail outcome is `needs_review`
- review rate changes in eval reports

Current mitigation:

- simple PII detection flags reviewable inputs or outputs
- typed outputs preserve `needs_review`
- traces and eval summaries expose review rates

Production extension:

- stronger PII and secrets detection
- policy-specific risk scoring
- human review queue integration
- audit trail for review decisions

### False confidence or wrong category

Signal:

- eval accuracy drops
- per-case eval diagnostics show expected and actual category divergence
- confidence averages or low-confidence counts change unexpectedly

Current mitigation:

- synthetic fixtures test expected categories
- eval reports include accuracy, confidence, category breakdown, and per-case diagnostics
- low-confidence cases can be counted and reviewed

Production extension:

- larger domain-specific eval suites
- rubric scoring for non-classification workflows
- sampling of production outputs for human review
- feedback loops from reviewer corrections

### Cost or latency regression

Signal:

- trace metrics show higher average latency or estimated cost
- eval reports show token, cost, latency, and retry deltas
- prompt comparison reports show token-per-case or latency changes

Current mitigation:

- traces record latency, input tokens, output tokens, and estimated cost
- metrics group performance by provider, model, provider/model pair, and guardrail outcome
- eval summaries include latency percentiles, token totals, retry counts, and cost estimates

Production extension:

- budget alerts
- latency SLOs
- provider/model cost dashboards
- cost projection for scheduled live runs
- adaptive routing by cost, latency, or quality threshold

### Duplicate or repeated side effects

Signal:

- repeated requests share an idempotency key
- a duplicate request is already in progress
- repeated retries would otherwise emit duplicate provider work

Current mitigation:

- provider retries reuse a stable idempotency key
- completed workflow results can be cached by idempotency key in SQLite
- duplicate in-progress keys fail clearly

Production extension:

- external idempotency store for multi-host deployments
- request-level dedupe at API gateway
- idempotency dashboards for repeated callers
- replay tooling for failed workflows

### Rate-limit pressure from one session

Signal:

- one user/session submits requests faster than the configured window
- provider calls are rejected before overloading the workflow path

Current mitigation:

- configurable per-session rate limits
- session IDs are recorded with traces and eval runs

Production extension:

- distributed rate limiting across processes
- per-user quotas
- tenant-aware throttling
- graceful retry-after responses

### Prompt version drift between environments

Signal:

- trace `prompt_version` differs across environments
- eval reports reference a different prompt version than production traces
- prompt comparison report shows a regression before deployment

Current mitigation:

- prompt versions are stored in JSON and reviewed with code
- active prompt version is loaded through the registry
- traces and eval runs persist prompt IDs and versions

Production extension:

- environment-specific prompt promotion
- signed prompt artifacts
- deployment checks that pin prompt version
- change approvals for prompt metadata and templates

## How To Debug

Start from the surface that saw the failure:

- CLI/API error: inspect `category`, `likely_cause`, and `next_step`.
- One bad request: run `llm-platform trace show <request_id>`.
- Pattern across requests: run `llm-platform metrics`.
- Eval regression: run `llm-platform eval show <eval_run_id>`.
- Prompt regression: run `llm-platform eval compare --baseline-version <n> --candidate-version <n>`.

The intended diagnostic path is session to eval run to case to provider trace. That keeps the user from guessing whether a failure came from prompt wording, provider behavior, validation, guardrails, or operating limits.
