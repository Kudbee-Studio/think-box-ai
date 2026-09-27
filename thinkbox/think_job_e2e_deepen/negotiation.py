"""Capability negotiation for Think Job e2e deepen (PR #183 F03)."""

from __future__ import annotations

from dataclasses import dataclass

THINK_JOB_E2E_DEEPEN_VERSION = 1


@dataclass(frozen=True)
class ThinkJobE2eCapabilities:
    capabilities: tuple[str, ...]
    version: int


def negotiate(
    client_caps: tuple[str, ...],
    server_caps: tuple[str, ...],
) -> ThinkJobE2eCapabilities:
    overlap = tuple(sorted(set(client_caps) & set(server_caps)))
    return ThinkJobE2eCapabilities(capabilities=overlap, version=THINK_JOB_E2E_DEEPEN_VERSION)


def compatible_with_server(min_version: int) -> bool:
    return min_version <= THINK_JOB_E2E_DEEPEN_VERSION
