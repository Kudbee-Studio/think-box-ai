"""Provider layer — model provider protocol and implementations."""

from __future__ import annotations

from core.providers.base import (
    CompletionResponse,
    Message,
    ModelProvider,
    ProviderCapabilities,
    ProviderRegistry,
)
from core.providers.openai_compat import OpenAICompatProvider
from core.providers.ollama import OllamaProvider

__all__ = [
    "CompletionResponse",
    "Message",
    "ModelProvider",
    "OpenAICompatProvider",
    "ProviderCapabilities",
    "ProviderRegistry",
    "OllamaProvider",
]
