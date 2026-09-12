"""KUDBEE Control Fabric — Reasoning-channel normalization.

vLLM serving `openai/gpt-oss-20b` exposes a reasoning channel in addition
to content. In non-streamed responses it arrives as
``choices[0].message.reasoning``; in streaming deltas as
``choices[0].delta.reasoning``. The reasoning channel must be captured,
never dropped, and is a grounding signal for the verifier.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Iterable

from thinkbox.thinktrace import ThinkTrace, ThinkTraceCapture


@dataclass
class ReasoningChunk:
    content: str = ""
    reasoning: str = ""
    finish_reason: str = ""
    usage: dict[str, Any] = field(default_factory=dict)


@dataclass
class NormalizedCompletion:
    content: str = ""
    reasoning: str = ""
    finish_reason: str = ""
    usage: dict[str, Any] = field(default_factory=dict)

    @property
    def had_reasoning(self) -> bool:
        return bool(self.reasoning)


def _delta_text(delta: dict[str, Any], key: str) -> str:
    value = delta.get(key)
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return "".join(parts)
    return ""


class ReasoningNormalizer:
    """Parses OpenAI-compatible completions, preserving the reasoning channel."""

    def parse_response(self, payload: dict[str, Any]) -> NormalizedCompletion:
        """Parse a non-streamed chat completion payload."""
        choices = payload.get("choices") or []
        if not choices:
            return NormalizedCompletion(usage=payload.get("usage") or {})
        choice = choices[0] or {}
        message = choice.get("message") or {}
        content = message.get("content")
        if not isinstance(content, str):
            content = _delta_text(message, "content")
        reasoning = _delta_text(message, "reasoning") or _delta_text(message, "reasoning_content")
        return NormalizedCompletion(
            content=content,
            reasoning=reasoning,
            finish_reason=str(choice.get("finish_reason") or ""),
            usage=payload.get("usage") or {},
        )

    def parse_stream_line(self, line: str) -> ReasoningChunk | None:
        """Parse one SSE/NDJSON line; returns None for keep-alives and [DONE]."""
        text = line.strip()
        if not text or text == "data: [DONE]" or text == "[DONE]":
            return None
        if text.startswith("data:"):
            text = text[len("data:"):].strip()
        if not text:
            return None
        try:
            payload = json.loads(text)
        except (json.JSONDecodeError, ValueError):
            return None
        choices = payload.get("choices") or []
        if not choices:
            return None
        choice = choices[0] or {}
        delta = choice.get("delta") or {}
        return ReasoningChunk(
            content=_delta_text(delta, "content"),
            reasoning=_delta_text(delta, "reasoning") or _delta_text(delta, "reasoning_content"),
            finish_reason=str(choice.get("finish_reason") or ""),
            usage=payload.get("usage") or {},
        )

    def normalize_stream(self, lines: Iterable[str]) -> NormalizedCompletion:
        """Fold streaming chunks into a single completion, keeping reasoning."""
        content_parts: list[str] = []
        reasoning_parts: list[str] = []
        finish_reason = ""
        usage: dict[str, Any] = {}
        for line in lines:
            chunk = self.parse_stream_line(line)
            if chunk is None:
                continue
            if chunk.content:
                content_parts.append(chunk.content)
            if chunk.reasoning:
                reasoning_parts.append(chunk.reasoning)
            if chunk.finish_reason:
                finish_reason = chunk.finish_reason
            if chunk.usage:
                usage = chunk.usage
        return NormalizedCompletion(
            content="".join(content_parts),
            reasoning="".join(reasoning_parts),
            finish_reason=finish_reason,
            usage=usage,
        )

    def extract_reasoning(self, payload: dict[str, Any]) -> str:
        """Best-effort reasoning extraction from either response shape."""
        direct = _delta_text(payload, "reasoning")
        if direct:
            return direct
        choices = payload.get("choices") or []
        if not choices:
            return ""
        choice = choices[0] or {}
        for container in ("message", "delta"):
            candidate = choice.get(container) or {}
            text = _delta_text(candidate, "reasoning") or _delta_text(candidate, "reasoning_content")
            if text:
                return text
        return ""


def capture_completion(
    capture: ThinkTraceCapture,
    agent_id: str,
    completion: NormalizedCompletion,
    evidence_refs: list[str] | None = None,
    tags: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> ThinkTrace:
    """Record a completion as a Think Trace, preserving its reasoning channel."""
    trace_tags = list(tags or [])
    if completion.had_reasoning:
        trace_tags.append("reasoning")
    trace_metadata: dict[str, Any] = dict(metadata or {})
    if completion.reasoning:
        trace_metadata["reasoning"] = completion.reasoning
    if completion.usage:
        trace_metadata["usage"] = completion.usage
    return capture.capture(
        agent_id=agent_id,
        thought=completion.content,
        evidence_refs=evidence_refs,
        tags=trace_tags,
        metadata=trace_metadata,
    )