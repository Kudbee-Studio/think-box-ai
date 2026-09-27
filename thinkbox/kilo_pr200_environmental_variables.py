"""Hermetic environmental variables contracts (PR #200)."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from thinkbox.kilo_live_proof_readiness import REPO_ROOT

__all__ = (
    "EXPECTED_FEATURE_COUNT",
    "FEATURES_MANIFEST_REL",
    "GATE_ID",
    "PR200_PASS_REL",
    "PR_NUMBER",
    "EnvironmentalVariablesViolation",
    "environmental_variables_contract_summary",
    "load_features_manifest",
    "validate_features_manifest",
)

GATE_ID = "environmental-variables"
PR_NUMBER = 200
EXPECTED_FEATURE_COUNT = 25

FEATURES_MANIFEST_REL = Path("data/env_vars/pr200_features.json")
PR200_PASS_REL = Path("docs/audit/passes/2026-09-24-pr200.json")


@dataclass(frozen=True)
class EnvironmentalVariablesViolation:
    code: str
    message: str
    path: str | None = None


def load_features_manifest(repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root if repo_root is not None else REPO_ROOT
    return json.loads((root / FEATURES_MANIFEST_REL).read_text(encoding="utf-8"))


def validate_features_manifest(
    doc: Mapping[str, Any] | None = None,
    repo_root: Path | None = None,
) -> tuple[bool, tuple[EnvironmentalVariablesViolation, ...]]:
    root = repo_root if repo_root is not None else REPO_ROOT
    violations: list[EnvironmentalVariablesViolation] = []
    if doc is None:
        if not (root / FEATURES_MANIFEST_REL).is_file():
            violations.append(EnvironmentalVariablesViolation("features_manifest", "missing manifest"))
            return (False, tuple(violations))
        doc = load_features_manifest(root)

    if doc.get("gate_id") != GATE_ID:
        violations.append(EnvironmentalVariablesViolation("gate_id", "gate_id mismatch"))
    if doc.get("pr_number") != PR_NUMBER:
        violations.append(EnvironmentalVariablesViolation("pr_number", "pr_number mismatch"))
    if doc.get("live_verified") is True:
        violations.append(EnvironmentalVariablesViolation("live_verified", "must be false"))
    if doc.get("live_api_called") is True:
        violations.append(EnvironmentalVariablesViolation("live_api_called", "must be false"))
    features = list(doc.get("features") or [])
    if len(features) != EXPECTED_FEATURE_COUNT:
        violations.append(EnvironmentalVariablesViolation("feature_count", "feature count mismatch"))
    for feat in features:
        rel = feat.get("module")
        if not rel or not (root / str(rel)).is_file():
            violations.append(
                EnvironmentalVariablesViolation("feature_module_missing", str(rel), path=str(rel)),
            )

    adr = root / "docs/decisions/005-environmental-variables.md"
    if not adr.is_file():
        violations.append(EnvironmentalVariablesViolation("adr", "missing ADR 005"))

    guide = root / "docs/guides/environmental_variables_matrix.md"
    if not guide.is_file():
        violations.append(EnvironmentalVariablesViolation("matrix_doc", "missing matrix guide"))

    example = root / "examples/environmental_variables_quickstart.py"
    if not example.is_file():
        violations.append(EnvironmentalVariablesViolation("quickstart", "missing quickstart example"))

    for cassette in (
        "valid_minimal.json",
        "missing_required.json",
        "malformed_int.json",
    ):
        if not (root / "data/env_vars/cassettes" / cassette).is_file():
            violations.append(EnvironmentalVariablesViolation("cassette", f"missing {cassette}"))

    ts = root / "apps/web/sdk/env_vars.ts"
    if not ts.is_file():
        violations.append(EnvironmentalVariablesViolation("typescript_surface", "missing TS surface"))

    if not (root / PR200_PASS_REL).is_file():
        violations.append(EnvironmentalVariablesViolation("audit_pass", "missing audit pass"))

    from thinkbox import kilo_pr199_cloud_execution_worker_orchestrator as pr199

    if not pr199.validate_features_manifest(repo_root=root)[0]:
        violations.append(EnvironmentalVariablesViolation("pr199_upstream", "pr199 invalid"))

    return (len(violations) == 0, tuple(violations))


def environmental_variables_contract_summary(repo_root: Path | None = None) -> dict[str, Any]:
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
        "upstream_pr": 199,
        "primary_surface": "thinkbox/env_vars",
        "violation_count": len(violations),
        "violation_codes": [v.code for v in violations],
    }
