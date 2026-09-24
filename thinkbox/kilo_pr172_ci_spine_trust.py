"""Hermetic CI spine-trust contracts (PR #172, ``ci-spine-trust``).

PR CI trusts one fast ``verify_kilo_spine.py`` pass plus explicit beyond-KILO lint
execute — not per-gate duplicate ``verify_kilo_*`` invocations. Operator scripts
remain on disk for local runs.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Mapping

from thinkbox.kilo_env_matrix import EnvMatrixMode, detect_matrix_mode
from thinkbox.kilo_hermetic_gate_memo import memoized_hermetic_check
from thinkbox.kilo_live_proof_readiness import REPO_ROOT

__all__ = (
    "CHECKLIST_REL",
    "CI_WORKFLOW_REL",
    "FIXTURES_REL",
    "FORBIDDEN_REDUNDANT_CI_VERIFY_SCRIPTS",
    "GATE_ID",
    "PR172_PASS_REL",
    "PR_NUMBER",
    "REQUIRED_CI_SNIPPETS",
    "VERIFY_SCRIPT_REL",
    "CiSpineTrustEvidence",
    "CiSpineTrustResult",
    "CiSpineTrustViolation",
    "ci_spine_trust_contract_summary",
    "ci_spine_trust_gate_closed",
    "evaluate_ci_spine_trust",
    "hermetic_ci_spine_trust_check",
    "minimal_ci_spine_trust_environ",
    "run_ci_spine_trust_fixture_suite",
    "validate_checklist_document",
    "validate_pr172_ci_workflow_manifest",
)

GATE_ID = "ci-spine-trust"
PR_NUMBER = 172

CI_WORKFLOW_REL = Path(".github/workflows/test.yml")
VERIFY_SCRIPT_REL = Path("scripts/verify_kilo_pr172_ci_spine_trust.py")
CHECKLIST_REL = Path("data/kilo_pr172_ci_spine_trust/checklist.json")
FIXTURES_REL = Path("data/kilo_pr172_ci_spine_trust/fixtures")
PR172_PASS_REL = Path("docs/audit/passes/2026-09-24-pr172.json")

REQUIRED_CI_SNIPPETS: tuple[str, ...] = (
    "python3 -m unittest discover",
    "verify_kilo_spine.py",
    'pip install -e ".[lint]"',
    "KILO_BEYOND_KILO_LINT_EXECUTE=1",
    "verify_kilo_beyond_kilo_lint.py",
    "scan_doc_secrets.py",
)

FORBIDDEN_REDUNDANT_CI_VERIFY_SCRIPTS: tuple[str, ...] = (
    "verify_kilo_post_season_harden.py",
    "verify_kilo_live_smoke_evidence.py",
    "verify_kilo_live_smoke_operator.py",
    "verify_kilo_control_plane_api.py",
    "verify_kilo_receipt_chain_etag.py",
    "verify_kilo_dashboard_receipt_chain_bind.py",
    "verify_kilo_api_ops_harden.py",
    "verify_kilo_end_link_deepen.py",
    "verify_kilo_end_link_operator_ux.py",
    "verify_kilo_receipt_chain_end_link_docs.py",
    "verify_kilo_end_link_api_ops_harden.py",
    "verify_kilo_receipt_chain_end_link_era_close.py",
    "verify_kilo_control_plane_e2e_deepen.py",
    "verify_kilo_governance_evidence_live_proof_readiness.py",
    "verify_kilo_live_smoke_audit_flip_harden.py",
    "verify_kilo_control_plane_post164_deepen.py",
    "verify_kilo_receipt_chain_end_link_season_harden.py",
    "verify_kilo_pr165_combined_harden.py",
    "verify_kilo_live_proof_operator_prep_deepen.py",
    "verify_kilo_api_ops_harden_post165.py",
    "verify_kilo_dashboard_pr165_gates_bind.py",
    "verify_kilo_swarm_governance_post165_deepen.py",
    "verify_kilo_pr166_combined_post165_lane.py",
    "verify_kilo_live_proof_operator_audit_flip_deepen.py",
    "verify_kilo_api_ops_harden_post166.py",
    "verify_kilo_dashboard_pr166_gates_bind.py",
    "verify_kilo_swarm_governance_post166_deepen.py",
    "verify_kilo_pr167_combined_post166_lane.py",
    "verify_kilo_live_proof_operator_audit_flip_post167.py",
    "verify_kilo_api_ops_harden_post167.py",
    "verify_kilo_dashboard_pr167_gates_bind.py",
    "verify_kilo_swarm_governance_post167_deepen.py",
    "verify_kilo_pr168_combined_post167_lane.py",
    "verify_kilo_live_proof_operator_audit_flip_post168.py",
    "verify_kilo_api_ops_harden_post168.py",
    "verify_kilo_dashboard_pr168_gates_bind.py",
    "verify_kilo_swarm_governance_post168_deepen.py",
    "verify_kilo_pr169_combined_post168_lane.py",
)


class CiSpineTrustMode(str, Enum):
    HERMETIC_UNIT = EnvMatrixMode.HERMETIC_UNIT.value
    HERMETIC_CI = EnvMatrixMode.HERMETIC_CI.value


@dataclass(frozen=True)
class CiSpineTrustViolation:
    """Single fail-closed CI manifest violation."""

    code: str
    message: str
    path: str | None = None


@dataclass(frozen=True)
class CiSpineTrustEvidence:
    ci_workflow_ok: bool
    checklist_ok: bool
    fixtures_ok: bool
    verify_script_present: bool
    audit_pass_ok: bool
    live_api_called: bool = False
    four_state_max: str = "TEST_VERIFIED"


@dataclass(frozen=True)
class CiSpineTrustResult:
    mode: CiSpineTrustMode
    ok: bool
    violations: tuple[CiSpineTrustViolation, ...]
    evidence: CiSpineTrustEvidence | None = None


def validate_pr172_ci_workflow_manifest(
    text: str,
) -> tuple[bool, tuple[CiSpineTrustViolation, ...]]:
    """Ensure PR CI matches spine-trust + explicit beyond-KILO lint execute."""
    violations: list[CiSpineTrustViolation] = []
    for snippet in REQUIRED_CI_SNIPPETS:
        if snippet not in text:
            violations.append(
                CiSpineTrustViolation(
                    code="ci_workflow_missing_snippet",
                    message=f"CI workflow must reference {snippet}",
                    path=str(CI_WORKFLOW_REL),
                )
            )
    if "verify_kilo_spine.py --e2e" in text:
        violations.append(
            CiSpineTrustViolation(
                code="ci_workflow_e2e_default_forbidden",
                message="PR CI must not default to verify_kilo_spine.py --e2e",
                path=str(CI_WORKFLOW_REL),
            )
        )
    for script in FORBIDDEN_REDUNDANT_CI_VERIFY_SCRIPTS:
        if script in text:
            violations.append(
                CiSpineTrustViolation(
                    code="ci_workflow_redundant_verify_script",
                    message=(
                        f"CI must not duplicate spine-covered gate {script}; "
                        "trust verify_kilo_spine.py"
                    ),
                    path=str(CI_WORKFLOW_REL),
                )
            )
    return (len(violations) == 0, tuple(violations))


def validate_checklist_document(
    doc: Mapping[str, Any],
) -> tuple[bool, tuple[CiSpineTrustViolation, ...]]:
    """Validate frozen PR #172 checklist JSON."""
    violations: list[CiSpineTrustViolation] = []
    for key in (
        "gate_id",
        "pr_number",
        "live_verified",
        "ci_workflow_rel",
        "required_ci_snippets",
        "trust_model",
    ):
        if key not in doc:
            violations.append(
                CiSpineTrustViolation(
                    code="checklist_missing_key",
                    message=f"Missing key {key}",
                    path=str(CHECKLIST_REL),
                )
            )
    if doc.get("gate_id") != GATE_ID:
        violations.append(
            CiSpineTrustViolation(
                code="checklist_gate_id",
                message="gate_id must be ci-spine-trust",
            )
        )
    if doc.get("pr_number") != PR_NUMBER:
        violations.append(
            CiSpineTrustViolation(
                code="checklist_pr_number",
                message="pr_number must be 172",
            )
        )
    if doc.get("live_verified") is True:
        violations.append(
            CiSpineTrustViolation(
                code="live_verified_forbidden",
                message="live_verified must be false",
            )
        )
    snippets = doc.get("required_ci_snippets")
    if not isinstance(snippets, list):
        violations.append(
            CiSpineTrustViolation(
                code="checklist_snippets",
                message="required_ci_snippets must be a list",
            )
        )
    else:
        for required in REQUIRED_CI_SNIPPETS:
            if required not in snippets:
                violations.append(
                    CiSpineTrustViolation(
                        code="checklist_snippet_missing",
                        message=f"checklist must include snippet {required}",
                    )
                )
    return (len(violations) == 0, tuple(violations))


def run_ci_spine_trust_fixture_suite() -> tuple[int, int, list[str]]:
    """Run positive/negative workflow fixture checks."""
    errors: list[str] = []
    positive = 0
    negative = 0
    fixtures_dir = REPO_ROOT / FIXTURES_REL
    if not fixtures_dir.is_dir():
        return 0, 0, ["fixtures directory missing"]
    for path in sorted(fixtures_dir.glob("*.yml")):
        text = path.read_text(encoding="utf-8")
        ok, viols = validate_pr172_ci_workflow_manifest(text)
        expect_ok = path.name.startswith("valid_")
        if expect_ok:
            positive += 1
            if not ok:
                errors.append(f"{path.name}: expected pass got {viols}")
        else:
            negative += 1
            if ok:
                errors.append(f"{path.name}: expected fail")
    return positive, negative, errors


def evaluate_ci_spine_trust(
    mode: CiSpineTrustMode | EnvMatrixMode | str,
    environ: Mapping[str, str],
    *,
    run_fixtures: bool = True,
) -> CiSpineTrustResult:
    resolved = (
        mode
        if isinstance(mode, CiSpineTrustMode)
        else CiSpineTrustMode(mode)
        if isinstance(mode, str)
        else CiSpineTrustMode(mode.value)
    )
    violations: list[CiSpineTrustViolation] = []

    workflow_path = REPO_ROOT / CI_WORKFLOW_REL
    ci_ok = False
    if workflow_path.is_file():
        ci_ok, ci_v = validate_pr172_ci_workflow_manifest(
            workflow_path.read_text(encoding="utf-8")
        )
        violations.extend(ci_v)
    else:
        violations.append(
            CiSpineTrustViolation(
                code="ci_workflow_missing",
                message="CI workflow file missing",
                path=str(CI_WORKFLOW_REL),
            )
        )

    checklist_ok = False
    checklist_path = REPO_ROOT / CHECKLIST_REL
    if checklist_path.is_file():
        doc = json.loads(checklist_path.read_text(encoding="utf-8"))
        checklist_ok, checklist_v = validate_checklist_document(doc)
        violations.extend(checklist_v)
    else:
        violations.append(
            CiSpineTrustViolation(
                code="checklist_missing",
                message="PR172 checklist JSON missing",
                path=str(CHECKLIST_REL),
            )
        )

    fixtures_ok = True
    if run_fixtures:
        pos, neg, fixture_errors = run_ci_spine_trust_fixture_suite()
        fixtures_ok = len(fixture_errors) == 0 and pos > 0 and neg > 0
        for err in fixture_errors:
            violations.append(
                CiSpineTrustViolation(code="fixture_failed", message=err)
            )

    verify_script_present = (REPO_ROOT / VERIFY_SCRIPT_REL).is_file()
    if not verify_script_present:
        violations.append(
            CiSpineTrustViolation(
                code="verify_script_missing",
                message="verify_kilo_pr172_ci_spine_trust.py must exist",
                path=str(VERIFY_SCRIPT_REL),
            )
        )

    audit_pass_ok = False
    audit_path = REPO_ROOT / PR172_PASS_REL
    if audit_path.is_file():
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        audit_pass_ok = (
            audit.get("gate_id") == GATE_ID
            and audit.get("live_verified") is False
            and audit.get("live_api_called") is False
        )
        if not audit_pass_ok:
            violations.append(
                CiSpineTrustViolation(
                    code="audit_pass_honesty",
                    message="PR172 audit pass must deny live claims",
                    path=str(PR172_PASS_REL),
                )
            )
    else:
        violations.append(
            CiSpineTrustViolation(
                code="audit_pass_missing",
                message="PR172 audit pass JSON missing",
                path=str(PR172_PASS_REL),
            )
        )

    ok = (
        ci_ok
        and checklist_ok
        and fixtures_ok
        and verify_script_present
        and audit_pass_ok
        and len(violations) == 0
    )
    evidence = CiSpineTrustEvidence(
        ci_workflow_ok=ci_ok,
        checklist_ok=checklist_ok,
        fixtures_ok=fixtures_ok,
        verify_script_present=verify_script_present,
        audit_pass_ok=audit_pass_ok,
    )
    return CiSpineTrustResult(
        mode=resolved,
        ok=ok,
        violations=violations if not ok else (),
        evidence=evidence,
    )


def minimal_ci_spine_trust_environ(
    extra: Mapping[str, str] | None = None,
) -> dict[str, str]:
    env = {"CI": "true"}
    if extra:
        env.update(extra)
    return env


def hermetic_ci_spine_trust_check(
    environ: Mapping[str, str] | None = None,
) -> CiSpineTrustResult:
    env = environ if environ is not None else minimal_ci_spine_trust_environ()
    return memoized_hermetic_check(
        GATE_ID,
        env,
        lambda: evaluate_ci_spine_trust(detect_matrix_mode(env), env),
    )


def ci_spine_trust_gate_closed() -> bool:
    env = minimal_ci_spine_trust_environ()
    return evaluate_ci_spine_trust(CiSpineTrustMode.HERMETIC_UNIT, env).ok


def ci_spine_trust_contract_summary(
    workflow_text: str | None = None,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Hermetic summary for PR #172 CI-trust gate."""
    if workflow_text is None:
        workflow_path = REPO_ROOT / CI_WORKFLOW_REL
        workflow_text = workflow_path.read_text(encoding="utf-8")
    manifest_ok, manifest_violations = validate_pr172_ci_workflow_manifest(workflow_text)
    operator = hermetic_ci_spine_trust_check(environ)
    return {
        "gate_id": GATE_ID,
        "pr_number": PR_NUMBER,
        "pr172_gate_id": GATE_ID,
        "hermetic_operator_ok": operator.ok and manifest_ok,
        "ci_manifest_ok": manifest_ok,
        "live_verified": False,
        "live_api_called": False,
        "four_state_max": "TEST_VERIFIED",
        "combined_umbrella_nested": False,
        "ci_workflow_rel": str(CI_WORKFLOW_REL),
        "required_ci_snippets": list(REQUIRED_CI_SNIPPETS),
        "forbidden_redundant_script_count": len(FORBIDDEN_REDUNDANT_CI_VERIFY_SCRIPTS),
        "violation_count": len(manifest_violations),
        "violation_codes": [v.code for v in manifest_violations],
        "operator_violation_codes": sorted({v.code for v in operator.violations}),
        "gate_closed_default": ci_spine_trust_gate_closed(),
        "verify_script": str(VERIFY_SCRIPT_REL),
        "verify_script_present": (REPO_ROOT / VERIFY_SCRIPT_REL).is_file(),
        "checklist_rel": str(CHECKLIST_REL),
        "trust_spine_fast_default": True,
        "pr_ci_e2e_nested_forbidden": True,
    }
