"""Hermetic cloud execution durable queue contracts (PR #198)."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from thinkbox.kilo_live_proof_readiness import REPO_ROOT

GATE_ID = "cloud-execution-durable-queue"
PR_NUMBER = 198
EXPECTED_FEATURE_COUNT = 10

FEATURES_MANIFEST_REL = Path("data/cloud_execution/pr198_features.json")
PR198_PASS_REL = Path("docs/audit/passes/2026-09-24-pr198.json")


@dataclass(frozen=True)
class CloudExecutionDurableQueueViolation:
    code: str
    message: str
    path: str | None = None


def load_features_manifest(repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root if repo_root is not None else REPO_ROOT
    return json.loads((root / FEATURES_MANIFEST_REL).read_text(encoding="utf-8"))


def validate_features_manifest(
    doc: Mapping[str, Any] | None = None,
    repo_root: Path | None = None,
) -> tuple[bool, tuple[CloudExecutionDurableQueueViolation, ...]]:
    root = repo_root if repo_root is not None else REPO_ROOT
    violations: list[CloudExecutionDurableQueueViolation] = []
    if doc is None:
        doc = load_features_manifest(root)

    if doc.get("gate_id") != GATE_ID:
        violations.append(CloudExecutionDurableQueueViolation("gate_id", "gate_id mismatch"))
    if doc.get("pr_number") != PR_NUMBER:
        violations.append(CloudExecutionDurableQueueViolation("pr_number", "pr_number mismatch"))
    if doc.get("live_verified") is True:
        violations.append(CloudExecutionDurableQueueViolation("live_verified", "must be false"))
    features = list(doc.get("features") or [])
    if len(features) != EXPECTED_FEATURE_COUNT:
        violations.append(CloudExecutionDurableQueueViolation("feature_count", "feature count mismatch"))
    for feat in features:
        rel = feat.get("module")
        if not rel or not (root / str(rel)).is_file():
            violations.append(
                CloudExecutionDurableQueueViolation("feature_module_missing", str(rel), path=str(rel)),
            )

    adr = root / "docs/decisions/003-cloud-execution-durable-queue.md"
    if not adr.is_file():
        violations.append(CloudExecutionDurableQueueViolation("adr", "missing ADR 003"))

    if not (root / PR198_PASS_REL).is_file():
        violations.append(CloudExecutionDurableQueueViolation("audit_pass", "missing audit"))

    from thinkbox import kilo_pr197_cloud_execution_substrate as pr197

    if not pr197.validate_features_manifest(repo_root=root)[0]:
        violations.append(CloudExecutionDurableQueueViolation("pr197_upstream", "pr197 invalid"))

    return (len(violations) == 0, tuple(violations))


def cloud_execution_durable_queue_contract_summary(repo_root: Path | None = None) -> dict[str, Any]:
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
        "upstream_pr": 197,
        "violation_count": len(violations),
        "violation_codes": [v.code for v in violations],
    }
