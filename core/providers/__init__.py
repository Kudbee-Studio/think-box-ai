"""Provider layer — model provider protocol and infrastructure provider protocol."""

from __future__ import annotations

from core.providers.base import (
    CompletionResponse,
    Message,
    ModelProvider,
    ProviderCapabilities,
    ProviderRegistry,
)
from core.providers.execution import (
    CapabilityCheck,
    CapabilityStatus,
    EvidenceRecord,
    ExecutionPlan,
    ExecutionProvider,
    ExecutionProviderCapabilities,
    ExecutionResult,
    ProviderExecutionRegistry,
)
from core.providers.openai_compat import OpenAICompatProvider
from core.providers.upcloud import UpCloudExecutionProvider

__all__ = [
    "CompletionResponse",
    "Message",
    "ModelProvider",
    "OpenAICompatProvider",
    "ProviderCapabilities",
    "ProviderRegistry",
    "CapabilityCheck",
    "CapabilityStatus",
    "EvidenceRecord",
    "ExecutionPlan",
    "ExecutionProvider",
    "ExecutionProviderCapabilities",
    "ExecutionResult",
    "ProviderExecutionRegistry",
    "UpCloudExecutionProvider",
]
