# Eval Methodology

The MVP uses small, synthetic JSONL fixtures to test task-specific behavior. Each fixture defines an input ticket and an expected category.

The current eval measures exact category accuracy, schema validity, review rate, latency, token usage, estimated cost, retry counts, and error categories. This keeps the MVP compact while making regressions easier to diagnose when a prompt, provider, or model changes.

Each report includes a `summary` object and per-case diagnostics. The summary captures aggregate quality and runtime signals such as accuracy, schema validity rate, total tokens, total estimated cost, average retries per case, latency percentiles, and category-level accuracy. Each case preserves the expected and actual category along with pass/fail status, validation state, review flag, confidence, latency, token counts, cost, retry count, and any error category.

Eval runs can be persisted to the same SQLite database used for traces. The `eval_runs`, `eval_cases`, and `traces` tables store `session_id` so reports can be grouped with trace traffic from the same user, workflow, or CI job. Each eval case also stores a deterministic `trace_request_id` in the form `<eval_run_id>:<case_id>`, and eval execution writes a matching trace row with that value as `traces.request_id`.

Logical connection paths:

- `eval_runs.session_id` -> `traces.session_id` for workflow-level comparisons.
- `eval_cases.session_id` -> `traces.session_id` for case cohorts inside a session.
- `eval_cases.trace_request_id` -> `traces.request_id` for direct per-case trace joins.
- `eval_runs.eval_run_id` -> `traces.eval_run_id` for all traces emitted by an eval run.
- `prompt_id`, `prompt_version`, `provider`, and `model` for comparing eval metrics to matching trace slices.

Prompt-version comparisons are scoped by prompt registry metadata. A prompt version can be compared with another version only when they share the same `comparison_group`, `output_schema`, and `eval_fixture`. This keeps regression reports tied to prompts that perform the same task and produce the same shape of output instead of comparing unrelated prompt families.

Use:

```bash
llm-platform eval compare --baseline-version 1 --candidate-version 2
```

The report includes summary deltas for accuracy, schema validity, review rate, latency, estimated cost, and token use, plus per-case before/after fields and deltas.

Future versions can add:

- provider/model comparisons
- richer review-reason categories
- rubric scoring for summarization or extraction tasks
- human review sampling
