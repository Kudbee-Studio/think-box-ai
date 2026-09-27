"""Hermetic long-range connection primitives (PR #192 expansion)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class LongRangeLink:
    link_id: str
    hops: int = 0
    max_hops: int = 12
    correlation_ids: list[str] = field(default_factory=list)

    @classmethod
    def open(cls, link_id: str, max_hops: int = 12) -> LongRangeLink:
        return cls(link_id=link_id, max_hops=max_hops)

    def ping(self) -> dict[str, object]:
        return {
            "link_id": self.link_id,
            "hops": self.hops,
            "reachable": self.hops <= self.max_hops,
            "live_api_called": False,
        }

    def advance_hop(self, correlation_id: str) -> None:
        self.hops += 1
        self.correlation_ids.append(correlation_id)


@dataclass
class LongRangePool:
    links: dict[str, LongRangeLink] = field(default_factory=dict)

    def acquire(self, link_id: str) -> LongRangeLink:
        if link_id not in self.links:
            self.links[link_id] = LongRangeLink.open(link_id)
        return self.links[link_id]
