"""Hermetic KUDBEECLI enterprise upgrade contracts (PR #196)."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from thinkbox.cli_phase4.negotiation import CLI_PHASE4_VERSION
from thinkbox.kilo_live_proof_readiness import REPO_ROOT

__all__ = (
    "EXPECTED_FEATURE_COUNT",
    "FEATURES_MANIFEST_REL",
    "GATE_ID",
    "PR196_PASS_REL",
    "PR_NUMBER",
    "KudbeeCliEnterpriseUpgradeViolation",
    "kudbee_cli_enterprise_upgrade_contract_summary",
    "load_features_manifest",
    "validate_features_manifest",
)

GATE_ID = "kudbee-cli-enterprise-upgrade"
PR_NUMBER = 196
EXPECTED_FEATURE_COUNT = 25

FEATURES_MANIFEST_REL = Path("data/kudbee_cli/pr196_features.json")
PR196_PASS_REL = Path("docs/audit/passes/2026-09-24-pr196.json")


@dataclass(frozen=True)
class KudbeeCliEnterpriseUpgradeViolation:
    code: str
    message: str
    path: str | None = None


def load_features_manifest(repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root if repo_root is not None else REPO_ROOT
    return json.loads((root / FEATURES_MANIFEST_REL).read_text(encoding="utf-8"))


def validate_features_manifest(
    doc: Mapping[str, Any] | None = None,
    repo_root: Path | None = None,
) -> tuple[bool, tuple[KudbeeCliEnterpriseUpgradeViolation, ...]]:
    root = repo_root if repo_root is not None else REPO_ROOT
    violations: list[KudbeeCliEnterpriseUpgradeViolation] = []
    if doc is None:
        doc = load_features_manifest(root)

    if doc.get("gate_id") != GATE_ID:
        violations.append(KudbeeCliEnterpriseUpgradeViolation("gate_id", "gate_id mismatch"))
    if doc.get("pr_number") != PR_NUMBER:
        violations.append(KudbeeCliEnterpriseUpgradeViolation("pr_number", "pr_number mismatch"))
    if doc.get("live_verified") is True:
        violations.append(KudbeeCliEnterpriseUpgradeViolation("live_verified", "must be false"))
    features = list(doc.get("features") or [])
    if len(features) != EXPECTED_FEATURE_COUNT:
        violations.append(KudbeeCliEnterpriseUpgradeViolation("feature_count", "feature count mismatch"))
    for feat in features:
        rel = feat.get("module")
        if not rel or not (root / str(rel)).is_file():
            violations.append(
                KudbeeCliEnterpriseUpgradeViolation("feature_module_missing", str(rel), path=str(rel)),
            )

    quickstart = root / "docs/guides/kudbee_cli_enterprise_upgrade_quickstart.md"
    if not quickstart.is_file():
        violations.append(KudbeeCliEnterpriseUpgradeViolation("quickstart_doc", "missing quickstart"))

    example = root / "examples/kudbee_cli_enterprise_upgrade_quickstart.py"
    if not example.is_file():
        violations.append(KudbeeCliEnterpriseUpgradeViolation("quickstart_example", "missing example"))

    cassette = root / "data/cli_phase4/cassettes/enterprise_cli_flow.json"
    if not cassette.is_file():
        violations.append(KudbeeCliEnterpriseUpgradeViolation("cassette_fixture", "missing cassette"))

    cli_main = root / "thinkbox/cli.py"
    if not cli_main.is_file():
        violations.append(KudbeeCliEnterpriseUpgradeViolation("cli_entry", "missing cli.py"))
    else:
        text = cli_main.read_text(encoding="utf-8")
        if "register_phase4_subcommands" not in text:
            violations.append(KudbeeCliEnterpriseUpgradeViolation("cli_wire", "phase4 not wired"))

    from thinkbox import kilo_pr195_kudbee_sdk_enterprise_lr_energy as pr195

    lanes_ok, _ = pr195.validate_lanes_manifest(repo_root=root)
    if not lanes_ok:
        violations.append(KudbeeCliEnterpriseUpgradeViolation("pr195_lanes", "pr195 invalid"))

    from thinkbox import kilo_pr180_kudbee_cli_phase3 as pr180

    p3_ok, _ = pr180.validate_features_manifest(repo_root=root)
    if not p3_ok:
        violations.append(KudbeeCliEnterpriseUpgradeViolation("pr180_phase3", "phase3 invalid"))

    audit = root / PR196_PASS_REL
    if not audit.is_file():
        violations.append(KudbeeCliEnterpriseUpgradeViolation("audit_pass", "missing audit"))

    return (len(violations) == 0, tuple(violations))


def kudbee_cli_enterprise_upgrade_contract_summary(repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root if repo_root is not None else REPO_ROOT
    ok, violations = validate_features_manifest(repo_root=root)
    return {
        "gate_id": GATE_ID,
        "pr_number": PR_NUMBER,
        "hermetic_operator_ok": ok,
        "live_verified": False,
        "live_api_called": False,
        "four_state_max": "TEST_VERIFIED",
        "combined_umbrella_nested": False,
        "feature_count": EXPECTED_FEATURE_COUNT,
        "cli_phase4_version": CLI_PHASE4_VERSION,
        "tier": "enterprise",
        "upstream_pr": 195,
        "violation_count": len(violations),
        "violation_codes": [v.code for v in violations],
    }
