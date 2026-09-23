"""Hermetic dashboard PR #168 gates bind gate (PR #169 theme C)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, MutableMapping

from thinkbox.dashboard_pr168_gates_bind import (
    DASHBOARD_PR168_BIND_LABEL,
    DASHBOARD_PR168_BIND_VERSION,
    PR168_THEME_GATE_IDS,
    bind_pr168_gates_to_slots,
    dashboard_pr168_bind_contract_snippet,
)
from thinkbox.kilo_api_ops_harden_post167 import hermetic_api_ops_harden_post167_check
from thinkbox.kilo_dashboard_pr167_gates_bind import (
    GATE_ID as POST167_DASHBOARD_BIND_GATE,
    hermetic_dashboard_pr167_gates_bind_check,
    minimal_dashboard_pr167_gates_bind_environ,
)
from thinkbox.kilo_dashboard_slots import (
    GATE_ID as DASHBOARD_SLOTS_GATE,
    hermetic_dashboard_slots_operator_check,
)
from thinkbox.kilo_env_matrix import EnvMatrixMode, detect_matrix_mode
from thinkbox.kilo_hermetic_gate_memo import memoized_hermetic_check
from thinkbox.kilo_live_proof_operator_audit_flip_post167 import (
    hermetic_live_proof_operator_audit_flip_post167_check,
)
from thinkbox.kilo_live_proof_readiness import REPO_ROOT
from thinkbox.kilo_swarm_governance_post167_deepen import (
    hermetic_swarm_governance_post167_deepen_check,
)

__all__ = (
    "CHECKLIST_REL",
    "GATE_ID",
    "HTML_REL",
    "PR_NUMBER",
    "VERIFY_SCRIPT_REL",
    "DashboardPr168BindEvidence",
    "DashboardPr168BindResult",
    "DashboardPr168BindViolation",
    "dashboard_pr168_gates_bind_contract_summary",
    "dashboard_pr168_gates_bind_gate_closed",
    "evaluate_dashboard_pr168_gates_bind",
    "hermetic_dashboard_pr168_gates_bind_check",
    "minimal_dashboard_pr168_gates_bind_environ",
    "validate_checklist_document",
)

GATE_ID = "dashboard-pr168-gates-bind"
PR_NUMBER = 169

VERIFY_SCRIPT_REL = Path("scripts/verify_kilo_dashboard_pr168_gates_bind.py")
CHECKLIST_REL = Path("data/kilo_dashboard_pr168_gates_bind/checklist.json")
HTML_REL = Path("public/control-plane/pr168_gates_status.html")


@dataclass(frozen=True)
class DashboardPr168BindViolation:
    code: str
    message: str
    path: str | None = None


@dataclass(frozen=True)
class DashboardPr168BindEvidence:
    gate_id: str
    pr_number: int
    dashboard_slots_ok: bool
    post167_dashboard_bind_ok: bool
    bound_slot_count: int
    bound_slots: tuple[dict[str, Any], ...] = ()
    live_api_called: bool = False
    four_state_max: str = "TEST_VERIFIED"


@dataclass(frozen=True)
class DashboardPr168BindResult:
    mode: EnvMatrixMode
    ok: bool
    violations: list[DashboardPr168BindViolation]
    evidence: DashboardPr168BindEvidence | None = None


def minimal_dashboard_pr168_gates_bind_environ(
    extra: Mapping[str, str] | None = None,
) -> dict[str, str]:
    base: MutableMapping[str, str] = dict(minimal_dashboard_pr167_gates_bind_environ())
    if extra:
        base.update(extra)
    return dict(base)


def validate_checklist_document(doc: Mapping[str, Any]) -> list[DashboardPr168BindViolation]:
    violations: list[DashboardPr168BindViolation] = []
    if doc.get("gate_id") != GATE_ID:
        violations.append(DashboardPr168BindViolation(code="gate_id", message="gate_id"))
    if doc.get("live_verified") is True:
        violations.append(DashboardPr168BindViolation(code="live_verified", message="false"))
    prior = doc.get("prior_gate_ids") or []
    if POST167_DASHBOARD_BIND_GATE not in prior:
        violations.append(
            DashboardPr168BindViolation(code="prior_missing", message=POST167_DASHBOARD_BIND_GATE),
        )
    if DASHBOARD_SLOTS_GATE not in prior:
        violations.append(DashboardPr168BindViolation(code="prior_missing", message=DASHBOARD_SLOTS_GATE))
    return violations


def _theme_hermetic_map(env: Mapping[str, str]) -> dict[str, bool]:
    return {
        PR168_THEME_GATE_IDS[0]: hermetic_live_proof_operator_audit_flip_post167_check(env).ok,
        PR168_THEME_GATE_IDS[1]: hermetic_api_ops_harden_post167_check(env).ok,
        PR168_THEME_GATE_IDS[2]: hermetic_dashboard_pr167_gates_bind_check(env).ok,
        PR168_THEME_GATE_IDS[3]: hermetic_swarm_governance_post167_deepen_check(env).ok,
    }


def evaluate_dashboard_pr168_gates_bind(
    mode: EnvMatrixMode | None = None,
    environ: Mapping[str, str] | None = None,
) -> DashboardPr168BindResult:
    env = environ if environ is not None else os.environ
    resolved = mode if mode is not None else detect_matrix_mode(env)
    violations: list[DashboardPr168BindViolation] = []

    slots = hermetic_dashboard_slots_operator_check(env)
    if not slots.ok:
        violations.append(DashboardPr168BindViolation(code="dashboard_slots", message=DASHBOARD_SLOTS_GATE))
    post167_bind = hermetic_dashboard_pr167_gates_bind_check(env)
    if not post167_bind.ok:
        violations.append(
            DashboardPr168BindViolation(code="post167_dashboard_bind", message=POST167_DASHBOARD_BIND_GATE),
        )

    checklist = REPO_ROOT / CHECKLIST_REL
    if checklist.is_file():
        violations.extend(validate_checklist_document(json.loads(checklist.read_text())))
    else:
        violations.append(DashboardPr168BindViolation(code="checklist_missing", message=""))

    html = REPO_ROOT / HTML_REL
    if not html.is_file():
        violations.append(DashboardPr168BindViolation(code="html_missing", message=str(HTML_REL)))
    elif DASHBOARD_PR168_BIND_LABEL not in html.read_text(encoding="utf-8"):
        violations.append(DashboardPr168BindViolation(code="html_marker", message="label"))

    theme_map = _theme_hermetic_map(env)
    bound = bind_pr168_gates_to_slots(theme_map)
    if len(bound) != len(PR168_THEME_GATE_IDS):
        violations.append(DashboardPr168BindViolation(code="bind_count", message="count"))
    for row in bound:
        if row.get("live_verified") is True:
            violations.append(DashboardPr168BindViolation(code="slot_live_claim", message="forbidden"))

    ok = slots.ok and post167_bind.ok and len(violations) == 0
    evidence = DashboardPr168BindEvidence(
        gate_id=GATE_ID,
        pr_number=PR_NUMBER,
        dashboard_slots_ok=slots.ok,
        post167_dashboard_bind_ok=post167_bind.ok,
        bound_slot_count=len(bound),
        bound_slots=tuple(bound),
    )
    return DashboardPr168BindResult(
        mode=resolved,
        ok=ok,
        violations=violations if not ok else [],
        evidence=evidence,
    )


def hermetic_dashboard_pr168_gates_bind_check(
    environ: Mapping[str, str] | None = None,
) -> DashboardPr168BindResult:
    env = environ if environ is not None else os.environ
    return memoized_hermetic_check(
        GATE_ID,
        env,
        lambda: evaluate_dashboard_pr168_gates_bind(detect_matrix_mode(env), env),
    )


def dashboard_pr168_gates_bind_gate_closed() -> bool:
    return hermetic_dashboard_pr168_gates_bind_check(
        minimal_dashboard_pr168_gates_bind_environ(),
    ).ok


def dashboard_pr168_gates_bind_contract_summary(
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    env = environ if environ is not None else os.environ
    result = hermetic_dashboard_pr168_gates_bind_check(env)
    bound = list(result.evidence.bound_slots) if result.evidence else []
    return {
        "gate_id": GATE_ID,
        "pr_number": PR_NUMBER,
        "pr169_theme_c_gate_id": GATE_ID,
        "bind_label": DASHBOARD_PR168_BIND_LABEL,
        "bind_version": DASHBOARD_PR168_BIND_VERSION,
        "prior_gate_ids": [DASHBOARD_SLOTS_GATE, POST167_DASHBOARD_BIND_GATE],
        "detected_mode": detect_matrix_mode(env).value,
        "hermetic_operator_ok": result.ok,
        "bound_slots": bound,
        "live_verified": False,
        "live_api_called": False,
        "four_state_max": "TEST_VERIFIED",
        "gate_closed_default": result.ok,
        "verify_script": str(VERIFY_SCRIPT_REL),
        "status_html": str(HTML_REL),
        "contract_snippet": dashboard_pr168_bind_contract_snippet(),
        "hermetic_violation_codes": sorted({v.code for v in result.violations}),
    }
