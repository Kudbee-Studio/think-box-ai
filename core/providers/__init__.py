"""Provider layer — model provider protocol and implementations."""

from __future__ import annotations

from core.providers.base import (
    CompletionResponse,
    Message,
    ModelProvider,
    ProviderCapabilities,
    ProviderRegistry,
)
from core.providers.ollama import OllamaProvider
from core.providers.openai_compat import OpenAICompatProvider

__all__ = [
    "CompletionResponse",
    "Message",
    "ModelProvider",
    "OllamaProvider",
    "OpenAICompatProvider",
    "ProviderCapabilities",
    "ProviderRegistry",
]
