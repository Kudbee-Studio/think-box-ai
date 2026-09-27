"""Hermetic gate for durable RUNNING orphan reclaim (stacked on QUEUED resume)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from thinkbox.kilo_live_proof_readiness import REPO_ROOT
from thinkbox.lifecycle_reclaim import GATE_ID, lifecycle_reclaim_contract_summary

PR204_PASS_REL = Path("docs/audit/passes/2026-09-24-pr204.json")


def validate_reclaim_gate(repo_root: Path | None = None) -> tuple[bool, tuple[str, ...]]:
    root = repo_root if repo_root is not None else REPO_ROOT
    violations: list[str] = []
    summary = lifecycle_reclaim_contract_summary()
    if summary.get("gate_id") != GATE_ID:
        violations.append("gate_id")
    if summary.get("live_verified") is True:
        violations.append("live_verified")
    if summary.get("worker_pool") is True:
        violations.append("worker_pool")
    if summary.get("upstash_live_gate_touched") is True:
        violations.append("upstash_live_gate")
    if not (root / "thinkbox/lifecycle_reclaim.py").is_file():
        violations.append("reclaim_module")
    if not (root / "thinkbox/lifecycle_lease.py").is_file():
        violations.append("lease_module")
    if not (root / PR204_PASS_REL).is_file():
        violations.append("audit_pass")
    return (len(violations) == 0, tuple(violations))


def lifecycle_reclaim_gate_summary(repo_root: Path | None = None) -> dict[str, Any]:
    ok, violations = validate_reclaim_gate(repo_root=repo_root)
    summary = lifecycle_reclaim_contract_summary()
    summary["hermetic_operator_ok"] = ok
    summary["violations"] = list(violations)
    return summary
