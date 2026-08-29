"""Provider layer — model provider protocol, implementations, and routing."""

from __future__ import annotations

from core.providers.base import (
    CompletionResponse,
    Message,
    ModelProvider,
    ProviderCapabilities,
    ProviderRegistry,
)
from core.providers.openai_compat import OpenAICompatProvider
from core.providers.router import ProviderRouter, SnapshotCache
from core.providers.snapshot import snapshot_hash

__all__ = [
    "CompletionResponse",
    "Message",
    "ModelProvider",
    "OpenAICompatProvider",
    "ProviderCapabilities",
    "ProviderRegistry",
    "ProviderRouter",
    "SnapshotCache",
    "snapshot_hash",
]
