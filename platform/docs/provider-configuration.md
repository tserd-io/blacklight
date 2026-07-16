# Provider Configuration

Blacklight has one safe default and an injected-provider path:

- `mock` is deterministic local demonstration mode for development, tests, CI,
  docs, and first-run product tours.
- injected providers connect Blacklight to a hosted, local, or private model
  runtime when the user is ready to leave mock mode.

Injected providers use `LLM_PROVIDER=injected` and
`LLM_PROVIDER_ADAPTER=<adapter>`. The built-in OpenAI adapter uses
`LLM_PROVIDER_ADAPTER=openai`; user-owned adapters loaded from an import path
use `LLM_PROVIDER_ADAPTER=custom`. OpenAI is an adapter example, not the center
of the architecture. The custom path is the recommended way to try local LLM
runtimes without adding runtime-specific dependencies to this starter project.

Provider names should identify what actually ran, such as `mock`, `openai`,
`ollama`, `lm-studio`, or a private gateway name. Configuration values such as
`mock` and `injected` explain the provider mode. Adapter values such as
`openai` and `custom` explain how Blacklight constructs the injected provider.
Keeping those concepts separate makes SDK and trace output easier to understand.

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
set LLM_PROVIDER=injected
set LLM_PROVIDER_ADAPTER=custom
set LLM_PROVIDER_NAME=my-provider
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
set LLM_PROVIDER=injected
set LLM_PROVIDER_ADAPTER=custom
set LLM_PROVIDER_NAME=local-http
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

`OPENAI_API_KEY` is the clearest name for OpenAI deployments. `LLM_API_KEY`
or `API_KEY` can also be used as generic private provider-key aliases when the
selected provider needs a single API key. Keep these values in `.env`, shell
exports, deployment secrets, or a secret manager; do not put them in
console-managed `user.env`.

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

Bundled Ollama adapter:

```bash
set RUN_OLLAMA_PROVIDER_SMOKE=1
set LLM_MODEL=llama3.1
set OLLAMA_BASE_URL=http://localhost:11434
pytest tests/test_provider_configuration_smoke.py
```

This opt-in test uses `blacklight.providers.ollama_provider:OllamaProvider` directly. It is skipped in default CI and should be run only after the local Ollama runtime is started and the model is installed.

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
set LLM_PROVIDER=injected
set LLM_PROVIDER_ADAPTER=custom
set LLM_CUSTOM_PROVIDER=blacklight.providers.ollama_provider:OllamaProvider
set LLM_MODEL=llama3.1
set OLLAMA_BASE_URL=http://localhost:11434
```

Then run the normal CLI path:

```bash
blacklight classify --subject "Login error" --body "The export page fails after login."
```

The same values can be stored in `user.env` for local console-managed settings. Runtime process environment variables still take precedence, so shell exports and deployment settings can override `user.env` without editing it.

This is a local-provider configuration path, not the default release path. CI and quickstart still use `mock` so they do not require Docker, Ollama, model downloads, GPU access, or live provider credentials. Ollama runs locally, but it is still a live model runtime: output quality, speed, disk usage, and hardware compatibility depend on the selected model and machine. Mock mode remains deterministic and free for tests; hosted APIs require private credentials and may create token costs.
