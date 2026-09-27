"""Enterprise CLI upgrade capability negotiation (PR #196 F21)."""

from __future__ import annotations

from dataclasses import dataclass

CLI_PHASE4_VERSION = "0.196.0-enterprise"
CLI_PHASE4_API_VERSION = 4

DEFAULT_ENTERPRISE_CLI_CAPABILITIES: tuple[str, ...] = (
    "enterprise_hub",
    "enterprise_lanes",
    "tenant_context",
    "rbac_matrix",
    "sla_tiers",
    "compliance_receipts",
    "audit_trail",
    "lr_energy_sdk",
)


@dataclass(frozen=True)
class Phase4CapabilitySet:
    cli_version: str
    api_version: int
    capabilities: tuple[str, ...]
    tier: str


def negotiate_phase4(
    client_caps: tuple[str, ...],
    server_caps: tuple[str, ...],
) -> Phase4CapabilitySet:
    overlap = tuple(sorted(set(client_caps) & set(server_caps)))
    return Phase4CapabilitySet(
        cli_version=CLI_PHASE4_VERSION,
        api_version=CLI_PHASE4_API_VERSION,
        capabilities=overlap,
        tier="enterprise",
    )
