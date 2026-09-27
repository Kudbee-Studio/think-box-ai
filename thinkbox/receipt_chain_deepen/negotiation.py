"""Capability negotiation for deepen gate (PR #182 F03)."""

from __future__ import annotations

from dataclasses import dataclass

RECEIPT_CHAIN_DEEPEN_VERSION = 1


@dataclass(frozen=True)
class DeepenCapabilities:
    capabilities: tuple[str, ...]
    version: int


def negotiate(
    client_caps: tuple[str, ...],
    server_caps: tuple[str, ...],
) -> DeepenCapabilities:
    overlap = tuple(sorted(set(client_caps) & set(server_caps)))
    return DeepenCapabilities(capabilities=overlap, version=RECEIPT_CHAIN_DEEPEN_VERSION)


def compatible_with_server(min_version: int) -> bool:
    return min_version <= RECEIPT_CHAIN_DEEPEN_VERSION
