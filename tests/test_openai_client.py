"""OpenAIClient request/response mapping, with the SDK replaced by a stub (no network)."""
from types import SimpleNamespace

from app import config
from app.llm.openai_client import OpenAIClient


class StubResponses:
    def __init__(self, usage=SimpleNamespace(input_tokens=321, output_tokens=45)):
        self.kwargs = None
        self.usage = usage

    async def create(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(output_text='{"ok": true}', usage=self.usage)


def client_with_stub(**stub_kwargs):
    stub = StubResponses(**stub_kwargs)
    client = OpenAIClient()
    client._client = SimpleNamespace(responses=stub)
    return client, stub


async def test_schema_sent_as_strict_json_schema_and_usage_returned():
    client, stub = client_with_stub()
    schema = {"type": "object", "properties": {}, "additionalProperties": False}
    result = await client.complete("classify", "sys", "usr", schema=schema)

    assert stub.kwargs == {
        "model": config.MODEL_NAME,
        "instructions": "sys",
        "input": "usr",
        "text": {
            "format": {
                "type": "json_schema",
                "name": "classify",
                "schema": schema,
                "strict": True,
            }
        },
    }
    assert (result.text, result.input_tokens, result.output_tokens) == ('{"ok": true}', 321, 45)


async def test_no_schema_means_no_text_format():
    client, stub = client_with_stub()
    await client.complete("draft", "sys", "usr")
    assert stub.kwargs == {"model": config.MODEL_NAME, "instructions": "sys", "input": "usr"}


async def test_missing_usage_counts_as_zero_tokens():
    client, _ = client_with_stub(usage=None)
    result = await client.complete("draft", "sys", "usr")
    assert (result.input_tokens, result.output_tokens) == (0, 0)


def test_settings_come_from_config_and_key_is_not_shown(monkeypatch):
    monkeypatch.setattr(config, "MODEL_NAME", "my-deployment")
    monkeypatch.setattr(config, "OPENAI_BASE_URL", "https://example.invalid/openai/v1/")
    monkeypatch.setattr(config, "OPENAI_API_KEY", "sk-test-not-real")
    client = OpenAIClient()
    assert client.model == "my-deployment"
    assert client.base_url == "https://example.invalid/openai/v1/"
    assert "sk-test-not-real" not in repr(client)
    assert client._client is None  # SDK client is still not created
