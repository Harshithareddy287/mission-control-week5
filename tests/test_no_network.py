import asyncio
import os
import sys

from app.llm.base import LLMClient, get_client
from app.llm.fake import FakeLLMClient


def test_no_api_key_and_fake_client_by_default():
    assert "OPENAI_API_KEY" not in os.environ
    client = get_client()
    assert isinstance(client, FakeLLMClient)
    assert isinstance(client, LLMClient)


def test_openai_provider_does_not_import_openai_until_called(monkeypatch):
    from app.llm.openai_client import OpenAIClient

    monkeypatch.setenv("LLM_PROVIDER", "openai")
    client = get_client()
    assert isinstance(client, OpenAIClient)
    assert "openai" not in sys.modules  # lazy: no import, no key needed yet


async def test_fake_records_calls_scripts_and_delays():
    fake = FakeLLMClient(replies={"review": ["not json"]}, delay=0.05)
    loop = asyncio.get_running_loop()
    start = loop.time()
    results = await asyncio.gather(
        fake.complete("review", "s", "u1"),
        fake.complete("review", "s", "u2"),
        fake.complete("check_panic", "s", "u3"),
    )
    elapsed = loop.time() - start
    assert elapsed < 0.12  # delays overlapped, not 3 x 0.05 in series
    assert results[0].text == "not json"  # scripted reply first
    assert results[1].text.startswith("{")  # then the default canned JSON
    assert [c[0] for c in fake.calls] == ["review", "review", "check_panic"]
    assert all((r.input_tokens, r.output_tokens) == (100, 50) for r in results)
