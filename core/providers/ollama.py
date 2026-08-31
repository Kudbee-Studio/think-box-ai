"""Ollama provider for THINK BOX AI."""

from __future__ import annotations

import json
from typing import Any

from core.providers.base import CompletionResponse, Message, ModelProvider, ProviderCapabilities, ProviderRegistry


@ProviderRegistry.register("ollama")
class OllamaProvider(ModelProvider):
    def __init__(self, config: dict[str, Any]) -> None:
        self._base_url = config.get("base_url", "http://localhost:11434")
        self._model = config.get("model", "llama3.2:latest")
        self._timeout = config.get("timeout", 120)
        self.capabilities = ProviderCapabilities(
            completion=True,
            streaming=True,
            embedding=False,
            supports_system_prompt=True,
        )

    async def complete(self, messages: list[Message], **kwargs: Any) -> CompletionResponse:
        import asyncio

        payload = {
            "model": self._model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
            "options": {
                "temperature": kwargs.get("temperature", 0.7),
                "num_predict": kwargs.get("max_tokens", 4096),
            },
        }

        def _fetch() -> CompletionResponse:
            import urllib.request
            import urllib.error

            req = urllib.request.Request(
                f"{self._base_url}/api/chat",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            try:
                with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    content = data.get("message", {}).get("content", "")
                    return CompletionResponse(
                        content=content,
                        model=data.get("model", self._model),
                        usage=data.get("usage", {}),
                    )
            except urllib.error.HTTPError as e:
                from core.foundation.errors import ProviderError
                raise ProviderError(f"Ollama HTTP {e.code}: {e.read().decode()}") from e

        return await asyncio.to_thread(_fetch)

    async def stream(self, messages: list[Message], **kwargs: Any):
        import asyncio
        import urllib.request

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

        def _stream_generator():
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                buffer = ""
                for chunk in resp:
                    buffer += chunk.decode("utf-8", errors="replace")
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if "message" in data and "content" in data["message"]:
                            yield data["message"]["content"]
                        if data.get("done"):
                            return

        loop = asyncio.get_event_loop()
        for item in await loop.run_in_executor(None, list, _stream_generator()):
            yield item

    async def embed(self, texts: list[str], **kwargs: Any) -> list[list[float]]:
        raise NotImplementedError("Embedding not supported by OllamaProvider")
