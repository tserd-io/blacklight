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

## Later Real-Config Testing

For a later milestone, add smoke tests that are skipped unless explicit environment variables are present, for example:

- `RUN_LOCAL_PROVIDER_SMOKE=1`
- `LLM_PROVIDER=custom`
- `LLM_MODEL=<local model name>`
- `LLM_CUSTOM_PROVIDER=<module:provider>`

Those tests should verify the API and CLI surfaces against a real local endpoint without making local model setup required for CI.
