"""Provider abstraction for THINK BOX AI."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass
class ProviderCapabilities:
    completion: bool = True
    streaming: bool = False
    embedding: bool = False
    supports_system_prompt: bool = True


@dataclass
class Message:
    role: str
    content: str


@dataclass
class CompletionResponse:
    content: str
    model: str
    usage: dict[str, int] = field(default_factory=dict)


@runtime_checkable
class ModelProvider(Protocol):
    capabilities: ProviderCapabilities

    def complete(self, messages: list[Message], **kwargs: Any) -> CompletionResponse:
        ...

    def stream(self, messages: list[Message], **kwargs: Any):
        ...

    def embed(self, texts: list[str], **kwargs: Any) -> list[list[float]]:
        ...


class ProviderRegistry:
    """Registry of available model providers."""

    _providers: dict[str, type] = {}

    @classmethod
    def register(cls, name: str) -> callable:
        def decorator(provider_cls: type) -> type:
            cls._providers[name] = provider_cls
            return provider_cls
        return decorator

    @classmethod
    def get(cls, name: str) -> type | None:
        return cls._providers.get(name)

    @classmethod
    def list_providers(cls) -> list[str]:
        return list(cls._providers.keys())
