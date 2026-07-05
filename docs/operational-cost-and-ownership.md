# Operational Cost And Ownership

This guide shows how to estimate and own the operating cost of an automated LLM workflow. The numbers below are examples, not price commitments. Real estimates should use the provider's current pricing, the selected model, measured trace data, and the organization's support expectations.

The default `mock` provider has no provider bill. It is useful for development, CI, demos, and regression checks, but it does not estimate live provider spend, real latency, real model quality, or vendor failure behavior.

## Operating Profile

Example workload:

- 5 live-analysis runs per day
- 30 days per month
- 150 live-analysis runs per month
- 1 production request per run
- 1 retry budget per failed provider call
- 1 eval run per day to catch prompt/model regressions

The starter records the fields needed to replace assumptions with measured data:

- `provider`
- `model`
- `session_id`
- `prompt_id`
- `prompt_version`
- `latency_ms`
- `input_tokens`
- `output_tokens`
- `estimated_cost_usd`
- `error_category`
- `validation_passed`
- `guardrail_outcome`

Use `llm-platform metrics`, `llm-platform trace list`, `llm-platform trace show`, and `llm-platform session show` to review the live traces behind a cost estimate.

## Hosted Provider Estimate

Hosted API cost is usually driven by token volume:

```text
request_cost =
  (input_tokens / 1000 * input_price_per_1k) +
  (output_tokens / 1000 * output_price_per_1k)
```

Monthly production cost:

```text
monthly_production_cost =
  daily_runs *
  days_per_month *
  average_request_cost *
  (1 + retry_rate)
```

Daily eval cost:

```text
monthly_eval_cost =
  eval_runs_per_month *
  eval_cases_per_run *
  average_eval_case_cost
```

Example using `gpt-4.1-mini` pricing from the local cost helper:

- input price: `$0.0004` per 1K tokens
- output price: `$0.0016` per 1K tokens
- average production request: 2,000 input tokens and 500 output tokens
- average request cost: `$0.0016`
- retry rate: 10%
- production runs: 150 per month
- eval runs: 30 per month
- eval cases per run: 3
- average eval case: 500 input tokens and 150 output tokens
- average eval case cost: `$0.00044`

```text
production = 150 * $0.0016 * 1.10 = $0.264/month
evals = 30 * 3 * $0.00044 = $0.0396/month
example hosted total = $0.3036/month
```

That number is intentionally small because the example workload is low volume and the model is inexpensive. Costs can rise quickly when the workflow uses larger models, long documents, multi-step analysis, retries, prompt comparison, or scheduled evals with larger fixtures.

### Hosted Ownership Checks

Before shipping regular live runs, decide:

- Who owns model and provider selection?
- What is the monthly budget ceiling?
- What retry rate triggers investigation?
- What failure rate pauses automation?
- What review rate means the prompt or model is not reliable enough?
- Who approves switching models if quality, latency, or price changes?

Trace fields support these decisions:

- `estimated_cost_usd` shows measured spend by request, session, eval run, provider, and model.
- `input_tokens` and `output_tokens` explain why spend moved.
- `error_category` shows whether retries and failed calls are inflating cost.
- `guardrail_outcome` shows review volume and automation confidence.
- `prompt_version` and `model` connect cost changes to prompt/model changes.

## Local Or On-Prem Estimate

Local/on-prem inference avoids an external per-token API bill, but it still has operating cost. The cost shifts from provider invoices to hardware, electricity, maintenance, utilization, and support.

Monthly local cost:

```text
monthly_local_cost =
  hardware_depreciation_per_month +
  electricity_per_month +
  maintenance_and_support_per_month +
  hosting_or_facility_cost_per_month
```

Run-level local cost:

```text
cost_per_run =
  monthly_local_cost / monthly_successful_runs
```

Example:

- workstation or server allocation: `$1,800`
- depreciation period: 36 months
- hardware depreciation: `$50/month`
- incremental electricity: `$6/month`
- maintenance/support allocation: `$75/month`
- hosting/facility allocation: `$0/month` for an existing workstation
- successful runs: 150 per month

```text
monthly_local_cost = $50 + $6 + $75 + $0 = $131/month
cost_per_run = $131 / 150 = $0.8733/run
```

For this low-volume example, a hosted API is likely cheaper. Local inference becomes easier to justify when:

- data cannot leave the environment
- offline/private-network operation matters
- the organization already owns suitable hardware
- many workflows share the same local runtime
- predictable capacity is more important than per-token elasticity
- model quality is sufficient for the task

## Hosted API, Local Provider, Or Local Fallback

### Hosted API

Best when speed to production, model quality, and low infrastructure burden matter most.

Primary risks:

- provider outage or rate limits
- vendor pricing changes
- data-governance approval
- unbounded spend if scheduled runs or retries grow

### Local/on-prem provider

Best when control, privacy, or offline operation outweigh infrastructure complexity.

Primary risks:

- hardware underutilization
- model/runtime maintenance
- slower or lower-quality responses
- unclear support ownership
- hidden electricity, patching, and incident cost

### Local fallback

Most shippable when it is optional, visible, and degraded by design. A fallback can be appropriate when:

- hosted provider calls fail
- a spend ceiling has been reached
- sensitive data cannot leave the machine
- the workflow can tolerate lower quality or slower responses

It becomes risky when it silently changes model behavior, hides quality drops, or creates a support burden for non-technical users. Fallback behavior should be visible in traces through provider/model metadata and, in a production version, a fallback reason.

## Escalation Decisions

A responsible owner should define thresholds before automation runs regularly:

| Signal | Example threshold | Owner action |
| --- | --- | --- |
| Monthly estimated cost | 80% of budget | Review token volume, retries, scheduled evals, and model choice |
| Failure rate | More than 5% over a day | Pause automation or switch provider after triage |
| Review rate | More than 20% over a week | Revisit prompt, model, guardrails, or workflow scope |
| Validation failures | Any sustained increase | Inspect examples before allowing unattended output |
| Latency | Above workflow SLA | Consider smaller model, batching, provider change, or async processing |
| Retry rate | More than 10% | Check provider stability, timeout settings, and idempotency behavior |

These thresholds are examples. The important ownership practice is to connect every threshold to a decision: keep running, degrade to fallback, send to review, pause automation, or escalate to the provider owner.

## Practical Review Loop

For regular live analysis:

1. Run the workflow with a stable `session_id`.
2. Inspect `llm-platform session show <session_id>` for per-run cost, failures, review outcomes, and provider/model use.
3. Inspect `llm-platform metrics` for aggregate cost, latency, failure rate, and provider/model breakdowns.
4. Run evals before changing prompts or models.
5. Compare measured cost to the monthly budget and the value of the automation.
6. Record model/provider changes as operational decisions, not incidental code changes.

This is the ownership story the starter is meant to demonstrate: automation is not only whether a model call works. It is whether the team can explain the cost, risk, fallback behavior, and review path when it runs repeatedly.
