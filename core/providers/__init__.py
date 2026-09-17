"""Provider layer — model provider protocol and implementations."""

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
    "CapabilityCheck",
    "CapabilityStatus",
    "CompletionResponse",
    "EvidenceRecord",
    "ExecutionPlan",
    "ExecutionProvider",
    "ExecutionProviderCapabilities",
    "ExecutionResult",
    "Message",
    "ModelProvider",
    "OpenAICompatProvider",
    "ProviderCapabilities",
    "ProviderExecutionRegistry",
    "ProviderRegistry",
    "UpCloudExecutionProvider",
]
