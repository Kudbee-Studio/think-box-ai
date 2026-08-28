"""Ollama provider for THINK BOX AI — local inference via Ollama."""

from __future__ import annotations

import asyncio
import json
import os
import threading
import urllib.error
import urllib.request
from typing import Any, AsyncGenerator

from core.foundation.errors import ProviderError, ProviderUnavailableError
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
    Uses stdlib urllib for HTTP (consistent with OpenAICompatProvider).
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
        payload = {
            "model": self._model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
            "options": {
                "temperature": kwargs.get("temperature", 0.7),
                "num_predict": kwargs.get("max_tokens", 4096),
            },
        }

        req = urllib.request.Request(
            f"{self._base_url}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )

        def _fetch() -> CompletionResponse:
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    if resp.status != 200:
                        raise ProviderUnavailableError(
                            message=f"Ollama returned HTTP {resp.status}"
                        )
                    data = json.loads(resp.read().decode("utf-8"))
                    content = data.get("message", {}).get("content", "")
                    return CompletionResponse(
                        content=content,
                        model=data.get("model", self._model),
                        usage=_extract_usage(data),
                    )
            except urllib.error.HTTPError as e:
                raise ProviderUnavailableError(
                    message=f"Ollama returned HTTP {e.code}"
                ) from e
            except urllib.error.URLError as e:
                raise ProviderUnavailableError(
                    message=f"Connection error: {e.reason}"
                ) from e

        return await asyncio.to_thread(_fetch)

    async def stream(
        self, messages: list[Message], **kwargs: Any
    ) -> AsyncGenerator[str, None]:
        """Stream chat completion tokens from Ollama."""
        payload = {
            "model": self._model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": True,
            "options": {
                "temperature": kwargs.get("temperature", 0.7),
                "num_predict": kwargs.get("max_tokens", 4096),
            },
        }

        req = urllib.request.Request(
            f"{self._base_url}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )

        queue: asyncio.Queue = asyncio.Queue()
        loop = asyncio.get_event_loop()

        def _fetch() -> None:
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    if resp.status != 200:
                        loop.call_soon_threadsafe(
                            queue.put_nowait,
                            ProviderUnavailableError(
                                message=f"Ollama returned HTTP {resp.status}"
                            ),
                        )
                        loop.call_soon_threadsafe(queue.put_nowait, None)
                        return
                    for line in resp:
                        line_str = line.decode("utf-8").strip()
                        if not line_str:
                            continue
                        try:
                            data = json.loads(line_str)
                        except json.JSONDecodeError:
                            continue
                        if "message" in data and "content" in data["message"]:
                            loop.call_soon_threadsafe(
                                queue.put_nowait, data["message"]["content"]
                            )
                        if data.get("done"):
                            break
            except urllib.error.HTTPError as e:
                loop.call_soon_threadsafe(
                    queue.put_nowait,
                    ProviderUnavailableError(
                        message=f"Ollama returned HTTP {e.code}"
                    ),
                )
            except urllib.error.URLError as e:
                loop.call_soon_threadsafe(
                    queue.put_nowait,
                    ProviderUnavailableError(
                        message=f"Connection error: {e.reason}"
                    ),
                )
            except Exception as e:
                loop.call_soon_threadsafe(
                    queue.put_nowait, ProviderError(message=str(e))
                )
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, None)

        thread = threading.Thread(target=_fetch, daemon=True)
        thread.start()

        while True:
            item = await queue.get()
            if item is None:
                break
            if isinstance(item, Exception):
                raise item
            yield item

    async def embed(
        self, texts: list[str], **kwargs: Any
    ) -> list[list[float]]:
        """Embedding is not supported by Ollama via this provider."""
        raise NotImplementedError("Embedding not supported by OllamaProvider")

    async def list_models(self) -> list[dict[str, Any]]:
        """List available Ollama models."""
        req = urllib.request.Request(f"{self._base_url}/api/tags")

        def _fetch() -> list[dict[str, Any]]:
            try:
                with urllib.request.urlopen(req, timeout=10) as resp:
                    if resp.status != 200:
                        raise ProviderUnavailableError(
                            message=f"Ollama returned HTTP {resp.status}"
                        )
                    data = json.loads(resp.read().decode("utf-8"))
                    return data.get("models", [])
            except urllib.error.HTTPError as e:
                raise ProviderUnavailableError(
                    message=f"Ollama returned HTTP {e.code}"
                ) from e
            except urllib.error.URLError as e:
                raise ProviderUnavailableError(
                    message=f"Connection error: {e.reason}"
                ) from e

        return await asyncio.to_thread(_fetch)


def _extract_usage(data: dict[str, Any]) -> dict[str, int]:
    """Extract token usage from Ollama response if available."""
    usage: dict[str, int] = {}
    for key in ("prompt_eval_count", "eval_count"):
        if key in data:
            usage[key] = data[key]
    return usage
