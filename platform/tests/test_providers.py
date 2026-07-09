import json

from blacklight.models import ProviderRequest
from blacklight.providers.mock import MockProvider
from blacklight.providers.ollama_provider import OllamaProvider
from blacklight.providers.openai_provider import OpenAIProvider


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

    monkeypatch.setattr("blacklight.providers.ollama_provider.urlrequest.urlopen", fake_urlopen)

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


def test_ollama_provider_maps_json_output_format(monkeypatch):
    captured = {}

    class FakeHTTPResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self):
            return json.dumps({"model": "llama3.1", "response": "{}"}).encode("utf-8")

    def fake_urlopen(http_request, timeout):
        captured["body"] = json.loads(http_request.data.decode("utf-8"))
        return FakeHTTPResponse()

    monkeypatch.setattr("blacklight.providers.ollama_provider.urlrequest.urlopen", fake_urlopen)

    OllamaProvider(base_url="http://localhost:11434/").complete(
        ProviderRequest(
            prompt="Classify this ticket.",
            model="llama3.1",
            output_format="json_object",
        )
    )

    assert captured["body"]["format"] == "json"


def test_openai_provider_maps_json_output_format():
    captured = {}

    class FakeResponses:
        def create(self, **kwargs):
            captured.update(kwargs)

            class FakeResponse:
                output_text = "{}"
                usage = None
                id = "response-1"

            return FakeResponse()

    provider = OpenAIProvider.__new__(OpenAIProvider)
    provider.client = type("FakeClient", (), {"responses": FakeResponses()})()

    response = provider.complete(
        ProviderRequest(
            prompt="Classify this ticket.",
            model="gpt-4o-mini",
            output_format="json_object",
        )
    )

    assert captured["text"] == {"format": {"type": "json_object"}}
    assert response.text == "{}"


def test_openai_provider_prefers_output_schema_over_json_object():
    captured = {}
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["category"],
        "properties": {"category": {"type": "string", "enum": ["billing"]}},
    }

    class FakeResponses:
        def create(self, **kwargs):
            captured.update(kwargs)

            class FakeResponse:
                output_text = '{"category":"billing"}'
                usage = None
                id = "response-1"

            return FakeResponse()

    provider = OpenAIProvider.__new__(OpenAIProvider)
    provider.client = type("FakeClient", (), {"responses": FakeResponses()})()

    provider.complete(
        ProviderRequest(
            prompt="Classify this ticket.",
            model="gpt-4o-mini",
            output_format="json_object",
            output_schema_name="ticket_classification",
            output_schema=schema,
        )
    )

    assert captured["text"] == {
        "format": {
            "type": "json_schema",
            "name": "ticket_classification",
            "schema": schema,
            "strict": True,
        }
    }


def test_ollama_provider_reads_base_url_from_user_env(monkeypatch, tmp_path):
    user_env_path = tmp_path / "user.env"
    user_env_path.write_text(
        "OLLAMA_BASE_URL=http://127.0.0.1:11435\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("BLACKLIGHT_USER_ENV_PATH", str(user_env_path))
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)

    provider = OllamaProvider()

    assert provider.base_url == "http://127.0.0.1:11435"
