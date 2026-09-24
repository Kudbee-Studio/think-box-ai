"""Hermetic lint scope wave 1 contracts (PR #174, ``lint-scope-wave1``).

Expands beyond-KILO lint to 25 spine / hermetic-helper modules per
``data/kilo_beyond_kilo_lint/wave1_scope.json``. Documents enterprise editing
commitments in ``docs/guides/kilo_enterprise_editing.md``.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from thinkbox.beyond_kilo_lint import LINT_SCOPE_REL_PATHS
from thinkbox.kilo_live_proof_readiness import REPO_ROOT

__all__ = (
    "ENTERPRISE_EDITING_GUIDE_REL",
    "EXPECTED_SCOPE_COUNT",
    "GATE_ID",
    "PR174_PASS_REL",
    "PR_NUMBER",
    "WAVE1_SCOPE_MANIFEST_REL",
    "LintScopeWave1Violation",
    "lint_scope_wave1_contract_summary",
    "load_wave1_scope_manifest",
    "validate_wave1_scope_manifest",
)

GATE_ID = "lint-scope-wave1"
PR_NUMBER = 174
EXPECTED_SCOPE_COUNT = 25

WAVE1_SCOPE_MANIFEST_REL = Path("data/kilo_beyond_kilo_lint/wave1_scope.json")
ENTERPRISE_EDITING_GUIDE_REL = Path("docs/guides/kilo_enterprise_editing.md")
PR174_PASS_REL = Path("docs/audit/passes/2026-09-24-pr174.json")


@dataclass(frozen=True)
class LintScopeWave1Violation:
    code: str
    message: str
    path: str | None = None


def load_wave1_scope_manifest(repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root if repo_root is not None else REPO_ROOT
    path = root / WAVE1_SCOPE_MANIFEST_REL
    return json.loads(path.read_text(encoding="utf-8"))


def validate_wave1_scope_manifest(
    doc: Mapping[str, Any] | None = None,
    repo_root: Path | None = None,
) -> tuple[bool, tuple[LintScopeWave1Violation, ...]]:
    """Fail closed if manifest, live LINT_SCOPE_REL_PATHS, and files disagree."""
    root = repo_root if repo_root is not None else REPO_ROOT
    violations: list[LintScopeWave1Violation] = []
    if doc is None:
        doc = load_wave1_scope_manifest(root)

    if doc.get("gate_id") != GATE_ID:
        violations.append(LintScopeWave1Violation(code="gate_id", message="gate_id mismatch"))
    if doc.get("pr_number") != PR_NUMBER:
        violations.append(LintScopeWave1Violation(code="pr_number", message="pr_number mismatch"))
    if doc.get("live_verified") is True:
        violations.append(LintScopeWave1Violation(code="live_verified", message="must be false"))
    if doc.get("scope_count") != EXPECTED_SCOPE_COUNT:
        violations.append(
            LintScopeWave1Violation(
                code="scope_count",
                message=f"expected {EXPECTED_SCOPE_COUNT}",
            ),
        )

    manifest_paths = tuple(doc.get("scope_paths") or [])
    if len(manifest_paths) != EXPECTED_SCOPE_COUNT:
        violations.append(
            LintScopeWave1Violation(
                code="manifest_path_count",
                message=f"manifest has {len(manifest_paths)} paths",
            ),
        )
    if tuple(manifest_paths) != LINT_SCOPE_REL_PATHS:
        violations.append(
            LintScopeWave1Violation(
                code="scope_paths_drift",
                message="LINT_SCOPE_REL_PATHS must match wave1_scope.json",
                path=str(WAVE1_SCOPE_MANIFEST_REL),
            ),
        )

    guide = root / ENTERPRISE_EDITING_GUIDE_REL
    if not guide.is_file():
        violations.append(
            LintScopeWave1Violation(
                code="enterprise_guide_missing",
                message="enterprise editing guide required",
                path=str(ENTERPRISE_EDITING_GUIDE_REL),
            ),
        )
    else:
        text = guide.read_text(encoding="utf-8")
        if "Twenty-five major commitments" not in text:
            violations.append(
                LintScopeWave1Violation(
                    code="commitments_missing",
                    message="guide must list 25 commitments",
                    path=str(ENTERPRISE_EDITING_GUIDE_REL),
                ),
            )

    for rel in manifest_paths:
        if not (root / rel).is_file():
            violations.append(
                LintScopeWave1Violation(
                    code="scope_file_missing",
                    message=str(rel),
                    path=str(rel),
                ),
            )

    return (len(violations) == 0, tuple(violations))


def lint_scope_wave1_contract_summary(
    repo_root: Path | None = None,
) -> dict[str, Any]:
    root = repo_root if repo_root is not None else REPO_ROOT
    ok, violations = validate_wave1_scope_manifest(repo_root=root)
    return {
        "gate_id": GATE_ID,
        "pr_number": PR_NUMBER,
        "pr174_gate_id": GATE_ID,
        "hermetic_operator_ok": ok,
        "live_verified": False,
        "live_api_called": False,
        "four_state_max": "TEST_VERIFIED",
        "combined_umbrella_nested": False,
        "scope_count": len(LINT_SCOPE_REL_PATHS),
        "expected_scope_count": EXPECTED_SCOPE_COUNT,
        "enterprise_editing_guide_rel": str(ENTERPRISE_EDITING_GUIDE_REL),
        "wave1_manifest_rel": str(WAVE1_SCOPE_MANIFEST_REL),
        "violation_count": len(violations),
        "violation_codes": [v.code for v in violations],
    }
