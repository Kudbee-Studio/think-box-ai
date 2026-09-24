"""Enterprise lr-energy lane negotiation (PR #195)."""

from __future__ import annotations

KUDBEE_SDK_ENTERPRISE_LR_ENERGY_VERSION = "1.0.0-enterprise"
ENTERPRISE_LR_ENERGY_API_VERSION = 6
ENTERPRISE_GATE_ID = "kudbee-sdk-enterprise-lr-energy-lanes"
EXPECTED_LANE_COUNT = 25

DEFAULT_ENTERPRISE_CAPABILITIES: tuple[str, ...] = (
    "tenant_isolation",
    "rbac",
    "sla_tiers",
    "compliance_receipts",
    "audit_trail",
    "data_residency",
    "governance_admission",
    "multi_region_routing",
    "enterprise_quotas",
    "soc2_mapping",
)
