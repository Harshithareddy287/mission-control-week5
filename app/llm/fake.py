"""Offline stand-in for the model: canned replies, scriptable, records every call."""
import asyncio
import json
from collections import defaultdict, deque
from typing import Callable, Optional, Union

from app.llm.base import LLMResult

# A reply is returned as-is (str), sent as JSON (dict/list), or computed from the
# prompt (callable(system, user) -> str | dict | list).
Reply = Union[str, dict, list, Callable[[str, str], Union[str, dict, list]]]


def default_draft(system: str, user: str) -> str:
    """Plain-text briefing built from the code FACTS block in the draft prompt."""
    lines = user.splitlines()
    try:
        start = lines.index("FACTS (computed by code; restate exactly):") + 1
    except ValueError:
        return "Briefing unavailable."
    facts = []
    for line in lines[start:]:
        if not line.strip():
            break
        facts.append(line)
    return "\n".join(facts)


DEFAULT_REPLIES: dict[str, Reply] = {
    "classify": {"subsystem": "propulsion", "severity": "medium"},
    "check_injection": {"flag": False, "reason": "No instructions to the system found."},
    "check_missing": {"flag": False, "reason": "Component, event and timing are all given."},
    "check_panic": {"flag": False, "reason": "Tone is calm and factual."},
    "draft": default_draft,
    "review": {"approved": True, "feedback": "Clear, brief and the verdict matches."},
}


def _as_text(reply: Reply, system: str, user: str) -> str:
    if callable(reply):
        reply = reply(system, user)
    return reply if isinstance(reply, str) else json.dumps(reply)


class FakeLLMClient:
    INPUT_TOKENS = 100
    OUTPUT_TOKENS = 50

    def __init__(
        self,
        replies: Optional[dict[str, list[Reply]]] = None,
        delay: float = 0.0,
    ):
        """
        replies: per-step queues; each call to that step pops the next reply,
                 falling back to DEFAULT_REPLIES once the queue is empty.
                 A str is returned verbatim (use it to send garbage), a dict/list
                 is sent as JSON, a callable is called with (system, user).
        delay:   seconds to asyncio.sleep in every call (for concurrency tests).
        """
        self._queues: dict[str, deque] = defaultdict(deque)
        for step, items in (replies or {}).items():
            self.script(step, *items)
        self.delay = delay
        self.calls: list[tuple[str, str, str]] = []

    def script(self, step: str, *replies: Reply) -> "FakeLLMClient":
        """Queue replies for a step (in order)."""
        self._queues[step].extend(replies)
        return self

    def calls_for(self, step: str) -> list[tuple[str, str, str]]:
        return [c for c in self.calls if c[0] == step]

    async def complete(
        self, step: str, system: str, user: str, schema: Optional[dict] = None
    ) -> LLMResult:
        self.calls.append((step, system, user))
        if self.delay:
            await asyncio.sleep(self.delay)
        queue = self._queues.get(step)
        reply = queue.popleft() if queue else DEFAULT_REPLIES.get(step, {})
        return LLMResult(
            text=_as_text(reply, system, user),
            input_tokens=self.INPUT_TOKENS,
            output_tokens=self.OUTPUT_TOKENS,
        )
