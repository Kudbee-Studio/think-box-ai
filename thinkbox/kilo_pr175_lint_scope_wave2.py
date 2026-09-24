"""Hermetic lint scope wave 2 contracts (PR #175, ``lint-scope-wave2``).

Adds live-proof readiness spine modules (END_LINK, receipt-chain docs, operator
audit-flip deepen) on top of wave 1. Manifest:
``data/kilo_beyond_kilo_lint/wave2_scope.json``.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from thinkbox.beyond_kilo_lint import LINT_SCOPE_REL_PATHS
from thinkbox.kilo_live_proof_readiness import REPO_ROOT
from thinkbox.kilo_pr174_lint_scope_wave1 import load_wave1_scope_manifest

__all__ = (
    "EXPECTED_FULL_SCOPE_COUNT",
    "GATE_ID",
    "PR175_PASS_REL",
    "PR_NUMBER",
    "WAVE2_SCOPE_MANIFEST_REL",
    "LintScopeWave2Violation",
    "lint_scope_wave2_contract_summary",
    "load_wave2_scope_manifest",
    "validate_wave2_scope_manifest",
)

GATE_ID = "lint-scope-wave2"
PR_NUMBER = 175
EXPECTED_FULL_SCOPE_COUNT = 38

WAVE2_SCOPE_MANIFEST_REL = Path("data/kilo_beyond_kilo_lint/wave2_scope.json")
PR175_PASS_REL = Path("docs/audit/passes/2026-09-24-pr175.json")


@dataclass(frozen=True)
class LintScopeWave2Violation:
    code: str
    message: str
    path: str | None = None


def load_wave2_scope_manifest(repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root if repo_root is not None else REPO_ROOT
    path = root / WAVE2_SCOPE_MANIFEST_REL
    return json.loads(path.read_text(encoding="utf-8"))


def validate_wave2_scope_manifest(
    doc: Mapping[str, Any] | None = None,
    repo_root: Path | None = None,
) -> tuple[bool, tuple[LintScopeWave2Violation, ...]]:
    root = repo_root if repo_root is not None else REPO_ROOT
    violations: list[LintScopeWave2Violation] = []
    if doc is None:
        doc = load_wave2_scope_manifest(root)

    if doc.get("gate_id") != GATE_ID:
        violations.append(LintScopeWave2Violation(code="gate_id", message="gate_id mismatch"))
    if doc.get("pr_number") != PR_NUMBER:
        violations.append(LintScopeWave2Violation(code="pr_number", message="pr_number mismatch"))
    if doc.get("live_verified") is True:
        violations.append(LintScopeWave2Violation(code="live_verified", message="must be false"))
    if doc.get("scope_count") != EXPECTED_FULL_SCOPE_COUNT:
        violations.append(
            LintScopeWave2Violation(
                code="scope_count",
                message=f"expected {EXPECTED_FULL_SCOPE_COUNT}",
            ),
        )

    wave1 = load_wave1_scope_manifest(root)
    wave1_paths = tuple(wave1.get("scope_paths") or [])
    additive = tuple(doc.get("additive_paths") or [])
    full_paths = tuple(doc.get("scope_paths") or [])

    if len(additive) != doc.get("additive_scope_count"):
        violations.append(
            LintScopeWave2Violation(code="additive_count", message="additive mismatch")
        )

    for rel in wave1_paths:
        if rel not in LINT_SCOPE_REL_PATHS:
            violations.append(
                LintScopeWave2Violation(
                    code="wave1_subset",
                    message=f"wave1 path not in lint scope: {rel}",
                ),
            )

    if tuple(full_paths) != LINT_SCOPE_REL_PATHS:
        violations.append(
            LintScopeWave2Violation(
                code="lint_scope_drift",
                message="LINT_SCOPE_REL_PATHS must match wave2 manifest",
            ),
        )

    for rel in full_paths:
        if not (root / rel).is_file():
            violations.append(
                LintScopeWave2Violation(
                    code="scope_file_missing",
                    message=str(rel),
                    path=str(rel),
                ),
            )

    return (len(violations) == 0, tuple(violations))


def lint_scope_wave2_contract_summary(
    repo_root: Path | None = None,
) -> dict[str, Any]:
    root = repo_root if repo_root is not None else REPO_ROOT
    ok, violations = validate_wave2_scope_manifest(repo_root=root)
    return {
        "gate_id": GATE_ID,
        "pr_number": PR_NUMBER,
        "pr175_gate_id": GATE_ID,
        "hermetic_operator_ok": ok,
        "live_verified": False,
        "live_api_called": False,
        "four_state_max": "TEST_VERIFIED",
        "combined_umbrella_nested": False,
        "scope_count": len(LINT_SCOPE_REL_PATHS),
        "expected_scope_count": EXPECTED_FULL_SCOPE_COUNT,
        "wave2_manifest_rel": str(WAVE2_SCOPE_MANIFEST_REL),
        "violation_count": len(violations),
        "violation_codes": [v.code for v in violations],
    }
