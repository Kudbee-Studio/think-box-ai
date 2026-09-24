"""Hermetic Kudbee SDK enterprise long-range energy lanes (PR #195)."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from thinkbox.kilo_live_proof_readiness import REPO_ROOT
from thinkbox.kudbee_sdk_enterprise_lr_energy.negotiation import (
    KUDBEE_SDK_ENTERPRISE_LR_ENERGY_VERSION,
)

__all__ = (
    "EXPECTED_LANE_COUNT",
    "GATE_ID",
    "LANES_MANIFEST_REL",
    "PR195_PASS_REL",
    "PR_NUMBER",
    "KudbeeSdkEnterpriseLrEnergyViolation",
    "kudbee_sdk_enterprise_lr_energy_contract_summary",
    "load_lanes_manifest",
    "validate_lanes_manifest",
)

GATE_ID = "kudbee-sdk-enterprise-lr-energy-lanes"
PR_NUMBER = 195
EXPECTED_LANE_COUNT = 25

LANES_MANIFEST_REL = Path("data/kudbee_sdk_enterprise/pr195_enterprise_lanes.json")
PR195_PASS_REL = Path("docs/audit/passes/2026-09-24-pr195.json")


@dataclass(frozen=True)
class KudbeeSdkEnterpriseLrEnergyViolation:
    code: str
    message: str
    path: str | None = None


def load_lanes_manifest(repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root if repo_root is not None else REPO_ROOT
    return json.loads((root / LANES_MANIFEST_REL).read_text(encoding="utf-8"))


def validate_lanes_manifest(
    doc: Mapping[str, Any] | None = None,
    repo_root: Path | None = None,
) -> tuple[bool, tuple[KudbeeSdkEnterpriseLrEnergyViolation, ...]]:
    root = repo_root if repo_root is not None else REPO_ROOT
    violations: list[KudbeeSdkEnterpriseLrEnergyViolation] = []
    if doc is None:
        if not (root / LANES_MANIFEST_REL).is_file():
            violations.append(KudbeeSdkEnterpriseLrEnergyViolation("lanes_manifest", "missing manifest"))
            return (False, tuple(violations))
        doc = load_lanes_manifest(root)

    if doc.get("gate_id") != GATE_ID:
        violations.append(KudbeeSdkEnterpriseLrEnergyViolation("gate_id", "gate_id mismatch"))
    if doc.get("pr_number") != PR_NUMBER:
        violations.append(KudbeeSdkEnterpriseLrEnergyViolation("pr_number", "pr_number mismatch"))
    if doc.get("live_verified") is True:
        violations.append(KudbeeSdkEnterpriseLrEnergyViolation("live_verified", "must be false"))
    lanes = list(doc.get("lanes") or [])
    if len(lanes) != EXPECTED_LANE_COUNT:
        violations.append(KudbeeSdkEnterpriseLrEnergyViolation("lane_count", "lane count mismatch"))
    seen: set[str] = set()
    for lane in lanes:
        lid = str(lane.get("id", ""))
        if lid in seen:
            violations.append(KudbeeSdkEnterpriseLrEnergyViolation("duplicate_lane_id", lid))
        seen.add(lid)
        rel = lane.get("module")
        if not rel or not (root / str(rel)).is_file():
            violations.append(
                KudbeeSdkEnterpriseLrEnergyViolation("lane_module_missing", str(rel), path=str(rel)),
            )

    quickstart = root / "docs/guides/kudbee_sdk_enterprise_lr_energy_quickstart.md"
    if not quickstart.is_file():
        violations.append(KudbeeSdkEnterpriseLrEnergyViolation("quickstart_doc", "missing quickstart"))

    example = root / "examples/kudbee_sdk_enterprise_lr_energy_quickstart.py"
    if not example.is_file():
        violations.append(KudbeeSdkEnterpriseLrEnergyViolation("quickstart_example", "missing example"))

    hub = root / "thinkbox/kudbee_sdk_enterprise_lr_energy/enterprise_hub.py"
    if not hub.is_file():
        violations.append(KudbeeSdkEnterpriseLrEnergyViolation("enterprise_hub", "missing hub module"))

    audit = root / PR195_PASS_REL
    if not audit.is_file():
        violations.append(KudbeeSdkEnterpriseLrEnergyViolation("audit_pass", "missing audit pass"))

    checklist = root / "data/kudbee_sdk_enterprise/pr195_checklist.json"
    if not checklist.is_file():
        violations.append(KudbeeSdkEnterpriseLrEnergyViolation("checklist", "missing checklist"))

    cassette = root / "data/kudbee_sdk_enterprise/cassettes/enterprise_lr_energy_flow.json"
    if not cassette.is_file():
        violations.append(KudbeeSdkEnterpriseLrEnergyViolation("cassette", "missing cassette"))

    ts = root / "apps/web/sdk/enterprise_lr_energy.ts"
    if not ts.is_file():
        violations.append(KudbeeSdkEnterpriseLrEnergyViolation("typescript_surface", "missing TS surface"))

    from thinkbox import kilo_pr194_kudbee_sdk_longrange_energy_major_fixes as pr194

    fixes_ok, _ = pr194.validate_fixes_manifest(repo_root=root)
    if not fixes_ok:
        violations.append(KudbeeSdkEnterpriseLrEnergyViolation("pr194_fixes", "pr194 fixes invalid"))

    from thinkbox import kilo_pr193_kudbee_sdk_longrange_energy as pr193

    features_ok, _ = pr193.validate_features_manifest(repo_root=root)
    if not features_ok:
        violations.append(KudbeeSdkEnterpriseLrEnergyViolation("pr193_features", "pr193 features invalid"))
    deepen_ok, _ = pr193.validate_deepen_manifest(repo_root=root)
    if not deepen_ok:
        violations.append(KudbeeSdkEnterpriseLrEnergyViolation("pr193_deepen", "pr193 deepen invalid"))

    return (len(violations) == 0, tuple(violations))


def kudbee_sdk_enterprise_lr_energy_contract_summary(repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root if repo_root is not None else REPO_ROOT
    ok, violations = validate_lanes_manifest(repo_root=root)
    return {
        "gate_id": GATE_ID,
        "pr_number": PR_NUMBER,
        "pr195_gate_id": GATE_ID,
        "hermetic_operator_ok": ok,
        "live_verified": False,
        "live_api_called": False,
        "four_state_max": "TEST_VERIFIED",
        "combined_umbrella_nested": False,
        "lane_count": EXPECTED_LANE_COUNT,
        "enterprise_lr_energy_version": KUDBEE_SDK_ENTERPRISE_LR_ENERGY_VERSION,
        "primary_surface": "thinkbox/kudbee_sdk_enterprise_lr_energy + apps/web/sdk",
        "lanes_manifest_rel": str(LANES_MANIFEST_REL),
        "violation_count": len(violations),
        "violation_codes": [v.code for v in violations],
        "upstream_pr": 194,
        "tier": "enterprise",
    }
