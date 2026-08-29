"""Provider layer — model provider protocol, implementations, and routing."""

from __future__ import annotations

from core.providers.base import (
    CompletionResponse,
    Message,
    ModelProvider,
    ProviderCapabilities,
    ProviderRegistry,
)
from core.providers.longcat import LongCatProvider
from core.providers.openai_compat import OpenAICompatProvider

try:
    from core.providers.router import ProviderRouter, SnapshotCache
    from core.providers.snapshot import snapshot_hash
except ImportError:
    ProviderRouter = None
    SnapshotCache = None
    snapshot_hash = None

__all__ = [
    "CompletionResponse",
    "LongCatProvider",
    "Message",
    "ModelProvider",
    "OpenAICompatProvider",
    "ProviderCapabilities",
    "ProviderRegistry",
    "ProviderRouter",
    "SnapshotCache",
    "snapshot_hash",
]
