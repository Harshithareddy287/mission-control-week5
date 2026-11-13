import os, socket
import pytest

os.environ["LLM_PROVIDER"] = "fake"
os.environ.pop("OPENAI_API_KEY", None)

@pytest.fixture(autouse=True)
def block_network(monkeypatch):
    def guard(*args, **kwargs):
        raise RuntimeError("Network access is disabled during tests")
    monkeypatch.setattr(socket.socket, "connect", guard)
