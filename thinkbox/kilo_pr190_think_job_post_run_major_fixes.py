"""Hermetic Think Job POST /run major fixes (PR #190, ``think-job-post-run-major-fixes``)."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from thinkbox.kilo_live_proof_readiness import REPO_ROOT
from thinkbox.think_job_post_run_major_fixes.negotiation import THINK_JOB_POST_RUN_MAJOR_FIXES_VERSION

__all__ = (
    "EXPECTED_FIX_COUNT",
    "FIXES_MANIFEST_REL",
    "GATE_ID",
    "PR190_PASS_REL",
    "PR_NUMBER",
    "ThinkJobPostRunMajorFixViolation",
    "load_fixes_manifest",
    "think_job_post_run_major_fixes_contract_summary",
    "validate_fixes_manifest",
)

GATE_ID = "think-job-post-run-major-fixes"
PR_NUMBER = 190
EXPECTED_FIX_COUNT = 25

FIXES_MANIFEST_REL = Path("data/think_job_post_run_major/pr190_fixes.json")
PR190_PASS_REL = Path("docs/audit/passes/2026-09-24-pr190.json")


@dataclass(frozen=True)
class ThinkJobPostRunMajorFixViolation:
    code: str
    message: str
    path: str | None = None


def load_fixes_manifest(repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root if repo_root is not None else REPO_ROOT
    return json.loads((root / FIXES_MANIFEST_REL).read_text(encoding="utf-8"))


def validate_fixes_manifest(
    doc: Mapping[str, Any] | None = None,
    repo_root: Path | None = None,
) -> tuple[bool, tuple[ThinkJobPostRunMajorFixViolation, ...]]:
    root = repo_root if repo_root is not None else REPO_ROOT
    violations: list[ThinkJobPostRunMajorFixViolation] = []
    if doc is None:
        doc = load_fixes_manifest(root)

    if doc.get("gate_id") != GATE_ID:
        violations.append(ThinkJobPostRunMajorFixViolation("gate_id", "gate_id mismatch"))
    if doc.get("pr_number") != PR_NUMBER:
        violations.append(ThinkJobPostRunMajorFixViolation("pr_number", "pr_number mismatch"))
    if doc.get("live_verified") is True:
        violations.append(ThinkJobPostRunMajorFixViolation("live_verified", "must be false"))
    fixes = list(doc.get("fixes") or [])
    if len(fixes) != EXPECTED_FIX_COUNT:
        violations.append(ThinkJobPostRunMajorFixViolation("fix_count", "fix count mismatch"))
    seen: set[str] = set()
    for fix in fixes:
        fid = str(fix.get("id", ""))
        if fid in seen:
            violations.append(ThinkJobPostRunMajorFixViolation("duplicate_fix_id", fid))
        seen.add(fid)
        rel = fix.get("module")
        if not rel or not (root / str(rel)).is_file():
            violations.append(
                ThinkJobPostRunMajorFixViolation("fix_module_missing", str(rel), path=str(rel)),
            )

    checklist = root / "data/think_job_post_run_major/pr190_checklist.json"
    if not checklist.is_file():
        violations.append(ThinkJobPostRunMajorFixViolation("checklist", "missing pr190 checklist"))

    quickstart = root / "docs/guides/think_job_post_run_major_fixes_quickstart.md"
    if not quickstart.is_file():
        violations.append(ThinkJobPostRunMajorFixViolation("quickstart_doc", "missing quickstart"))

    audit = root / PR190_PASS_REL
    if not audit.is_file():
        violations.append(ThinkJobPostRunMajorFixViolation("audit_pass", "missing audit pass"))

    from thinkbox import kilo_pr189_think_job_lifecycle_major_fixes as pr189

    fixes_ok, _ = pr189.validate_fixes_manifest(repo_root=root)
    if not fixes_ok:
        violations.append(ThinkJobPostRunMajorFixViolation("pr189_fixes", "pr189 fixes invalid"))

    return (len(violations) == 0, tuple(violations))


def think_job_post_run_major_fixes_contract_summary(repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root if repo_root is not None else REPO_ROOT
    fixes_ok, violations = validate_fixes_manifest(repo_root=root)
    return {
        "gate_id": GATE_ID,
        "pr_number": PR_NUMBER,
        "pr190_gate_id": GATE_ID,
        "hermetic_operator_ok": fixes_ok,
        "live_verified": False,
        "live_api_called": False,
        "four_state_max": "TEST_VERIFIED",
        "combined_umbrella_nested": False,
        "fix_count": EXPECTED_FIX_COUNT,
        "fixes_manifest_ok": fixes_ok,
        "think_job_post_run_major_fixes_version": THINK_JOB_POST_RUN_MAJOR_FIXES_VERSION,
        "primary_surface": "thinkbox/think_job_post_run_major_fixes + F131 POST /run",
        "fixes_manifest_rel": str(FIXES_MANIFEST_REL),
        "violation_count": len(violations),
        "violation_codes": [v.code for v in violations],
    }
