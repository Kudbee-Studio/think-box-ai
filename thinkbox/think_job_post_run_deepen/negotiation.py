"""Capability negotiation (PR #184 F03)."""
from __future__ import annotations
from dataclasses import dataclass
THINK_JOB_POST_RUN_DEEPEN_VERSION = 1

@dataclass(frozen=True)
class PostRunCapabilities:
    capabilities: tuple[str, ...]
    version: int

def negotiate(client: tuple[str, ...], server: tuple[str, ...]) -> PostRunCapabilities:
    overlap = tuple(sorted(set(client) & set(server)))
    return PostRunCapabilities(capabilities=overlap, version=THINK_JOB_POST_RUN_DEEPEN_VERSION)
