"""Hermetic ModelProvider for governed runs and e2e (no network).

Used by F023 lifecycle tests and ``POST /api/v1/run`` when ``model=hermetic-mock``.
"""

from __future__ import annotations

from typing import Any

from core.providers.base import CompletionResponse, Message, ModelProvider, ProviderCapabilities
from thinkbox.pop_arena import deterministic_emission_v2


class HermeticModelProvider:
    """Scripted ``ModelProvider`` — routes prompts by subtask description prefix."""

    capabilities = ProviderCapabilities(completion=True, streaming=False, embedding=False)

    def __init__(
        self,
        subtasks: list[dict[str, Any]],
        behaviors: dict[int, str] | None = None,
    ) -> None:
        self._subtasks = subtasks
        self._behaviors = behaviors or {}
        self.complete_calls: int = 0
        self._calls: dict[str, int] = {}

    async def complete(self, messages: list[Message], **kwargs: Any) -> CompletionResponse:
        self.complete_calls += 1
        prompt = messages[-1].content if messages else ""
        index = None
        for i, st in enumerate(self._subtasks):
            if prompt.startswith(st["description"]):
                index = i
                break
        if index is None:
            raise AssertionError(f"unrouted hermetic ModelProvider prompt: {prompt[:80]!r}")

        st = self._subtasks[index]
        key = st["description"]
        self._calls[key] = self._calls.get(key, 0) + 1
        n = self._calls[key]
        fam, var, spec = st["family"], st["variant"], st["spec"]
        behavior = self._behaviors.get(index, "valid")
        valid = deterministic_emission_v2(fam, var, spec)
        wrongkey = '{"result": %s}' % spec["expected"]

        if behavior == "valid":
            body = valid
        elif behavior == "wrongkey_then_valid":
            body = wrongkey if n == 1 else valid
        elif behavior == "wrongkey_always":
            body = wrongkey
        elif behavior == "arithmetic_always":
            body = '{"answer": %s}' % (spec["expected"] + 1)
        elif behavior == "valid_with_usage":
            return CompletionResponse(
                content=valid,
                model="hermetic-mock",
                usage={"total_tokens": 17},
            )
        else:
            raise AssertionError(f"unknown behavior: {behavior}")

        return CompletionResponse(content=body, model="hermetic-mock", usage={"total_tokens": 3})

    async def stream(self, messages: list[Message], **kwargs: Any):
        resp = await self.complete(messages, **kwargs)
        yield resp

    async def embed(self, texts: list[str], **kwargs: Any) -> list[list[float]]:
        return [[0.0] * 4 for _ in texts]


def provider_complete_async(provider: HermeticModelProvider):
    """Bridge ``ModelProvider.complete`` into ``execute_verified_goal``'s ``complete_async``."""

    async def complete(prompt: str) -> str | tuple[str, dict[str, int]]:
        resp = await provider.complete([Message(role="user", content=prompt)])
        if resp.usage:
            return resp.content, dict(resp.usage)
        return resp.content

    return complete
