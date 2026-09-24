"""Hermetic Think Job lifecycle integration fix pack (PR #185)."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from thinkbox.kilo_live_proof_readiness import REPO_ROOT
from thinkbox.think_job_lifecycle_fixes.negotiation import (
    GATE_ID,
    THINK_JOB_LIFECYCLE_FIXES_VERSION,
)

__all__ = (
    "EXPECTED_FIX_COUNT",
    "EXPECTED_LOCAL_STEP_COUNT",
    "FIXES_MANIFEST_REL",
    "GATE_ID",
    "LOCAL_SETUP_MANIFEST_REL",
    "PR185_PASS_REL",
    "PR_NUMBER",
    "ThinkJobLifecycleFixViolation",
    "load_fixes_manifest",
    "load_local_setup_manifest",
    "local_environment_contract_summary",
    "think_job_lifecycle_fixes_contract_summary",
    "validate_fixes_manifest",
    "validate_local_setup_manifest",
)

PR_NUMBER = 185
EXPECTED_FIX_COUNT = 25
EXPECTED_LOCAL_STEP_COUNT = 8

FIXES_MANIFEST_REL = Path("data/think_job/pr185_fixes.json")
LOCAL_SETUP_MANIFEST_REL = Path("data/think_job/pr185_local_setup.json")
PR185_PASS_REL = Path("docs/audit/passes/2026-09-24-pr185.json")
LOCAL_RUNBOOK_REL = Path("docs/runbooks/think-job-pr185-local-environment.md")


@dataclass(frozen=True)
class ThinkJobLifecycleFixViolation:
    code: str
    message: str
    path: str | None = None


def load_fixes_manifest(repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root if repo_root is not None else REPO_ROOT
    return json.loads((root / FIXES_MANIFEST_REL).read_text(encoding="utf-8"))


def load_local_setup_manifest(repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root if repo_root is not None else REPO_ROOT
    return json.loads((root / LOCAL_SETUP_MANIFEST_REL).read_text(encoding="utf-8"))


def validate_fixes_manifest(
    doc: Mapping[str, Any] | None = None,
    repo_root: Path | None = None,
) -> tuple[bool, tuple[ThinkJobLifecycleFixViolation, ...]]:
    root = repo_root if repo_root is not None else REPO_ROOT
    violations: list[ThinkJobLifecycleFixViolation] = []
    if doc is None:
        doc = load_fixes_manifest(root)

    if doc.get("gate_id") != GATE_ID:
        violations.append(ThinkJobLifecycleFixViolation("gate_id", "gate_id mismatch"))
    if doc.get("pr_number") != PR_NUMBER:
        violations.append(ThinkJobLifecycleFixViolation("pr_number", "pr_number mismatch"))
    if doc.get("live_verified") is True:
        violations.append(ThinkJobLifecycleFixViolation("live_verified", "must be false"))
    fixes = list(doc.get("fixes") or [])
    if len(fixes) != EXPECTED_FIX_COUNT:
        violations.append(
            ThinkJobLifecycleFixViolation("fix_count", f"expected {EXPECTED_FIX_COUNT} fixes"),
        )
    seen: set[str] = set()
    for fix in fixes:
        fid = str(fix.get("id", ""))
        if fid in seen:
            violations.append(ThinkJobLifecycleFixViolation("duplicate_fix_id", fid))
        seen.add(fid)
        rel = fix.get("module")
        if not rel or not (root / str(rel)).is_file():
            violations.append(
                ThinkJobLifecycleFixViolation("fix_module_missing", str(rel), path=str(rel)),
            )

    quickstart = root / "docs/guides/think_job_lifecycle_fixes_quickstart.md"
    if not quickstart.is_file():
        violations.append(ThinkJobLifecycleFixViolation("quickstart_doc", "missing quickstart"))

    example = root / "examples/think_job_lifecycle_fixes_quickstart.py"
    if not example.is_file():
        violations.append(ThinkJobLifecycleFixViolation("quickstart_example", "missing example"))

    checklist = root / "data/think_job/pr185_checklist.json"
    if not checklist.is_file():
        violations.append(ThinkJobLifecycleFixViolation("checklist", "missing checklist"))

    cassette = root / "data/think_job/cassettes/lifecycle_fix_flow.json"
    if not cassette.is_file():
        violations.append(ThinkJobLifecycleFixViolation("cassette_fixture", "missing cassette"))

    audit = root / PR185_PASS_REL
    if not audit.is_file():
        violations.append(ThinkJobLifecycleFixViolation("audit_pass", "missing audit pass"))

    return (len(violations) == 0, tuple(violations))


def validate_local_setup_manifest(
    doc: Mapping[str, Any] | None = None,
    repo_root: Path | None = None,
) -> tuple[bool, tuple[ThinkJobLifecycleFixViolation, ...]]:
    root = repo_root if repo_root is not None else REPO_ROOT
    violations: list[ThinkJobLifecycleFixViolation] = []
    if doc is None:
        doc = load_local_setup_manifest(root)
    steps = list(doc.get("steps") or [])
    if len(steps) != EXPECTED_LOCAL_STEP_COUNT:
        violations.append(
            ThinkJobLifecycleFixViolation("local_step_count", "local step count mismatch"),
        )
    for step in steps:
        rel = step.get("module")
        if not rel or not (root / str(rel)).is_file():
            violations.append(
                ThinkJobLifecycleFixViolation("local_module_missing", str(rel), path=str(rel)),
            )
    for script in doc.get("scripts") or []:
        if not (root / str(script)).is_file():
            violations.append(
                ThinkJobLifecycleFixViolation("local_script_missing", str(script), path=str(script)),
            )
    runbook = root / str(doc.get("runbook") or LOCAL_RUNBOOK_REL)
    if not runbook.is_file():
        violations.append(ThinkJobLifecycleFixViolation("local_runbook", "missing runbook"))
    return (len(violations) == 0, tuple(violations))


def local_environment_contract_summary(
    repo_root: Path | None = None,
    *,
    run_workflow: bool = False,
) -> dict[str, Any]:
    root = repo_root if repo_root is not None else REPO_ROOT
    manifest_ok, violations = validate_local_setup_manifest(repo_root=root)
    workflow_ok = True
    workflow_summary: dict[str, Any] | None = None
    if run_workflow:
        from thinkbox.think_job_lifecycle_fixes.local.steps_registry import run_all_local_steps

        workflow_summary = run_all_local_steps()
        workflow_ok = bool(workflow_summary.get("all_ok"))
    return {
        "gate_id": GATE_ID,
        "local_environment_ok": manifest_ok and workflow_ok,
        "local_setup_manifest_ok": manifest_ok,
        "local_workflow_ok": workflow_ok,
        "local_step_count": EXPECTED_LOCAL_STEP_COUNT,
        "workflow": workflow_summary,
        "violation_codes": [v.code for v in violations],
        "live_verified": False,
        "live_api_called": False,
    }


def think_job_lifecycle_fixes_contract_summary(repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root if repo_root is not None else REPO_ROOT
    fixes_ok, violations = validate_fixes_manifest(repo_root=root)
    local_ok, local_violations = validate_local_setup_manifest(repo_root=root)
    violations = (*violations, *local_violations)
    ok = fixes_ok and local_ok
    return {
        "gate_id": GATE_ID,
        "pr_number": PR_NUMBER,
        "pr185_gate_id": GATE_ID,
        "hermetic_operator_ok": ok,
        "local_setup_manifest_ok": local_ok,
        "live_verified": False,
        "live_api_called": False,
        "four_state_max": "TEST_VERIFIED",
        "combined_umbrella_nested": False,
        "fix_count": EXPECTED_FIX_COUNT,
        "fixes_manifest_ok": fixes_ok,
        "local_setup_manifest_rel": str(LOCAL_SETUP_MANIFEST_REL),
        "think_job_lifecycle_fixes_version": THINK_JOB_LIFECYCLE_FIXES_VERSION,
        "primary_surface": "thinkbox/think_job_lifecycle_fixes (F131–F140 glue)",
        "fixes_manifest_rel": str(FIXES_MANIFEST_REL),
        "violation_count": len(violations),
        "violation_codes": [v.code for v in violations],
    }
