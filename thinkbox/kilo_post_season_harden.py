"""Hermetic post-season ops harden contracts (PR #151, ``post-season-harden``).

Post-arc #141–#150 maintenance: CI spine alignment, branch hygiene tooling, docs sync.
Not an arc gate — layers on PR #150 ``live-proof-exec`` hermetic closure only.
Default path: no network; ``live_api_called=False``.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Mapping

from thinkbox.kilo_env_matrix import EnvMatrixMode, detect_matrix_mode
from thinkbox.kilo_live_proof_exec import (
    hermetic_live_proof_exec_operator_check,
    minimal_live_proof_exec_environ,
)
from thinkbox.kilo_live_proof_readiness import REPO_ROOT

__all__ = (
    "BRANCH_HYGIENE_SCRIPT_REL",
    "CI_WORKFLOW_REL",
    "GATE_ID",
    "POST_SEASON_CHECKLIST_REL",
    "PR_NUMBER",
    "SPINE_VERIFY_SCRIPTS",
    "PostSeasonHardenEvidence",
    "PostSeasonHardenMode",
    "PostSeasonHardenResult",
    "PostSeasonHardenViolation",
    "evaluate_post_season_harden",
    "hermetic_post_season_harden_operator_check",
    "minimal_post_season_harden_environ",
    "post_season_harden_contract_summary",
    "post_season_harden_gate_closed",
    "validate_ci_workflow_manifest",
    "validate_post_season_checklist_document",
)

GATE_ID = "post-season-harden"
PR_NUMBER = 151

CI_WORKFLOW_REL = Path(".github/workflows/test.yml")
BRANCH_HYGIENE_SCRIPT_REL = Path("scripts/cleanup_merged_cursor_branches.py")
POST_SEASON_CHECKLIST_REL = Path("data/kilo_post_season_harden/checklist.json")
_VERIFY_SCRIPT_REL = Path("scripts/verify_kilo_post_season_harden.py")
_RUNBOOK_BRANCH_HYGIENE_REL = Path("docs/runbooks/branch-hygiene.md")

SPINE_VERIFY_SCRIPTS: tuple[Path, ...] = (
    Path("scripts/verify_kilo_env_matrix.py"),
    Path("scripts/verify_kilo_substrate_checklist.py"),
    Path("scripts/verify_kilo_governance_evidence.py"),
    Path("scripts/verify_kilo_mercury_hermetic.py"),
    Path("scripts/verify_kilo_swarm_instrumentation.py"),
    Path("scripts/verify_kilo_proof_schema.py"),
    Path("scripts/verify_kilo_dashboard_slots.py"),
    Path("scripts/verify_kilo_live_proof_exec.py"),
    Path("scripts/verify_kilo_post_season_harden.py"),
    Path("scripts/verify_kilo_live_smoke_evidence.py"),
    Path("scripts/verify_kilo_live_smoke_operator.py"),
    Path("scripts/verify_kilo_control_plane_api.py"),
    Path("scripts/verify_kilo_spine.py"),
    Path("scripts/scan_doc_secrets.py"),
)

_REQUIRED_CI_SNIPPETS: tuple[str, ...] = (
    "verify_kilo_spine.py",
    "scan_doc_secrets.py",
    "verify_kilo_post_season_harden.py",
    "verify_kilo_live_smoke_evidence.py",
    "verify_kilo_live_smoke_operator.py",
    "verify_kilo_control_plane_api.py",
)

_FORBIDDEN_LITERAL_CLAIMS = (
    "KILO LIVE VERIFIED",
    "KILO PRODUCTION READY",
    "KILO live build verified",
)


class PostSeasonHardenMode(str, Enum):
    """Alias of env-matrix modes for post-season reporting."""

    HERMETIC_UNIT = EnvMatrixMode.HERMETIC_UNIT.value
    HERMETIC_CI = EnvMatrixMode.HERMETIC_CI.value
    LIVE_PROOF_PREP = EnvMatrixMode.LIVE_PROOF_PREP.value


@dataclass(frozen=True)
class PostSeasonHardenViolation:
    """Single fail-closed post-season violation."""

    code: str
    message: str
    path: str | None = None


@dataclass(frozen=True)
class PostSeasonHardenEvidence:
    """Hermetic evidence bundle for PR #151."""

    live_proof_exec_ok: bool
    ci_workflow_ok: bool
    spine_scripts_present: bool
    branch_hygiene_script_present: bool
    checklist_ok: bool
    live_api_called: bool = False
    four_state_max: str = "TEST_VERIFIED"


@dataclass(frozen=True)
class PostSeasonHardenResult:
    """Outcome of post-season harden evaluation."""

    mode: PostSeasonHardenMode
    ok: bool
    live_proof_exec_ok: bool
    violations: tuple[PostSeasonHardenViolation, ...]
    evidence: PostSeasonHardenEvidence | None = None


def validate_ci_workflow_manifest(text: str) -> tuple[bool, tuple[PostSeasonHardenViolation, ...]]:
    """Ensure CI workflow references spine + secrets scan + post-season gate."""
    violations: list[PostSeasonHardenViolation] = []
    for snippet in _REQUIRED_CI_SNIPPETS:
        if snippet not in text:
            violations.append(
                PostSeasonHardenViolation(
                    code="ci_workflow_missing_snippet",
                    message=f"CI workflow must reference {snippet}",
                    path=str(CI_WORKFLOW_REL),
                )
            )
    if "python3 -m unittest discover" not in text:
        violations.append(
            PostSeasonHardenViolation(
                code="ci_workflow_missing_unittest_discover",
                message="CI workflow must run unittest discover",
                path=str(CI_WORKFLOW_REL),
            )
        )
    return (len(violations) == 0, tuple(violations))


def validate_post_season_checklist_document(
    doc: Mapping[str, Any],
) -> tuple[bool, tuple[PostSeasonHardenViolation, ...]]:
    """Validate frozen post-season checklist JSON."""
    violations: list[PostSeasonHardenViolation] = []
    required_keys = (
        "schema_version",
        "gate_id",
        "pr_number",
        "arc_season_marker",
        "four_state_max",
        "live_verified",
        "ci_workflow_rel",
        "spine_verify_scripts",
        "branch_hygiene_script",
    )
    for key in required_keys:
        if key not in doc:
            violations.append(
                PostSeasonHardenViolation(
                    code="checklist_missing_key",
                    message=f"Missing key {key}",
                    path=str(POST_SEASON_CHECKLIST_REL),
                )
            )
    if doc.get("gate_id") != GATE_ID:
        violations.append(
            PostSeasonHardenViolation(
                code="checklist_gate_id",
                message="gate_id must be post-season-harden",
            )
        )
    if doc.get("pr_number") != PR_NUMBER:
        violations.append(
            PostSeasonHardenViolation(
                code="checklist_pr_number",
                message="pr_number must be 151",
            )
        )
    if doc.get("live_verified") is True:
        violations.append(
            PostSeasonHardenViolation(
                code="live_verified_forbidden",
                message="live_verified must be false in hermetic checklist",
            )
        )
    scripts = doc.get("spine_verify_scripts")
    if not isinstance(scripts, list) or len(scripts) < len(SPINE_VERIFY_SCRIPTS):
        violations.append(
            PostSeasonHardenViolation(
                code="checklist_spine_scripts",
                message="spine_verify_scripts must list all spine operator scripts",
            )
        )
    return (len(violations) == 0, tuple(violations))


def _check_spine_scripts_present() -> tuple[bool, tuple[PostSeasonHardenViolation, ...]]:
    violations: list[PostSeasonHardenViolation] = []
    for rel in SPINE_VERIFY_SCRIPTS:
        if not (REPO_ROOT / rel).is_file():
            violations.append(
                PostSeasonHardenViolation(
                    code="spine_script_missing",
                    message=f"Missing spine script {rel}",
                    path=str(rel),
                )
            )
    return (len(violations) == 0, tuple(violations))


def evaluate_post_season_harden(
    mode: EnvMatrixMode | PostSeasonHardenMode,
    environ: Mapping[str, str],
    *,
    run_checklist: bool = True,
) -> PostSeasonHardenResult:
    """Evaluate post-season harden gate (hermetic only)."""
    resolved = (
        PostSeasonHardenMode(mode.value)
        if isinstance(mode, EnvMatrixMode)
        else mode
    )
    violations: list[PostSeasonHardenViolation] = []

    live_exec = hermetic_live_proof_exec_operator_check(environ)
    live_proof_exec_ok = live_exec.ok
    if not live_proof_exec_ok:
        violations.append(
            PostSeasonHardenViolation(
                code="live_proof_exec_layer_failed",
                message="PR #150 live-proof-exec hermetic layer must pass first",
            )
        )

    ci_path = REPO_ROOT / CI_WORKFLOW_REL
    ci_ok = False
    if ci_path.is_file():
        ci_ok, ci_v = validate_ci_workflow_manifest(ci_path.read_text(encoding="utf-8"))
        violations.extend(ci_v)
    else:
        violations.append(
            PostSeasonHardenViolation(
                code="ci_workflow_missing",
                message="CI workflow file missing",
                path=str(CI_WORKFLOW_REL),
            )
        )

    scripts_ok, script_v = _check_spine_scripts_present()
    violations.extend(script_v)

    hygiene_ok = (REPO_ROOT / BRANCH_HYGIENE_SCRIPT_REL).is_file()
    if not hygiene_ok:
        violations.append(
            PostSeasonHardenViolation(
                code="branch_hygiene_script_missing",
                message="Branch hygiene script must exist",
                path=str(BRANCH_HYGIENE_SCRIPT_REL),
            )
        )

    runbook_ok = (REPO_ROOT / _RUNBOOK_BRANCH_HYGIENE_REL).is_file()
    if not runbook_ok:
        violations.append(
            PostSeasonHardenViolation(
                code="branch_hygiene_runbook_missing",
                message="Branch hygiene runbook must exist",
                path=str(_RUNBOOK_BRANCH_HYGIENE_REL),
            )
        )

    checklist_ok = False
    if run_checklist:
        checklist_path = REPO_ROOT / POST_SEASON_CHECKLIST_REL
        if checklist_path.is_file():
            doc = json.loads(checklist_path.read_text(encoding="utf-8"))
            checklist_ok, checklist_v = validate_post_season_checklist_document(doc)
            violations.extend(checklist_v)
        else:
            violations.append(
                PostSeasonHardenViolation(
                    code="checklist_missing",
                    message="Post-season checklist JSON missing",
                    path=str(POST_SEASON_CHECKLIST_REL),
                )
            )

    verify_ok = (REPO_ROOT / _VERIFY_SCRIPT_REL).is_file()
    if not verify_ok:
        violations.append(
            PostSeasonHardenViolation(
                code="verify_script_missing",
                message="verify_kilo_post_season_harden.py must exist",
                path=str(_VERIFY_SCRIPT_REL),
            )
        )

    for claim in _FORBIDDEN_LITERAL_CLAIMS:
        if claim in os.environ.get("THINKBOX_KILO_CLAIM", ""):
            violations.append(
                PostSeasonHardenViolation(
                    code="forbidden_claim_in_env",
                    message="Forbidden KILO claim in THINKBOX_KILO_CLAIM",
                )
            )

    ok = (
        live_proof_exec_ok
        and ci_ok
        and scripts_ok
        and hygiene_ok
        and runbook_ok
        and checklist_ok
        and verify_ok
        and len(violations) == 0
    )
    evidence = PostSeasonHardenEvidence(
        live_proof_exec_ok=live_proof_exec_ok,
        ci_workflow_ok=ci_ok,
        spine_scripts_present=scripts_ok,
        branch_hygiene_script_present=hygiene_ok,
        checklist_ok=checklist_ok,
    )
    return PostSeasonHardenResult(
        mode=resolved,
        ok=ok,
        live_proof_exec_ok=live_proof_exec_ok,
        violations=violations if not ok else (),
        evidence=evidence,
    )


def minimal_post_season_harden_environ(
    extra: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Minimal env for hermetic post-season checks."""
    env = dict(minimal_live_proof_exec_environ())
    env.setdefault("CI", "true")
    if extra:
        env.update(extra)
    return env


def hermetic_post_season_harden_operator_check(
    environ: Mapping[str, str] | None = None,
) -> PostSeasonHardenResult:
    env: Mapping[str, str] = environ if environ is not None else os.environ
    return evaluate_post_season_harden(detect_matrix_mode(env), env)


def post_season_harden_gate_closed() -> bool:
    env = minimal_post_season_harden_environ()
    unit = evaluate_post_season_harden(EnvMatrixMode.HERMETIC_UNIT, env)
    op = hermetic_post_season_harden_operator_check(env)
    return unit.ok and op.ok


def post_season_harden_contract_summary(
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    env = environ if environ is not None else os.environ
    mode = detect_matrix_mode(env)
    operator = hermetic_post_season_harden_operator_check(env)
    return {
        "gate_id": GATE_ID,
        "pr_number": PR_NUMBER,
        "pr151_gate_id": GATE_ID,
        "detected_mode": mode.value,
        "live_proof_exec_layer": True,
        "hermetic_operator_ok": operator.ok,
        "live_proof_exec_ok": operator.live_proof_exec_ok,
        "ci_workflow_rel": str(CI_WORKFLOW_REL),
        "branch_hygiene_script": str(BRANCH_HYGIENE_SCRIPT_REL),
        "post_season_checklist": str(POST_SEASON_CHECKLIST_REL),
        "spine_verify_script_count": len(SPINE_VERIFY_SCRIPTS),
        "hermetic_violation_codes": sorted({v.code for v in operator.violations}),
        "live_api_called": False,
        "four_state_max": "TEST_VERIFIED",
        "live_proof_in_this_pr": False,
        "arc_season_complete": True,
        "ops_harden_not_live_gate": True,
        "gate_closed_default": post_season_harden_gate_closed(),
        "verify_script": str(_VERIFY_SCRIPT_REL),
        "verify_script_present": (REPO_ROOT / _VERIFY_SCRIPT_REL).is_file(),
    }
