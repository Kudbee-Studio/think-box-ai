"""Hermetic gate for durable QUEUED resume (stacked on PR #202)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from thinkbox.kilo_live_proof_readiness import REPO_ROOT
from thinkbox.lifecycle_resume import GATE_ID, lifecycle_resume_contract_summary

PR203_PASS_REL = Path("docs/audit/passes/2026-09-24-pr203.json")


def validate_resume_gate(repo_root: Path | None = None) -> tuple[bool, tuple[str, ...]]:
    root = repo_root if repo_root is not None else REPO_ROOT
    violations: list[str] = []
    summary = lifecycle_resume_contract_summary()
    if summary.get("gate_id") != GATE_ID:
        violations.append("gate_id")
    if summary.get("live_verified") is True:
        violations.append("live_verified")
    if summary.get("orphaned_running_reclaim") is True:
        violations.append("orphan_reclaim_out_of_scope")
    if not (root / "thinkbox/lifecycle_resume.py").is_file():
        violations.append("resume_module")
    if not (root / PR203_PASS_REL).is_file():
        violations.append("audit_pass")
    return (len(violations) == 0, tuple(violations))


def lifecycle_resume_gate_summary(repo_root: Path | None = None) -> dict[str, Any]:
    ok, violations = validate_resume_gate(repo_root=repo_root)
    summary = lifecycle_resume_contract_summary()
    summary["hermetic_operator_ok"] = ok
    summary["violations"] = list(violations)
    return summary
