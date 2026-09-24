"""Hermetic Think Job lifecycle major fixes (PR #189, ``think-job-lifecycle-major-fixes``)."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from thinkbox.kilo_live_proof_readiness import REPO_ROOT
from thinkbox.think_job_lifecycle_major_fixes.negotiation import THINK_JOB_LIFECYCLE_MAJOR_FIXES_VERSION

__all__ = (
    "EXPECTED_FIX_COUNT",
    "FIXES_MANIFEST_REL",
    "GATE_ID",
    "PR189_PASS_REL",
    "PR_NUMBER",
    "ThinkJobLifecycleMajorFixViolation",
    "load_fixes_manifest",
    "think_job_lifecycle_major_fixes_contract_summary",
    "validate_fixes_manifest",
)

GATE_ID = "think-job-lifecycle-major-fixes"
PR_NUMBER = 189
EXPECTED_FIX_COUNT = 25

FIXES_MANIFEST_REL = Path("data/think_job_lifecycle_major/pr189_fixes.json")
PR189_PASS_REL = Path("docs/audit/passes/2026-09-24-pr189.json")


@dataclass(frozen=True)
class ThinkJobLifecycleMajorFixViolation:
    code: str
    message: str
    path: str | None = None


def load_fixes_manifest(repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root if repo_root is not None else REPO_ROOT
    return json.loads((root / FIXES_MANIFEST_REL).read_text(encoding="utf-8"))


def validate_fixes_manifest(
    doc: Mapping[str, Any] | None = None,
    repo_root: Path | None = None,
) -> tuple[bool, tuple[ThinkJobLifecycleMajorFixViolation, ...]]:
    root = repo_root if repo_root is not None else REPO_ROOT
    violations: list[ThinkJobLifecycleMajorFixViolation] = []
    if doc is None:
        doc = load_fixes_manifest(root)

    if doc.get("gate_id") != GATE_ID:
        violations.append(ThinkJobLifecycleMajorFixViolation("gate_id", "gate_id mismatch"))
    if doc.get("pr_number") != PR_NUMBER:
        violations.append(ThinkJobLifecycleMajorFixViolation("pr_number", "pr_number mismatch"))
    if doc.get("live_verified") is True:
        violations.append(ThinkJobLifecycleMajorFixViolation("live_verified", "must be false"))
    fixes = list(doc.get("fixes") or [])
    if len(fixes) != EXPECTED_FIX_COUNT:
        violations.append(ThinkJobLifecycleMajorFixViolation("fix_count", "fix count mismatch"))
    seen: set[str] = set()
    for fix in fixes:
        fid = str(fix.get("id", ""))
        if fid in seen:
            violations.append(ThinkJobLifecycleMajorFixViolation("duplicate_fix_id", fid))
        seen.add(fid)
        rel = fix.get("module")
        if not rel or not (root / str(rel)).is_file():
            violations.append(
                ThinkJobLifecycleMajorFixViolation("fix_module_missing", str(rel), path=str(rel)),
            )

    checklist = root / "data/think_job_lifecycle_major/pr189_checklist.json"
    if not checklist.is_file():
        violations.append(ThinkJobLifecycleMajorFixViolation("checklist", "missing pr189 checklist"))

    quickstart = root / "docs/guides/think_job_lifecycle_major_fixes_quickstart.md"
    if not quickstart.is_file():
        violations.append(ThinkJobLifecycleMajorFixViolation("quickstart_doc", "missing quickstart"))

    audit = root / PR189_PASS_REL
    if not audit.is_file():
        violations.append(ThinkJobLifecycleMajorFixViolation("audit_pass", "missing audit pass"))

    from thinkbox import kilo_pr188_think_job_governed_run_major_fixes as pr188

    fixes_ok, _ = pr188.validate_fixes_manifest(repo_root=root)
    if not fixes_ok:
        violations.append(ThinkJobLifecycleMajorFixViolation("pr188_fixes", "pr188 fixes invalid"))

    return (len(violations) == 0, tuple(violations))


def think_job_lifecycle_major_fixes_contract_summary(repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root if repo_root is not None else REPO_ROOT
    fixes_ok, violations = validate_fixes_manifest(repo_root=root)
    return {
        "gate_id": GATE_ID,
        "pr_number": PR_NUMBER,
        "pr189_gate_id": GATE_ID,
        "hermetic_operator_ok": fixes_ok,
        "live_verified": False,
        "live_api_called": False,
        "four_state_max": "TEST_VERIFIED",
        "combined_umbrella_nested": False,
        "fix_count": EXPECTED_FIX_COUNT,
        "fixes_manifest_ok": fixes_ok,
        "think_job_lifecycle_major_fixes_version": THINK_JOB_LIFECYCLE_MAJOR_FIXES_VERSION,
        "primary_surface": "thinkbox/think_job_lifecycle_major_fixes + F023 lifecycle",
        "fixes_manifest_rel": str(FIXES_MANIFEST_REL),
        "violation_count": len(violations),
        "violation_codes": [v.code for v in violations],
    }
