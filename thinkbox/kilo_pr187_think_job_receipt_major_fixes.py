"""Hermetic Think Job receipt major fixes (PR #187, ``think-job-receipt-major-fixes``)."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from thinkbox.kilo_live_proof_readiness import REPO_ROOT
from thinkbox.think_job_run_receipt_deepen.negotiation import THINK_JOB_RUN_RECEIPT_DEEPEN_VERSION

__all__ = (
    "EXPECTED_FIX_COUNT",
    "FIXES_MANIFEST_REL",
    "GATE_ID",
    "PR187_PASS_REL",
    "PR_NUMBER",
    "ThinkJobReceiptMajorFixViolation",
    "load_fixes_manifest",
    "think_job_receipt_major_fixes_contract_summary",
    "validate_fixes_manifest",
)

GATE_ID = "think-job-receipt-major-fixes"
PR_NUMBER = 187
EXPECTED_FIX_COUNT = 25

FIXES_MANIFEST_REL = Path("data/think_job_run_receipt/pr187_fixes.json")
PR187_PASS_REL = Path("docs/audit/passes/2026-09-24-pr187.json")


@dataclass(frozen=True)
class ThinkJobReceiptMajorFixViolation:
    code: str
    message: str
    path: str | None = None


def load_fixes_manifest(repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root if repo_root is not None else REPO_ROOT
    return json.loads((root / FIXES_MANIFEST_REL).read_text(encoding="utf-8"))


def validate_fixes_manifest(
    doc: Mapping[str, Any] | None = None,
    repo_root: Path | None = None,
) -> tuple[bool, tuple[ThinkJobReceiptMajorFixViolation, ...]]:
    root = repo_root if repo_root is not None else REPO_ROOT
    violations: list[ThinkJobReceiptMajorFixViolation] = []
    if doc is None:
        doc = load_fixes_manifest(root)

    if doc.get("gate_id") != GATE_ID:
        violations.append(ThinkJobReceiptMajorFixViolation("gate_id", "gate_id mismatch"))
    if doc.get("pr_number") != PR_NUMBER:
        violations.append(ThinkJobReceiptMajorFixViolation("pr_number", "pr_number mismatch"))
    if doc.get("live_verified") is True:
        violations.append(ThinkJobReceiptMajorFixViolation("live_verified", "must be false"))
    fixes = list(doc.get("fixes") or [])
    if len(fixes) != EXPECTED_FIX_COUNT:
        violations.append(ThinkJobReceiptMajorFixViolation("fix_count", "fix count mismatch"))
    seen: set[str] = set()
    for fix in fixes:
        fid = str(fix.get("id", ""))
        if fid in seen:
            violations.append(ThinkJobReceiptMajorFixViolation("duplicate_fix_id", fid))
        seen.add(fid)
        rel = fix.get("module")
        if not rel or not (root / str(rel)).is_file():
            violations.append(
                ThinkJobReceiptMajorFixViolation("fix_module_missing", str(rel), path=str(rel)),
            )

    checklist = root / "data/think_job_run_receipt/pr187_checklist.json"
    if not checklist.is_file():
        violations.append(ThinkJobReceiptMajorFixViolation("checklist", "missing pr187 checklist"))

    quickstart = root / "docs/guides/think_job_run_receipt_deepen_quickstart.md"
    if not quickstart.is_file():
        violations.append(ThinkJobReceiptMajorFixViolation("quickstart_doc", "missing quickstart"))

    audit = root / PR187_PASS_REL
    if not audit.is_file():
        violations.append(ThinkJobReceiptMajorFixViolation("audit_pass", "missing audit pass"))

    from thinkbox import kilo_pr186_think_job_run_receipt_deepen as pr186

    features_ok, _ = pr186.validate_features_manifest(repo_root=root)
    if not features_ok:
        violations.append(ThinkJobReceiptMajorFixViolation("pr186_features", "pr186 features invalid"))

    return (len(violations) == 0, tuple(violations))


def think_job_receipt_major_fixes_contract_summary(repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root if repo_root is not None else REPO_ROOT
    fixes_ok, violations = validate_fixes_manifest(repo_root=root)
    return {
        "gate_id": GATE_ID,
        "pr_number": PR_NUMBER,
        "pr187_gate_id": GATE_ID,
        "hermetic_operator_ok": fixes_ok,
        "live_verified": False,
        "live_api_called": False,
        "four_state_max": "TEST_VERIFIED",
        "combined_umbrella_nested": False,
        "fix_count": EXPECTED_FIX_COUNT,
        "fixes_manifest_ok": fixes_ok,
        "think_job_run_receipt_deepen_version": THINK_JOB_RUN_RECEIPT_DEEPEN_VERSION,
        "primary_surface": "thinkbox/think_job_run_receipt_deepen/fixes + F133 receipts",
        "fixes_manifest_rel": str(FIXES_MANIFEST_REL),
        "violation_count": len(violations),
        "violation_codes": [v.code for v in violations],
    }
