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

The SDK facade exposes stable construction, metadata, and the ticket-classifier
workflow runner:

- `Blacklight.mock(...)`
- `Blacklight.from_settings(...)`
- `Blacklight.from_provider(...)`
- `client.provider_source`
- `client.provider_name`
- `client.model`
- `client.trace_db_path`
- `client.workflows.list()`
- `client.workflows.run_ticket_classifier(...)`
- `client.workflows.run("ticket_classifier", input=...)`

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

`provider_source` explains how the provider entered Blacklight:

- `mock`: deterministic demo/test mode
- `injected`: built from runtime settings such as `LLM_PROVIDER=injected`
  and `LLM_PROVIDER_ADAPTER=custom`
  or supplied directly by SDK code

`provider_name` explains what actually ran, such as `mock`, `openai`,
`ollama`, `lm-studio`, or a private provider name. Keeping these separate avoids
mistaking a user-owned provider name for a value that the settings factory knows
how to construct.

Trace, eval, provider-status, and managed-agent clients are planned in later
Milestone 9 issues. Until those land, applications should treat
`blacklight.sdk.Blacklight` as the stable construction root and use the typed
workflow result instead of reaching through it to internal storage helpers.
