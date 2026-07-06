# Provider Configuration

The provider factory supports three paths:

- `mock` for deterministic local development and CI.
- `openai` for the optional built-in OpenAI adapter.
- `custom` for user-owned adapters loaded from an import path.

The custom path is the recommended way to try local LLM runtimes without adding runtime-specific dependencies to this starter project.

## Custom Provider Contract

A custom provider must implement `LLMProvider`:

```python
from blacklight.models import ProviderRequest, ProviderResponse
from blacklight.providers.base import LLMProvider


class MyProvider(LLMProvider):
    name = "my-provider"

    def complete(self, request: ProviderRequest) -> ProviderResponse:
        return ProviderResponse(
            text="{}",
            provider=self.name,
            model=request.model,
        )
```

Then configure the import path:

```bash
set LLM_PROVIDER=custom
set LLM_CUSTOM_PROVIDER=my_project.providers:MyProvider
```

`LLM_CUSTOM_PROVIDER` can point to an `LLMProvider` subclass, an `LLMProvider` instance, or a zero-argument factory returning an `LLMProvider`.

## Local LLM Endpoint Example

For a local model server, keep the platform adapter thin. The local runtime can be Ollama, LM Studio, llama.cpp, vLLM, Transformers, or a private localhost service. The platform only needs a normalized `ProviderResponse`.

This example shows the shape for an Ollama-style HTTP endpoint:

```python
import json
from urllib import request as urlrequest

from blacklight.models import ProviderRequest, ProviderResponse
from blacklight.providers.base import LLMProvider


class LocalHTTPProvider(LLMProvider):
    name = "local-http"
    endpoint = "http://localhost:11434/api/generate"

    def complete(self, request: ProviderRequest) -> ProviderResponse:
        payload = json.dumps(
            {
                "model": request.model,
                "prompt": request.prompt,
                "stream": False,
            }
        ).encode("utf-8")
        http_request = urlrequest.Request(
            self.endpoint,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlrequest.urlopen(http_request, timeout=60) as response:
            data = json.loads(response.read().decode("utf-8"))

        return ProviderResponse(
            text=data["response"],
            provider=self.name,
            model=request.model,
            metadata={"endpoint": self.endpoint},
        )
```

Configure it like this:

```bash
set LLM_PROVIDER=custom
set LLM_MODEL=llama3.1
set LLM_CUSTOM_PROVIDER=my_project.local_provider:LocalHTTPProvider
```

Then run the same platform surface:

```bash
blacklight classify --subject "Login error" --body "The export page fails after login."
```

## Provider Smoke Tests

Provider configuration smoke tests live in `tests/test_provider_configuration_smoke.py`.

The mock provider smoke test runs in normal CI and requires no secrets:

```bash
pytest tests/test_provider_configuration_smoke.py
```

Live provider smoke tests are opt-in and skip with a clear reason unless their flags and configuration are present.

OpenAI:

```bash
set RUN_OPENAI_PROVIDER_SMOKE=1
set OPENAI_API_KEY=...
set LLM_MODEL=gpt-4o-mini
pytest tests/test_provider_configuration_smoke.py
```

Custom provider:

```bash
set RUN_CUSTOM_PROVIDER_SMOKE=1
set LLM_CUSTOM_PROVIDER=my_project.providers:MyProvider
set LLM_MODEL=my-model
pytest tests/test_provider_configuration_smoke.py
```

Local endpoint provider:

```bash
set RUN_LOCAL_PROVIDER_SMOKE=1
set LLM_CUSTOM_PROVIDER=my_project.local_provider:LocalHTTPProvider
set LLM_MODEL=llama3.1
pytest tests/test_provider_configuration_smoke.py
```

The local endpoint path uses the same `custom` provider contract, so Ollama, LM Studio, llama.cpp, vLLM, Transformers, or a private localhost service can be smoke-tested without changing application code.

## Ollama Runtime Configuration

The repository includes a lightweight Ollama configuration for local experiments. It does not vendor an Ollama binary or model weights into the repo. Docker downloads the runtime image when you start it, and `ollama pull` downloads the selected model into the local Docker volume.

Start Ollama:

```bash
docker compose -f docker-compose.ollama.yml up -d
```

Download a local model:

```bash
docker compose -f docker-compose.ollama.yml exec ollama ollama pull llama3.1
```

Point the platform at the bundled Ollama adapter:

```bash
set LLM_PROVIDER=custom
set LLM_CUSTOM_PROVIDER=blacklight.providers.ollama_provider:OllamaProvider
set LLM_MODEL=llama3.1
set OLLAMA_BASE_URL=http://localhost:11434
```

Then run the normal CLI path:

```bash
blacklight classify --subject "Login error" --body "The export page fails after login."
```

Inspect local model readiness:

```bash
blacklight local-model status
```

The local model status surface is also available at `/console/local-model` and
`/api/console/local-model`. It reports:

- `unavailable` when local mode is not selected, Ollama is unreachable, or the model is missing
- `loading` when the runtime does not respond before the readiness timeout
- `ready` when Ollama is reachable and the configured model is installed

Blacklight does not bundle model weights. That keeps the package small, avoids unclear
redistribution/licensing risk, and lets each installation choose a model appropriate for its
hardware. A business-user installer could later offer a first-run download flow for a recommended
small model, but it should show disk usage, license terms, update behavior, and expected
performance before downloading.

Local fallback is represented separately from the active provider. If Ollama is reachable and the
selected local model is installed, the local model status reports fallback as available even when
the active provider is still mock or hosted. That gives a future packaged app a clear path to use a
local model when hosted service is unavailable or when privacy/control mode is selected.

Hosted provider credentials stay private. Keep keys such as `OPENAI_API_KEY` in `.env`, shell
environment variables, or deployment secrets; the app-editable `user.env` path is for non-secret
settings such as provider choice, model name, local endpoint URL, and reliability limits.

This is a local-provider configuration path, not the default release path. CI and quickstart still use `mock` so they do not require Docker, Ollama, model downloads, GPU access, or live provider credentials.
