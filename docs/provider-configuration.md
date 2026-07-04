# Provider Configuration

The provider factory supports three paths:

- `mock` for deterministic local development and CI.
- `openai` for the optional built-in OpenAI adapter.
- `custom` for user-owned adapters loaded from an import path.

The custom path is the recommended way to try local LLM runtimes without adding runtime-specific dependencies to this starter project.

## Custom Provider Contract

A custom provider must implement `LLMProvider`:

```python
from llm_platform_starter.models import ProviderRequest, ProviderResponse
from llm_platform_starter.providers.base import LLMProvider


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

from llm_platform_starter.models import ProviderRequest, ProviderResponse
from llm_platform_starter.providers.base import LLMProvider


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
llm-platform classify --subject "Login error" --body "The export page fails after login."
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
