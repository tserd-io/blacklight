import json
import socket
from urllib import error as urlerror

from blacklight.local_models import OLLAMA_PROVIDER_PATH, local_model_status
from blacklight.settings import Settings


class FakeResponse:
    def __init__(self, payload: dict):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def test_local_model_status_is_unavailable_until_configured(monkeypatch):
    def fake_urlopen(_request, timeout):
        raise urlerror.URLError("not running")

    monkeypatch.setattr("blacklight.local_models.urlrequest.urlopen", fake_urlopen)
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")

    status = local_model_status(Settings()).as_dict()

    assert status["status"] == "unavailable"
    assert status["configured"] is False
    assert status["selected"] is False
    assert status["ready"] is False
    assert status["model"] == "llama3.1"
    assert status["install_command"].endswith("ollama pull llama3.1")
    assert status["fallback"]["type"] == "local_model"
    assert status["fallback"]["configured"] is False


def test_local_model_status_ready_when_ollama_lists_selected_model(monkeypatch):
    def fake_urlopen(_request, timeout):
        assert timeout == 0.5
        return FakeResponse({"models": [{"name": "llama3.1:latest"}, {"name": "mistral"}]})

    monkeypatch.setattr("blacklight.local_models.urlrequest.urlopen", fake_urlopen)
    status = local_model_status(
        Settings(
            provider="custom",
            model="llama3.1",
            custom_provider_path=OLLAMA_PROVIDER_PATH,
        )
    ).as_dict()

    assert status["status"] == "ready"
    assert status["selected"] is True
    assert status["installed"] is True
    assert status["ready"] is True
    assert status["available_models"] == ["llama3.1:latest", "mistral"]
    assert status["fallback"]["configured"] is True
    assert status["fallback"]["model"] == "llama3.1"


def test_local_model_status_can_show_ready_fallback_without_selecting_it(monkeypatch):
    def fake_urlopen(_request, timeout):
        return FakeResponse({"models": [{"name": "llama3.1:latest"}]})

    monkeypatch.setattr("blacklight.local_models.urlrequest.urlopen", fake_urlopen)

    status = local_model_status(Settings()).as_dict()

    assert status["status"] == "ready"
    assert status["selected"] is False
    assert status["ready"] is True
    assert status["fallback"]["configured"] is True
    assert "Set LLM_PROVIDER=custom" in status["status_message"]


def test_local_model_status_loading_when_ollama_times_out(monkeypatch):
    def fake_urlopen(_request, timeout):
        raise socket.timeout("starting")

    monkeypatch.setattr("blacklight.local_models.urlrequest.urlopen", fake_urlopen)
    status = local_model_status(
        Settings(
            provider="custom",
            model="llama3.1",
            custom_provider_path=OLLAMA_PROVIDER_PATH,
        )
    ).as_dict()

    assert status["status"] == "loading"
    assert status["loading"] is True
    assert status["ready"] is False


def test_local_model_status_rejects_public_probe_urls():
    status = local_model_status(Settings(ollama_base_url="https://example.com")).as_dict()

    assert status["status"] == "unavailable"
    assert "local or private-network" in status["status_message"]
