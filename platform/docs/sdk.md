# Blacklight SDK

The public SDK starts at `blacklight.sdk`. It is the supported Python embedding
surface for applications that want to construct Blacklight without importing
internal modules directly.

```python
from blacklight.sdk import Blacklight

client = Blacklight.mock(trace_db_path="traces.sqlite3")

print(client.provider_name)
print(client.provider_source)
print(client.model)
print(client.trace_db_path)
```

`Blacklight.mock(...)` is the safest fresh-clone path. It uses the deterministic
mock provider and does not read `.env`, `user.env`, OpenAI credentials, Ollama,
Docker, or any live provider configuration.

The SDK also exposes workflow execution through `client.workflows`:

```python
from blacklight.sdk import Blacklight

client = Blacklight.mock(trace_db_path="traces.sqlite3")

result = client.workflows.run_ticket_classifier(
    subject="Invoice refund request",
    body="The customer was charged twice and needs a refund.",
    session_id="demo-session",
)

print(result.output.category)
print(result.trace_id)
print(result.review.state)
```

For known operational failures, workflow calls return a structured failed result
with an `error` object that a user-facing application can render directly:

```python
result = client.workflows.run_ticket_classifier(
    subject="Invoice refund request",
    body="The customer was charged twice and needs a refund.",
)

if result.run_status == "failed" and result.error:
    print(result.error.message)
    print(result.error.likely_cause)
    print(result.error.next_step)
```

Blacklight keeps a hybrid boundary for SDK ergonomics:

- Provider/runtime/validation failures return `WorkflowResult(run_status="failed")`.
- Programmer mistakes, such as an unsupported workflow ID or invalid input shape,
  raise normal Python exceptions.
- `result.trace` is present when the run reached durable trace writing. If a
  failure happens before evidence can be written, `result.trace` and
  `result.trace_id` may be `None`.
- SDK error objects extend `TypedError`, so workflow, agent-run, and future SDK
  surfaces share `category`, `message`, `likely_cause`, and `next_step`.

Use the generic workflow runner when a host application wants to choose the
workflow by ID:

```python
result = client.workflows.run(
    "ticket_classifier",
    input={
        "subject": "Login loop",
        "body": "The user hits an API error after signing in.",
    },
)
```

After a workflow runs, inspect traces without leaving Python:

```python
trace = client.traces.show(result.trace_id)

print(trace.trace["provider"])
print(trace.eval_evidence["suite_name"])
```

Run and inspect eval evidence from the same SDK client:

```python
eval_result = client.evals.run(session_id="demo-eval")
eval_run_id = eval_result.report["eval_run_id"]

print(client.evals.list().eval_runs)
print(client.evals.show(eval_run_id).eval_run["summary"])
```

Prompt-version comparison uses fresh mock providers automatically in mock mode.
Injected providers must supply a factory so baseline and candidate runs do not
share mutable provider state:

```python
comparison = client.evals.compare(
    baseline_version=1,
    candidate_version=2,
    provider_factory=MyProvider,
)
```

Provider readiness is also available through the SDK:

```python
print(client.providers.health().model)
print(client.providers.status().providers["mock"]["ready"])
print(client.providers.status(include_local_probe=False).local_model["status"])
```

`client.providers.status()` probes the configured local model endpoint by
default. Use `include_local_probe=False` when a host application only wants a
cheap configuration snapshot.

Managed-agent inspection and runs are exposed through `client.agents`:

```python
agent = client.agents.show("ticket_classifier_agent")

run = client.agents.run(
    "ticket_classifier_agent",
    input={
        "subject": "Invoice refund request",
        "body": "The customer was charged twice and needs a refund.",
        "session_id": "demo-session",
        "context": {"source": "demo"},
        "suggested_action": {"queue": "billing"},
    },
)

print(agent.governed_range["output_schema"])
print(run.agent_run_id)
print(run.trace_id)
print(run.domain_to_range["review"]["state"])
```

Agent runs return the same durable run envelope used by the CLI and console API.
They include agent metadata, domain/range snapshots, validation, guardrail,
review routing, eval evidence, the linked trace ID, and optional `run_context`
fields such as context, insight, suggested action, and final action.

The `run_context` field is also included in the domain-to-range traceability
payload. This supports minimum-trust, high-observability chains where one step
retrieves context, another creates an insight from that context, another drafts
an action from both, and a final review step decides whether to send, store, or
route the result for human review.

## Construction Paths

Use mock mode when examples, tests, or embedded demos should run without setup:

```python
client = Blacklight.mock(trace_db_path="traces.sqlite3")
```

Use explicit settings when the host application owns configuration:

```python
from blacklight.sdk import Blacklight
from blacklight.settings import Settings

client = Blacklight.from_settings(
    Settings(
        provider="mock",
        model="mock-ticket-classifier",
        trace_db_path="traces.sqlite3",
    )
)
```

Use provider injection when the host application has already created an
`LLMProvider`:

```python
from blacklight.providers.mock import MockProvider
from blacklight.sdk import Blacklight

client = Blacklight.from_provider(
    MockProvider(),
    model="mock-ticket-classifier",
    trace_db_path="traces.sqlite3",
)
```

`Blacklight.from_settings()` can also load the normal runtime configuration with
`load_settings()`. Keep live provider keys in `.env`, shell environment
variables, deployment secrets, or a secret manager. Keep app-editable non-secret
settings in `user.env`.

## Current Public Surface

The SDK facade exposes stable construction, metadata, workflow execution, and
inspection clients:

- `Blacklight.mock(...)`
- `Blacklight.from_settings(...)`
- `Blacklight.from_provider(...)`
- `TypedError`
- `client.provider_source`
- `client.provider_name`
- `client.model`
- `client.trace_db_path`
- `client.workflows.list()`
- `client.workflows.run_ticket_classifier(...)`
- `client.workflows.run("ticket_classifier", input=...)`
- `client.agents.list()`
- `client.agents.show(agent_id)`
- `client.agents.run(agent_id, input=...)`
- `client.traces.list(...)`
- `client.traces.show(trace_id)`
- `client.evals.run(...)`
- `client.evals.list(...)`
- `client.evals.show(eval_run_id)`
- `client.evals.compare(...)`
- `client.providers.health()`
- `client.providers.list()`
- `client.providers.status()`

Workflow results are typed Pydantic models. They can be serialized with
`result.model_dump(mode="json")` and include:

- output
- trace ID
- validation result
- guardrail outcome
- review state
- structured error detail for known operational failures
- provider and model
- prompt version
- latency
- token counts and estimated cost where available

Trace and eval lookups raise `SDKNotFoundError` when the requested trace or eval
run is not present in the configured trace database. This keeps missing evidence
distinct from a successful empty result.

`provider_source` explains how the provider entered Blacklight:

- `mock`: deterministic demo/test mode
- `injected`: built from runtime settings such as `LLM_PROVIDER=injected`
  and `LLM_PROVIDER_ADAPTER=custom`
  or supplied directly by SDK code

`provider_name` explains what actually ran, such as `mock`, `openai`,
`ollama`, `lm-studio`, or a private provider name. Keeping these separate avoids
mistaking a user-owned provider name for a value that the settings factory knows
how to construct.

Managed-agent run results are typed Pydantic models. They can be serialized with
`run.model_dump(mode="json")` and are intended for applications that need to
show a non-technical user what happened from session, to agent run, to trace, to
review/eval evidence without reaching into internal storage helpers.
