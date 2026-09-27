"""Hermetic CI spine-trust contracts (PR #172, ``ci-spine-trust``).

PR CI trusts one fast ``verify_kilo_spine.py`` pass plus explicit beyond-KILO lint
execute — not per-gate duplicate ``verify_kilo_*`` invocations. Operator scripts
remain on disk for local runs.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from thinkbox.kilo_live_proof_readiness import REPO_ROOT

__all__ = (
    "CI_WORKFLOW_REL",
    "FORBIDDEN_REDUNDANT_CI_VERIFY_SCRIPTS",
    "GATE_ID",
    "PR_NUMBER",
    "REQUIRED_CI_SNIPPETS",
    "CiSpineTrustViolation",
    "ci_spine_trust_contract_summary",
    "validate_pr172_ci_workflow_manifest",
)

GATE_ID = "ci-spine-trust"
PR_NUMBER = 172

CI_WORKFLOW_REL = Path(".github/workflows/test.yml")

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


@dataclass(frozen=True)
class CiSpineTrustViolation:
    """Single fail-closed CI manifest violation."""

    code: str
    message: str
    path: str | None = None


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


def ci_spine_trust_contract_summary(
    workflow_text: str | None = None,
) -> dict[str, Any]:
    """Hermetic summary for PR #172 CI-trust gate."""
    if workflow_text is None:
        workflow_path = REPO_ROOT / CI_WORKFLOW_REL
        workflow_text = workflow_path.read_text(encoding="utf-8")
    ok, violations = validate_pr172_ci_workflow_manifest(workflow_text)
    return {
        "gate_id": GATE_ID,
        "pr_number": PR_NUMBER,
        "pr172_gate_id": GATE_ID,
        "hermetic_operator_ok": ok,
        "live_verified": False,
        "live_api_called": False,
        "four_state_max": "TEST_VERIFIED",
        "combined_umbrella_nested": False,
        "ci_workflow_rel": str(CI_WORKFLOW_REL),
        "required_ci_snippets": list(REQUIRED_CI_SNIPPETS),
        "forbidden_redundant_script_count": len(FORBIDDEN_REDUNDANT_CI_VERIFY_SCRIPTS),
        "violation_count": len(violations),
        "violation_codes": [v.code for v in violations],
    }
