"""Hermetic Kudbee SDK long-range + energy loops deepen (PR #193, ``kudbee-sdk-longrange-energy-deepen``)."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from thinkbox.kilo_live_proof_readiness import REPO_ROOT
from thinkbox.kudbee_sdk_longrange_energy.negotiation import SDK_LR_ENERGY_VERSION

__all__ = (
    "DEEPEN_MANIFEST_REL",
    "EXPECTED_DEEPEN_PACK_COUNT",
    "EXPECTED_FEATURE_COUNT",
    "FEATURES_MANIFEST_REL",
    "GATE_ID",
    "PR193_PASS_REL",
    "PR_NUMBER",
    "KudbeeSdkLongrangeEnergyViolation",
    "kudbee_sdk_longrange_energy_contract_summary",
    "load_deepen_manifest",
    "load_features_manifest",
    "validate_deepen_manifest",
    "validate_features_manifest",
)

GATE_ID = "kudbee-sdk-longrange-energy-deepen"
PR_NUMBER = 193
EXPECTED_FEATURE_COUNT = 25

FEATURES_MANIFEST_REL = Path("data/kudbee_sdk/pr193_features.json")
DEEPEN_MANIFEST_REL = Path("data/kudbee_sdk/pr193_deepen_packs.json")
PR193_PASS_REL = Path("docs/audit/passes/2026-09-24-pr193.json")
EXPECTED_DEEPEN_PACK_COUNT = 30
DEEPEN_GATE_ID = "kudbee-sdk-longrange-energy-deepen-packs"


@dataclass(frozen=True)
class KudbeeSdkLongrangeEnergyViolation:
    code: str
    message: str
    path: str | None = None


def load_features_manifest(repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root if repo_root is not None else REPO_ROOT
    return json.loads((root / FEATURES_MANIFEST_REL).read_text(encoding="utf-8"))


def load_deepen_manifest(repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root if repo_root is not None else REPO_ROOT
    return json.loads((root / DEEPEN_MANIFEST_REL).read_text(encoding="utf-8"))


def validate_deepen_manifest(
    doc: Mapping[str, Any] | None = None,
    repo_root: Path | None = None,
) -> tuple[bool, tuple[KudbeeSdkLongrangeEnergyViolation, ...]]:
    root = repo_root if repo_root is not None else REPO_ROOT
    violations: list[KudbeeSdkLongrangeEnergyViolation] = []
    if doc is None:
        if not (root / DEEPEN_MANIFEST_REL).is_file():
            violations.append(KudbeeSdkLongrangeEnergyViolation("deepen_manifest", "missing deepen manifest"))
            return (False, tuple(violations))
        doc = load_deepen_manifest(root)
    if doc.get("gate_id") != DEEPEN_GATE_ID:
        violations.append(KudbeeSdkLongrangeEnergyViolation("deepen_gate_id", "gate_id mismatch"))
    packs = list(doc.get("packs") or [])
    if len(packs) != EXPECTED_DEEPEN_PACK_COUNT:
        violations.append(KudbeeSdkLongrangeEnergyViolation("deepen_pack_count", "pack count mismatch"))
    for pack in packs:
        rel = pack.get("module")
        if not rel or not (root / str(rel)).is_file():
            violations.append(
                KudbeeSdkLongrangeEnergyViolation("deepen_module_missing", str(rel), path=str(rel)),
            )
    return (len(violations) == 0, tuple(violations))


def validate_features_manifest(
    doc: Mapping[str, Any] | None = None,
    repo_root: Path | None = None,
) -> tuple[bool, tuple[KudbeeSdkLongrangeEnergyViolation, ...]]:
    root = repo_root if repo_root is not None else REPO_ROOT
    violations: list[KudbeeSdkLongrangeEnergyViolation] = []
    if doc is None:
        doc = load_features_manifest(root)

    if doc.get("gate_id") != GATE_ID:
        violations.append(KudbeeSdkLongrangeEnergyViolation("gate_id", "gate_id mismatch"))
    if doc.get("pr_number") != PR_NUMBER:
        violations.append(KudbeeSdkLongrangeEnergyViolation("pr_number", "pr_number mismatch"))
    if doc.get("live_verified") is True:
        violations.append(KudbeeSdkLongrangeEnergyViolation("live_verified", "must be false"))
    if doc.get("upstream_gate_id") != "kudbee-sdk-followup-w3-major-fixes":
        violations.append(KudbeeSdkLongrangeEnergyViolation("upstream_gate_id", "must reference pr192 gate"))
    features = list(doc.get("features") or [])
    if len(features) != EXPECTED_FEATURE_COUNT:
        violations.append(
            KudbeeSdkLongrangeEnergyViolation(
                "feature_count",
                f"expected {EXPECTED_FEATURE_COUNT} features",
            ),
        )
    seen_ids: set[str] = set()
    for feat in features:
        fid = str(feat.get("id", ""))
        if fid in seen_ids:
            violations.append(KudbeeSdkLongrangeEnergyViolation("duplicate_feature_id", fid))
        seen_ids.add(fid)
        rel = feat.get("module")
        if not rel or not (root / str(rel)).is_file():
            violations.append(
                KudbeeSdkLongrangeEnergyViolation(
                    "feature_module_missing",
                    f"missing module for {fid}",
                    path=str(rel),
                ),
            )

    quickstart = root / "docs/guides/kudbee_sdk_longrange_energy_quickstart.md"
    if not quickstart.is_file():
        violations.append(KudbeeSdkLongrangeEnergyViolation("quickstart_doc", "missing quickstart guide"))

    example = root / "examples/kudbee_sdk_longrange_energy_quickstart.py"
    if not example.is_file():
        violations.append(KudbeeSdkLongrangeEnergyViolation("quickstart_example", "missing example"))

    status_mod = root / "thinkbox/kudbee_sdk_longrange_energy/sdk_status_report.py"
    if not status_mod.is_file():
        violations.append(KudbeeSdkLongrangeEnergyViolation("sdk_status", "missing sdk status module"))

    cassette = root / "data/kudbee_sdk/cassettes/lr_energy/long_range_energy_flow.json"
    if not cassette.is_file():
        violations.append(KudbeeSdkLongrangeEnergyViolation("cassette_fixture", "missing default cassette"))

    ts_surface = root / "apps/web/sdk/longrange_energy.ts"
    if not ts_surface.is_file():
        violations.append(KudbeeSdkLongrangeEnergyViolation("typescript_surface", "missing longrange_energy.ts"))

    audit = root / PR193_PASS_REL
    if not audit.is_file():
        violations.append(KudbeeSdkLongrangeEnergyViolation("audit_pass", "missing audit pass"))

    from thinkbox import kilo_pr192_kudbee_sdk_followup_w3_major_fixes as pr192

    fixes_ok, _ = pr192.validate_fixes_manifest(repo_root=root)
    if not fixes_ok:
        violations.append(KudbeeSdkLongrangeEnergyViolation("pr192_fixes", "pr192 fixes manifest invalid"))
    expansion_ok, _ = pr192.validate_expansion_manifest(repo_root=root)
    if not expansion_ok:
        violations.append(KudbeeSdkLongrangeEnergyViolation("pr192_expansion", "pr192 expansion invalid"))

    deepen_ok, _ = validate_deepen_manifest(repo_root=root)
    if not deepen_ok:
        violations.append(KudbeeSdkLongrangeEnergyViolation("deepen_packs", "pr193 deepen packs invalid"))

    return (len(violations) == 0, tuple(violations))


def kudbee_sdk_longrange_energy_contract_summary(repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root if repo_root is not None else REPO_ROOT
    ok, violations = validate_features_manifest(repo_root=root)
    return {
        "gate_id": GATE_ID,
        "pr_number": PR_NUMBER,
        "pr193_gate_id": GATE_ID,
        "hermetic_operator_ok": ok,
        "live_verified": False,
        "live_api_called": False,
        "four_state_max": "TEST_VERIFIED",
        "combined_umbrella_nested": False,
        "feature_count": EXPECTED_FEATURE_COUNT,
        "sdk_lr_energy_version": SDK_LR_ENERGY_VERSION,
        "primary_surface": "thinkbox/kudbee_sdk_longrange_energy + apps/web/sdk",
        "features_manifest_rel": str(FEATURES_MANIFEST_REL),
        "violation_count": len(violations),
        "violation_codes": [v.code for v in violations],
        "upstream_pr": 192,
        "theme": "long_range_connections_quantitative_energy_loops",
        "deepen_pack_count": EXPECTED_DEEPEN_PACK_COUNT,
        "deepen_manifest_rel": str(DEEPEN_MANIFEST_REL),
    }
