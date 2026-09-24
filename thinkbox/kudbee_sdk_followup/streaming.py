"""SSE stream parsing (hermetic) (PR #179 F13)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator


@dataclass(frozen=True)
class SseEvent:
    event: str | None
    data: str
    id: str | None = None


def parse_sse_block(block: str) -> SseEvent | None:
    if not block.strip():
        return None
    event_name: str | None = None
    event_id: str | None = None
    data_lines: list[str] = []
    for line in block.splitlines():
        if line.startswith("event:"):
            event_name = line.split(":", 1)[1].strip()
        elif line.startswith("id:"):
            event_id = line.split(":", 1)[1].strip()
        elif line.startswith("data:"):
            data_lines.append(line.split(":", 1)[1].strip())
    if not data_lines and event_name is None:
        return None
    return SseEvent(event=event_name, data="\n".join(data_lines), id=event_id)


def parse_sse_chunk(buffer: str) -> tuple[tuple[SseEvent, ...], str]:
    """Parse complete SSE events from a text buffer; return remainder."""
    if "\n\n" not in buffer:
        return (), buffer
    *blocks, remainder = buffer.split("\n\n")
    events: list[SseEvent] = []
    for block in blocks:
        ev = parse_sse_block(block)
        if ev is not None:
            events.append(ev)
    return tuple(events), remainder


def iter_sse_events(chunks: Iterator[str]) -> Iterator[SseEvent]:
    buf = ""
    for chunk in chunks:
        buf += chunk
        parsed, buf = parse_sse_chunk(buf)
        for ev in parsed:
            yield ev


@dataclass(frozen=True)
class SseReconnectPolicy:
    """Hermetic SSE reconnect policy (no network)."""

    max_attempts: int = 3
    base_delay_ms: int = 250

    def delay_for_attempt(self, attempt: int) -> int:
        if attempt < 1:
            return 0
        if attempt > self.max_attempts:
            return -1
        return self.base_delay_ms * attempt

    def should_retry(self, attempt: int) -> bool:
        return attempt < self.max_attempts
