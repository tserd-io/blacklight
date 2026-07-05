import json

from llm_platform_starter.models import ProviderRequest
from llm_platform_starter.providers.mock import MockProvider
from llm_platform_starter.providers.ollama_provider import OllamaProvider


def test_mock_provider_returns_normalized_ticket_json():
    response = MockProvider().complete(
        ProviderRequest(
            prompt="Refund requested after duplicate billing.",
            model="mock-ticket-classifier",
        )
    )

    payload = json.loads(response.text)

    assert response.provider == "mock"
    assert payload["category"] == "billing"
    assert response.input_tokens > 0


def test_ollama_provider_normalizes_generate_response(monkeypatch):
    captured = {}

    class FakeHTTPResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self):
            return json.dumps(
                {
                    "model": "llama3.1",
                    "response": '{"category":"technical"}',
                    "prompt_eval_count": 12,
                    "eval_count": 4,
                    "done": True,
                    "total_duration": 100,
                    "load_duration": 20,
                }
            ).encode("utf-8")

    def fake_urlopen(http_request, timeout):
        captured["url"] = http_request.full_url
        captured["timeout"] = timeout
        captured["body"] = json.loads(http_request.data.decode("utf-8"))
        return FakeHTTPResponse()

    monkeypatch.setattr("llm_platform_starter.providers.ollama_provider.urlrequest.urlopen", fake_urlopen)

    response = OllamaProvider(base_url="http://localhost:11434/").complete(
        ProviderRequest(prompt="Classify this ticket.", model="llama3.1")
    )

    assert captured["url"] == "http://localhost:11434/api/generate"
    assert captured["timeout"] == 60
    assert captured["body"] == {
        "model": "llama3.1",
        "prompt": "Classify this ticket.",
        "stream": False,
    }
    assert response.provider == "ollama"
    assert response.model == "llama3.1"
    assert response.text == '{"category":"technical"}'
    assert response.input_tokens == 12
    assert response.output_tokens == 4
    assert response.metadata["base_url"] == "http://localhost:11434"
