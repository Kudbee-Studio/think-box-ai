"""Ollama provider for THINK BOX AI — local inference via Ollama."""

from __future__ import annotations

import json
import os
from typing import Any, AsyncGenerator

from core.providers.base import (
    CompletionResponse,
    Message,
    ModelProvider,
    ProviderCapabilities,
    ProviderRegistry,
)


@ProviderRegistry.register("ollama")
class OllamaProvider:
    """ModelProvider implementation for Ollama local inference.

    Bridges the Ollama HTTP API (api/chat, api/tags) into the
    core/providers/ layer without modifying backend/models/ollama_client.py.
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        config = config or {}
        self._base_url = config.get(
            "base_url",
            os.environ.get("THINKBOX_OLLAMA_BASE_URL", "http://localhost:11434"),
        )
        self._model = config.get(
            "model",
            os.environ.get("THINKBOX_OLLAMA_MODEL", "llama3"),
        )
        self.capabilities = ProviderCapabilities(
            completion=True,
            streaming=True,
            embedding=False,
            supports_system_prompt=True,
        )

    async def complete(
        self, messages: list[Message], **kwargs: Any
    ) -> CompletionResponse:
        """Non-streaming chat completion."""
        import aiohttp

        payload = {
            "model": self._model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
            "options": {
                "temperature": kwargs.get("temperature", 0.7),
                "num_predict": kwargs.get("max_tokens", 4096),
            },
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self._base_url}/api/chat",
                    json=payload,
                    headers={"Content-Type": "application/json"},
                ) as resp:
                    data = await resp.json()
                    content = data.get("message", {}).get("content", "")
                    return CompletionResponse(
                        content=content,
                        model=data.get("model", self._model),
                        usage=_extract_usage(data),
                    )
        except Exception as e:
            return CompletionResponse(
                content=f"[Error: {str(e)}]",
                model=self._model,
            )

    async def stream(
        self, messages: list[Message], **kwargs: Any
    ) -> AsyncGenerator[str, None]:
        """Stream chat completion tokens from Ollama."""
        import aiohttp

        payload = {
            "model": self._model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": True,
            "options": {
                "temperature": kwargs.get("temperature", 0.7),
                "num_predict": kwargs.get("max_tokens", 4096),
            },
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self._base_url}/api/chat",
                    json=payload,
                    headers={"Content-Type": "application/json"},
                ) as resp:
                    buffer = ""
                    async for chunk in resp.content.iter_any():
                        buffer += chunk.decode("utf-8", errors="replace")
                        while "\n" in buffer:
                            line_str, buffer = buffer.split("\n", 1)
                            line_str = line_str.strip()
                            if not line_str:
                                continue
                            try:
                                data = json.loads(line_str)
                            except json.JSONDecodeError:
                                continue
                            if "message" in data and "content" in data["message"]:
                                yield data["message"]["content"]
                            if data.get("done"):
                                return
        except Exception as e:
            yield f"[Error: {str(e)}]"

    async def embed(
        self, texts: list[str], **kwargs: Any
    ) -> list[list[float]]:
        """Embedding is not supported by Ollama via this provider."""
        raise NotImplementedError(
            "Embedding not supported by OllamaProvider"
        )

    async def list_models(self) -> list[dict[str, Any]]:
        """List available Ollama models."""
        import aiohttp

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self._base_url}/api/tags"
                ) as resp:
                    data = await resp.json()
                    return data.get("models", [])
        except Exception:
            return []


def _extract_usage(data: dict[str, Any]) -> dict[str, int]:
    """Extract token usage from Ollama response if available."""
    usage: dict[str, int] = {}
    for key in ("prompt_eval_count", "eval_count"):
        if key in data:
            usage[key] = data[key]
    return usage
