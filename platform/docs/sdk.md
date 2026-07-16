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

The initial SDK facade intentionally exposes only stable construction and
metadata:

- `Blacklight.mock(...)`
- `Blacklight.from_settings(...)`
- `Blacklight.from_provider(...)`
- `client.provider_source`
- `client.provider_name`
- `client.model`
- `client.trace_db_path`

`provider_source` explains how the provider entered Blacklight:

- `mock`: deterministic demo/test mode
- `injected`: built from runtime settings such as `LLM_PROVIDER=injected`
  and `LLM_PROVIDER_ADAPTER=custom`
  or supplied directly by SDK code

`provider_name` explains what actually ran, such as `mock`, `openai`,
`ollama`, `lm-studio`, or a private provider name. Keeping these separate avoids
mistaking a user-owned provider name for a value that the settings factory knows
how to construct.

Workflow, trace, eval, provider-status, and managed-agent clients are planned in
the later Milestone 9 issues. Until those land, applications should treat
`blacklight.sdk.Blacklight` as the stable construction root rather than reaching
through it to internal storage helpers.
