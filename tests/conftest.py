import os, socket, tempfile
import pytest

os.environ["LLM_PROVIDER"] = "fake"
os.environ.pop("OPENAI_API_KEY", None)
# Keep the module-level `app` (imported by some tests) off the real database file.
os.environ["DB_PATH"] = os.path.join(tempfile.mkdtemp(prefix="mc-tests-"), "session.db")

@pytest.fixture(autouse=True)
def block_network(monkeypatch):
    def guard(*args, **kwargs):
        raise RuntimeError("Network access is disabled during tests")
    monkeypatch.setattr(socket.socket, "connect", guard)
