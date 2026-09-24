"""Hermetic cloud execution worker orchestrator contracts (PR #199)."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from thinkbox.kilo_live_proof_readiness import REPO_ROOT

GATE_ID = "cloud-execution-worker-orchestrator"
PR_NUMBER = 199
EXPECTED_FEATURE_COUNT = 10

FEATURES_MANIFEST_REL = Path("data/cloud_execution/pr199_features.json")
PR199_PASS_REL = Path("docs/audit/passes/2026-09-24-pr199.json")


@dataclass(frozen=True)
class CloudExecutionWorkerOrchestratorViolation:
    code: str
    message: str
    path: str | None = None


def load_features_manifest(repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root if repo_root is not None else REPO_ROOT
    return json.loads((root / FEATURES_MANIFEST_REL).read_text(encoding="utf-8"))


def validate_features_manifest(
    doc: Mapping[str, Any] | None = None,
    repo_root: Path | None = None,
) -> tuple[bool, tuple[CloudExecutionWorkerOrchestratorViolation, ...]]:
    root = repo_root if repo_root is not None else REPO_ROOT
    violations: list[CloudExecutionWorkerOrchestratorViolation] = []
    if doc is None:
        doc = load_features_manifest(root)

    if doc.get("gate_id") != GATE_ID:
        violations.append(CloudExecutionWorkerOrchestratorViolation("gate_id", "gate_id mismatch"))
    if doc.get("pr_number") != PR_NUMBER:
        violations.append(CloudExecutionWorkerOrchestratorViolation("pr_number", "pr_number mismatch"))
    if doc.get("live_verified") is True:
        violations.append(CloudExecutionWorkerOrchestratorViolation("live_verified", "must be false"))
    features = list(doc.get("features") or [])
    if len(features) != EXPECTED_FEATURE_COUNT:
        violations.append(
            CloudExecutionWorkerOrchestratorViolation("feature_count", "feature count mismatch"),
        )
    for feat in features:
        rel = feat.get("module")
        if not rel or not (root / str(rel)).is_file():
            violations.append(
                CloudExecutionWorkerOrchestratorViolation(
                    "feature_module_missing",
                    str(rel),
                    path=str(rel),
                ),
            )

    adr = root / "docs/decisions/004-cloud-execution-worker-orchestrator.md"
    if not adr.is_file():
        violations.append(CloudExecutionWorkerOrchestratorViolation("adr", "missing ADR 004"))

    if not (root / PR199_PASS_REL).is_file():
        violations.append(CloudExecutionWorkerOrchestratorViolation("audit_pass", "missing audit"))

    from thinkbox import kilo_pr198_cloud_execution_durable_queue as pr198

    if not pr198.validate_features_manifest(repo_root=root)[0]:
        violations.append(CloudExecutionWorkerOrchestratorViolation("pr198_upstream", "pr198 invalid"))

    return (len(violations) == 0, tuple(violations))


def cloud_execution_worker_orchestrator_contract_summary(
    repo_root: Path | None = None,
) -> dict[str, Any]:
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
        "upstream_pr": 198,
        "violation_count": len(violations),
        "violation_codes": [v.code for v in violations],
    }
