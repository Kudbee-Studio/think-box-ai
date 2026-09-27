"""Hermetic Think Job governed run receipt deepen (PR #186)."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from thinkbox.kilo_live_proof_readiness import REPO_ROOT
from thinkbox.think_job_run_receipt_deepen.negotiation import (
    GATE_ID,
    THINK_JOB_RUN_RECEIPT_DEEPEN_VERSION,
)

__all__ = (
    "EXPECTED_FEATURE_COUNT",
    "FEATURES_MANIFEST_REL",
    "GATE_ID",
    "PR186_PASS_REL",
    "PR_NUMBER",
    "ThinkJobRunReceiptDeepenViolation",
    "load_features_manifest",
    "think_job_run_receipt_deepen_contract_summary",
    "validate_features_manifest",
)

PR_NUMBER = 186
EXPECTED_FEATURE_COUNT = 25

FEATURES_MANIFEST_REL = Path("data/think_job_run_receipt/pr186_features.json")
PR186_PASS_REL = Path("docs/audit/passes/2026-09-24-pr186.json")


@dataclass(frozen=True)
class ThinkJobRunReceiptDeepenViolation:
    code: str
    message: str
    path: str | None = None


def load_features_manifest(repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root if repo_root is not None else REPO_ROOT
    return json.loads((root / FEATURES_MANIFEST_REL).read_text(encoding="utf-8"))


def validate_features_manifest(
    doc: Mapping[str, Any] | None = None,
    repo_root: Path | None = None,
) -> tuple[bool, tuple[ThinkJobRunReceiptDeepenViolation, ...]]:
    root = repo_root if repo_root is not None else REPO_ROOT
    violations: list[ThinkJobRunReceiptDeepenViolation] = []
    if doc is None:
        doc = load_features_manifest(root)

    if doc.get("gate_id") != GATE_ID:
        violations.append(ThinkJobRunReceiptDeepenViolation("gate_id", "gate_id mismatch"))
    if doc.get("pr_number") != PR_NUMBER:
        violations.append(ThinkJobRunReceiptDeepenViolation("pr_number", "pr_number mismatch"))
    if doc.get("live_verified") is True:
        violations.append(ThinkJobRunReceiptDeepenViolation("live_verified", "must be false"))
    features = list(doc.get("features") or [])
    if len(features) != EXPECTED_FEATURE_COUNT:
        violations.append(ThinkJobRunReceiptDeepenViolation("feature_count", "feature count mismatch"))
    seen: set[str] = set()
    for feat in features:
        fid = str(feat.get("id", ""))
        if fid in seen:
            violations.append(ThinkJobRunReceiptDeepenViolation("duplicate_feature_id", fid))
        seen.add(fid)
        rel = feat.get("module")
        if not rel or not (root / str(rel)).is_file():
            violations.append(
                ThinkJobRunReceiptDeepenViolation("feature_module_missing", str(rel), path=str(rel)),
            )

    quickstart = root / "docs/guides/think_job_run_receipt_deepen_quickstart.md"
    if not quickstart.is_file():
        violations.append(ThinkJobRunReceiptDeepenViolation("quickstart_doc", "missing quickstart"))

    example = root / "examples/think_job_run_receipt_deepen_quickstart.py"
    if not example.is_file():
        violations.append(ThinkJobRunReceiptDeepenViolation("quickstart_example", "missing example"))

    cassette = root / "data/think_job_run_receipt/cassettes/receipt_deepen_flow.json"
    if not cassette.is_file():
        violations.append(ThinkJobRunReceiptDeepenViolation("cassette_fixture", "missing cassette"))

    checklist = root / "data/think_job_run_receipt/pr186_checklist.json"
    if not checklist.is_file():
        violations.append(ThinkJobRunReceiptDeepenViolation("checklist", "missing checklist"))

    return (len(violations) == 0, tuple(violations))


def think_job_run_receipt_deepen_contract_summary(repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root if repo_root is not None else REPO_ROOT
    features_ok, violations = validate_features_manifest(repo_root=root)
    return {
        "gate_id": GATE_ID,
        "pr_number": PR_NUMBER,
        "pr186_gate_id": GATE_ID,
        "hermetic_operator_ok": features_ok,
        "live_verified": False,
        "live_api_called": False,
        "four_state_max": "TEST_VERIFIED",
        "combined_umbrella_nested": False,
        "feature_count": EXPECTED_FEATURE_COUNT,
        "think_job_run_receipt_deepen_version": THINK_JOB_RUN_RECEIPT_DEEPEN_VERSION,
        "primary_surface": "thinkbox/think_job_run_receipt_deepen + F133 receipts",
        "features_manifest_rel": str(FEATURES_MANIFEST_REL),
        "violation_count": len(violations),
        "violation_codes": [v.code for v in violations],
    }
