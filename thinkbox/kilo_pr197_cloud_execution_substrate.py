"""Hermetic cloud execution substrate contracts (PR #197)."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from thinkbox.cloud_execution.providers.hermetic import PROVIDER_NAME
from thinkbox.kilo_live_proof_readiness import REPO_ROOT

__all__ = (
    "EXPECTED_FEATURE_COUNT",
    "FEATURES_MANIFEST_REL",
    "GATE_ID",
    "PR197_PASS_REL",
    "PR_NUMBER",
    "CloudExecutionSubstrateViolation",
    "cloud_execution_substrate_contract_summary",
    "load_features_manifest",
    "validate_features_manifest",
)

GATE_ID = "cloud-execution-substrate"
PR_NUMBER = 197
EXPECTED_FEATURE_COUNT = 10

FEATURES_MANIFEST_REL = Path("data/cloud_execution/pr197_features.json")
PR197_PASS_REL = Path("docs/audit/passes/2026-09-24-pr197.json")


@dataclass(frozen=True)
class CloudExecutionSubstrateViolation:
    code: str
    message: str
    path: str | None = None


def load_features_manifest(repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root if repo_root is not None else REPO_ROOT
    return json.loads((root / FEATURES_MANIFEST_REL).read_text(encoding="utf-8"))


def validate_features_manifest(
    doc: Mapping[str, Any] | None = None,
    repo_root: Path | None = None,
) -> tuple[bool, tuple[CloudExecutionSubstrateViolation, ...]]:
    root = repo_root if repo_root is not None else REPO_ROOT
    violations: list[CloudExecutionSubstrateViolation] = []
    if doc is None:
        doc = load_features_manifest(root)

    if doc.get("gate_id") != GATE_ID:
        violations.append(CloudExecutionSubstrateViolation("gate_id", "gate_id mismatch"))
    if doc.get("pr_number") != PR_NUMBER:
        violations.append(CloudExecutionSubstrateViolation("pr_number", "pr_number mismatch"))
    if doc.get("live_verified") is True:
        violations.append(CloudExecutionSubstrateViolation("live_verified", "must be false"))
    features = list(doc.get("features") or [])
    if len(features) != EXPECTED_FEATURE_COUNT:
        violations.append(CloudExecutionSubstrateViolation("feature_count", "feature count mismatch"))
    for feat in features:
        rel = feat.get("module")
        if not rel or not (root / str(rel)).is_file():
            violations.append(
                CloudExecutionSubstrateViolation("feature_module_missing", str(rel), path=str(rel)),
            )

    adr = root / "docs/decisions/002-cloud-execution-substrate.md"
    if not adr.is_file():
        violations.append(CloudExecutionSubstrateViolation("adr", "missing ADR 002"))

    audit = root / PR197_PASS_REL
    if not audit.is_file():
        violations.append(CloudExecutionSubstrateViolation("audit_pass", "missing audit"))

    from thinkbox import kilo_pr196_kudbee_cli_enterprise_upgrade as pr196

    ok196, _ = pr196.validate_features_manifest(repo_root=root)
    if not ok196:
        violations.append(CloudExecutionSubstrateViolation("pr196_upstream", "pr196 invalid"))

    hermetic = root / "thinkbox/cloud_execution/providers/hermetic.py"
    if PROVIDER_NAME not in hermetic.read_text(encoding="utf-8"):
        violations.append(CloudExecutionSubstrateViolation("hermetic_provider", "missing provider name"))

    return (len(violations) == 0, tuple(violations))


def cloud_execution_substrate_contract_summary(repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root if repo_root is not None else REPO_ROOT
    ok, violations = validate_features_manifest(repo_root=root)
    return {
        "gate_id": GATE_ID,
        "pr_number": PR_NUMBER,
        "hermetic_operator_ok": ok,
        "live_verified": False,
        "live_api_called": False,
        "four_state_max": "TEST_VERIFIED",
        "feature_count": EXPECTED_FEATURE_COUNT,
        "default_provider": PROVIDER_NAME,
        "upstream_pr": 196,
        "violation_count": len(violations),
        "violation_codes": [v.code for v in violations],
    }
