"""Hermetic dashboard PR #167 gates bind gate (PR #168 theme C)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, MutableMapping

from thinkbox.dashboard_pr167_gates_bind import (
    DASHBOARD_PR167_BIND_LABEL,
    DASHBOARD_PR167_BIND_VERSION,
    PR167_THEME_GATE_IDS,
    bind_pr167_gates_to_slots,
    dashboard_pr167_bind_contract_snippet,
)
from thinkbox.kilo_api_ops_harden_post166 import hermetic_api_ops_harden_post166_check
from thinkbox.kilo_dashboard_pr166_gates_bind import (
    hermetic_dashboard_pr166_gates_bind_check,
    minimal_dashboard_pr166_gates_bind_environ,
)
from thinkbox.kilo_dashboard_slots import (
    GATE_ID as DASHBOARD_SLOTS_GATE,
    hermetic_dashboard_slots_operator_check,
)
from thinkbox.kilo_env_matrix import EnvMatrixMode, detect_matrix_mode
from thinkbox.kilo_live_proof_operator_audit_flip_deepen import (
    hermetic_live_proof_operator_audit_flip_deepen_check,
)
from thinkbox.kilo_live_proof_readiness import REPO_ROOT
from thinkbox.kilo_pr167_combined_post166_lane import (
    GATE_ID as PR167_GATE_ID,
    hermetic_pr167_combined_post166_lane_check,
)
from thinkbox.kilo_swarm_governance_post166_deepen import (
    hermetic_swarm_governance_post166_deepen_check,
)

__all__ = (
    "CHECKLIST_REL",
    "GATE_ID",
    "HTML_REL",
    "PR_NUMBER",
    "VERIFY_SCRIPT_REL",
    "DashboardPr167BindEvidence",
    "DashboardPr167BindResult",
    "DashboardPr167BindViolation",
    "dashboard_pr167_gates_bind_contract_summary",
    "dashboard_pr167_gates_bind_gate_closed",
    "evaluate_dashboard_pr167_gates_bind",
    "hermetic_dashboard_pr167_gates_bind_check",
    "minimal_dashboard_pr167_gates_bind_environ",
    "validate_checklist_document",
)

GATE_ID = "dashboard-pr167-gates-bind"
PR_NUMBER = 168

VERIFY_SCRIPT_REL = Path("scripts/verify_kilo_dashboard_pr167_gates_bind.py")
CHECKLIST_REL = Path("data/kilo_dashboard_pr167_gates_bind/checklist.json")
HTML_REL = Path("public/control-plane/pr167_gates_status.html")


@dataclass(frozen=True)
class DashboardPr167BindViolation:
    code: str
    message: str
    path: str | None = None


@dataclass(frozen=True)
class DashboardPr167BindEvidence:
    gate_id: str
    pr_number: int
    dashboard_slots_ok: bool
    pr167_combined_ok: bool
    bound_slot_count: int
    live_api_called: bool = False
    four_state_max: str = "TEST_VERIFIED"


@dataclass(frozen=True)
class DashboardPr167BindResult:
    mode: EnvMatrixMode
    ok: bool
    violations: list[DashboardPr167BindViolation]
    evidence: DashboardPr167BindEvidence | None = None


def minimal_dashboard_pr167_gates_bind_environ(
    extra: Mapping[str, str] | None = None,
) -> dict[str, str]:
    base: MutableMapping[str, str] = dict(minimal_dashboard_pr166_gates_bind_environ())
    if extra:
        base.update(extra)
    return dict(base)


def validate_checklist_document(doc: Mapping[str, Any]) -> list[DashboardPr167BindViolation]:
    violations: list[DashboardPr167BindViolation] = []
    if doc.get("gate_id") != GATE_ID:
        violations.append(DashboardPr167BindViolation(code="gate_id", message="gate_id"))
    if doc.get("live_verified") is True:
        violations.append(DashboardPr167BindViolation(code="live_verified", message="false"))
    prior = doc.get("prior_gate_ids") or []
    if PR167_GATE_ID not in prior:
        violations.append(DashboardPr167BindViolation(code="prior_missing", message=PR167_GATE_ID))
    if DASHBOARD_SLOTS_GATE not in prior:
        violations.append(DashboardPr167BindViolation(code="prior_missing", message=DASHBOARD_SLOTS_GATE))
    return violations


def _theme_hermetic_map(env: Mapping[str, str]) -> dict[str, bool]:
    return {
        PR167_THEME_GATE_IDS[0]: hermetic_live_proof_operator_audit_flip_deepen_check(env).ok,
        PR167_THEME_GATE_IDS[1]: hermetic_api_ops_harden_post166_check(env).ok,
        PR167_THEME_GATE_IDS[2]: hermetic_dashboard_pr166_gates_bind_check(env).ok,
        PR167_THEME_GATE_IDS[3]: hermetic_swarm_governance_post166_deepen_check(env).ok,
    }


def evaluate_dashboard_pr167_gates_bind(
    mode: EnvMatrixMode | None = None,
    environ: Mapping[str, str] | None = None,
) -> DashboardPr167BindResult:
    env = environ if environ is not None else os.environ
    resolved = mode if mode is not None else detect_matrix_mode(env)
    violations: list[DashboardPr167BindViolation] = []

    slots = hermetic_dashboard_slots_operator_check(env)
    if not slots.ok:
        violations.append(DashboardPr167BindViolation(code="dashboard_slots", message=DASHBOARD_SLOTS_GATE))
    pr167 = hermetic_pr167_combined_post166_lane_check(env)
    if not pr167.ok:
        violations.append(DashboardPr167BindViolation(code="pr167_combined", message=PR167_GATE_ID))

    checklist = REPO_ROOT / CHECKLIST_REL
    if checklist.is_file():
        violations.extend(validate_checklist_document(json.loads(checklist.read_text())))
    else:
        violations.append(DashboardPr167BindViolation(code="checklist_missing", message=""))

    html = REPO_ROOT / HTML_REL
    if not html.is_file():
        violations.append(DashboardPr167BindViolation(code="html_missing", message=str(HTML_REL)))
    elif DASHBOARD_PR167_BIND_LABEL not in html.read_text(encoding="utf-8"):
        violations.append(DashboardPr167BindViolation(code="html_marker", message="label"))

    theme_map = _theme_hermetic_map(env)
    bound = bind_pr167_gates_to_slots(theme_map)
    if len(bound) != len(PR167_THEME_GATE_IDS):
        violations.append(DashboardPr167BindViolation(code="bind_count", message="count"))
    for row in bound:
        if row.get("live_verified") is True:
            violations.append(DashboardPr167BindViolation(code="slot_live_claim", message="forbidden"))

    ok = slots.ok and pr167.ok and len(violations) == 0
    evidence = DashboardPr167BindEvidence(
        gate_id=GATE_ID,
        pr_number=PR_NUMBER,
        dashboard_slots_ok=slots.ok,
        pr167_combined_ok=pr167.ok,
        bound_slot_count=len(bound),
    )
    return DashboardPr167BindResult(
        mode=resolved,
        ok=ok,
        violations=violations if not ok else [],
        evidence=evidence,
    )


def hermetic_dashboard_pr167_gates_bind_check(
    environ: Mapping[str, str] | None = None,
) -> DashboardPr167BindResult:
    env = environ if environ is not None else os.environ
    return evaluate_dashboard_pr167_gates_bind(detect_matrix_mode(env), env)


def dashboard_pr167_gates_bind_gate_closed() -> bool:
    return hermetic_dashboard_pr167_gates_bind_check(
        minimal_dashboard_pr167_gates_bind_environ(),
    ).ok


def dashboard_pr167_gates_bind_contract_summary(
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    env = environ if environ is not None else os.environ
    result = hermetic_dashboard_pr167_gates_bind_check(env)
    theme_map = _theme_hermetic_map(env)
    return {
        "gate_id": GATE_ID,
        "pr_number": PR_NUMBER,
        "pr168_theme_c_gate_id": GATE_ID,
        "bind_label": DASHBOARD_PR167_BIND_LABEL,
        "bind_version": DASHBOARD_PR167_BIND_VERSION,
        "prior_gate_ids": [DASHBOARD_SLOTS_GATE, PR167_GATE_ID],
        "detected_mode": detect_matrix_mode(env).value,
        "hermetic_operator_ok": result.ok,
        "bound_slots": bind_pr167_gates_to_slots(theme_map),
        "live_verified": False,
        "live_api_called": False,
        "four_state_max": "TEST_VERIFIED",
        "gate_closed_default": dashboard_pr167_gates_bind_gate_closed(),
        "verify_script": str(VERIFY_SCRIPT_REL),
        "status_html": str(HTML_REL),
        "contract_snippet": dashboard_pr167_bind_contract_snippet(),
        "hermetic_violation_codes": sorted({v.code for v in result.violations}),
    }
