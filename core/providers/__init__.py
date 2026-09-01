"""Provider abstraction layer for Think Box AI.

Supports: Ollama, OpenAI, Anthropic, Groq, Together, vLLM, any OpenAI-compatible API.
"""

from __future__ import annotations

import json
import os
from typing import Any, Protocol

from core.foundation.logging import get_logger

logger = get_logger(__name__)


class Message:
    def __init__(self, role: str, content: str):
        self.role = role
        self.content = content


class CompletionResponse:
    def __init__(self, content: str, model: str, usage: dict | None = None):
        self.content = content
        self.model = model
        self.usage = usage or {}


class ProviderCapabilities:
    def __init__(self, completion=True, streaming=False, embedding=False, supports_system_prompt=True):
        self.completion = completion
        self.streaming = streaming
        self.embedding = embedding
        self.supports_system_prompt = supports_system_prompt


class ModelProvider(Protocol):
    async def complete(self, messages: list[Message], **kwargs: Any) -> CompletionResponse: ...
    async def stream(self, messages: list[Message], **kwargs: Any): ...
    async def embed(self, texts: list[str], **kwargs: Any) -> list[list[float]]: ...


class ProviderRegistry:
    _providers: dict[str, type] = {}

    @classmethod
    def register(cls, name: str):
        def decorator(provider_cls):
            cls._providers[name] = provider_cls
            return provider_cls
        return decorator

    @classmethod
    def get(cls, name: str):
        provider_cls = cls._providers.get(name)
        if not provider_cls:
            raise ValueError(f"Unknown provider: {name}. Available: {list(cls._providers.keys())}")
        return provider_cls

    @classmethod
    def list_providers(cls) -> list[str]:
        return list(cls._providers.keys())


def create_provider(config: dict[str, Any]) -> ModelProvider:
    """Factory: create a provider from config dict."""
    name = config.get("name", "ollama")
    provider_cls = ProviderRegistry.get(name)
    return provider_cls(config)


# Ollama Provider
@ProviderRegistry.register("ollama")
class OllamaProvider:
    def __init__(self, config: dict[str, Any]):
        self.base_url = config.get("base_url", "http://localhost:11434")
        self.model = config.get("model", "llama3.1:8b")
        self.timeout = config.get("timeout", 120)
        self.capabilities = ProviderCapabilities(streaming=True)

    async def complete(self, messages: list[Message], **kwargs: Any) -> CompletionResponse:
        import asyncio
        payload = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
            "options": {"temperature": kwargs.get("temperature", 0.7), "num_predict": kwargs.get("max_tokens", 4096)},
        }
        def _fetch():
            import urllib.request, urllib.error
            req = urllib.request.Request(f"{self.base_url}/api/chat", data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode())
                return CompletionResponse(data.get("message", {}).get("content", ""), data.get("model", self.model), data.get("usage", {}))
        return await asyncio.to_thread(_fetch)

    async def stream(self, messages: list[Message], **kwargs: Any):
        import urllib.request
        payload = {"model": self.model, "messages": [{"role": m.role, "content": m.content} for m in messages], "stream": True}
        req = urllib.request.Request(f"{self.base_url}/api/chat", data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            for line in resp:
                data = json.loads(line.decode())
                if "message" in data:
                    yield data["message"].get("content", "")

    async def embed(self, texts: list[str], **kwargs: Any) -> list[list[float]]:
        raise NotImplementedError


# OpenAI-Compatible Provider
@ProviderRegistry.register("openai_compat")
class OpenAICompatProvider:
    def __init__(self, config: dict[str, Any]):
        self.api_key = config.get("api_key", "")
        self.model = config.get("model", "gpt-4o-mini")
        self.base_url = config.get("base_url", "https://api.openai.com/v1")
        self.capabilities = ProviderCapabilities(streaming=config.get("streaming", False))

    async def complete(self, messages: list[Message], **kwargs: Any) -> CompletionResponse:
        import asyncio
        payload = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 4096),
        }
        def _fetch():
            import urllib.request, urllib.error
            req = urllib.request.Request(
                f"{self.base_url}/chat/completions",
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"},
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode())
                choice = data["choices"][0]["message"]
                return CompletionResponse(choice.get("content", ""), data.get("model", self.model), data.get("usage", {}))
        return await asyncio.to_thread(_fetch)

    async def stream(self, messages: list[Message], **kwargs: Any):
        raise NotImplementedError

    async def embed(self, texts: list[str], **kwargs: Any) -> list[list[float]]:
        raise NotImplementedError


# Anthropic Provider
@ProviderRegistry.register("anthropic")
class AnthropicProvider:
    def __init__(self, config: dict[str, Any]):
        self.api_key = config.get("api_key", "")
        self.model = config.get("model", "claude-sonnet-4-20250514")
        self.base_url = config.get("base_url", "https://api.anthropic.com/v1")
        self.capabilities = ProviderCapabilities()

    async def complete(self, messages: list[Message], **kwargs: Any) -> CompletionResponse:
        import asyncio
        system_msgs = [m for m in messages if m.role == "system"]
        user_msgs = [m for m in messages if m.role != "system"]
        system = system_msgs[0].content if system_msgs else ""
        payload = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in user_msgs],
            "max_tokens": kwargs.get("max_tokens", 4096),
        }
        if system:
            payload["system"] = system
        def _fetch():
            import urllib.request
            req = urllib.request.Request(
                f"{self.base_url}/messages",
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json", "x-api-key": self.api_key, "anthropic-version": "2023-06-01"},
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode())
                return CompletionResponse(data.get("content", [{}])[0].get("text", ""), data.get("model", self.model), data.get("usage", {}))
        return await asyncio.to_thread(_fetch)

    async def stream(self, messages: list[Message], **kwargs: Any):
        raise NotImplementedError

    async def embed(self, texts: list[str], **kwargs: Any) -> list[list[float]]:
        raise NotImplementedError
