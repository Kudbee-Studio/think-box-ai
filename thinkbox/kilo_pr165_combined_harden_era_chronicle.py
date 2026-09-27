"""Umbrella gate: PR #165 combined harden + #154–#164 era chronicle."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, MutableMapping

from thinkbox.kilo_control_plane_post164_deepen import (
    GATE_ID as THEME_B_GATE_ID,
    control_plane_post164_deepen_contract_summary,
    hermetic_control_plane_post164_deepen_check,
    minimal_control_plane_post164_deepen_environ,
)
from thinkbox.kilo_env_matrix import EnvMatrixMode, detect_matrix_mode
from thinkbox.kilo_governance_evidence_live_proof_readiness import GATE_ID as PRIOR_GATE_ID
from thinkbox.kilo_live_proof_readiness import REPO_ROOT
from thinkbox.kilo_live_smoke_audit_flip_harden import (
    GATE_ID as THEME_A_GATE_ID,
    hermetic_live_smoke_audit_flip_harden_check,
    live_smoke_audit_flip_harden_contract_summary,
)
from thinkbox.kilo_receipt_chain_end_link_season_harden import (
    GATE_ID as THEME_C_GATE_ID,
    hermetic_receipt_chain_end_link_season_harden_check,
    receipt_chain_end_link_season_harden_contract_summary,
)
from thinkbox.pr165_era_chronicle import (
    CHRONICLE_LABEL,
    CHRONICLE_VERSION,
    ERA_154_164_PACK_REL,
    chronicle_contract_snippet,
    load_era_154_164_chronicle_pack,
    validate_era_154_164_chronicle_pack,
)

__all__ = (
    "CHECKLIST_REL",
    "GATE_ID",
    "PR165_PASS_REL",
    "PR_NUMBER",
    "VERIFY_SCRIPT_REL",
    "Pr165CombinedEvidence",
    "Pr165CombinedResult",
    "Pr165CombinedViolation",
    "evaluate_pr165_combined_harden_era_chronicle",
    "hermetic_pr165_combined_harden_era_chronicle_check",
    "minimal_pr165_combined_environ",
    "pr165_combined_harden_era_chronicle_contract_summary",
    "pr165_combined_harden_era_chronicle_gate_closed",
    "validate_checklist_document",
)

GATE_ID = "pr165-combined-harden-era-chronicle"
PR_NUMBER = 165

VERIFY_SCRIPT_REL = Path("scripts/verify_kilo_pr165_combined_harden.py")
CHECKLIST_REL = Path("data/kilo_pr165_combined_harden/checklist.json")
PR165_PASS_REL = Path("docs/audit/passes/2026-09-23-pr165.json")


@dataclass(frozen=True)
class Pr165CombinedViolation:
    code: str
    message: str
    path: str | None = None


@dataclass(frozen=True)
class Pr165CombinedEvidence:
    gate_id: str
    pr_number: int
    theme_a_ok: bool
    theme_b_ok: bool
    theme_c_ok: bool
    chronicle_pack_ok: bool
    live_api_called: bool = False
    four_state_max: str = "TEST_VERIFIED"


@dataclass(frozen=True)
class Pr165CombinedResult:
    mode: EnvMatrixMode
    ok: bool
    violations: list[Pr165CombinedViolation]
    evidence: Pr165CombinedEvidence | None = None


def minimal_pr165_combined_environ(
    extra: Mapping[str, str] | None = None,
) -> dict[str, str]:
    base: MutableMapping[str, str] = dict(minimal_control_plane_post164_deepen_environ())
    if extra:
        base.update(extra)
    return dict(base)


def validate_checklist_document(doc: Mapping[str, Any]) -> list[Pr165CombinedViolation]:
    violations: list[Pr165CombinedViolation] = []
    if doc.get("gate_id") != GATE_ID:
        violations.append(Pr165CombinedViolation(code="gate_id", message="gate_id"))
    if doc.get("pr_number") != PR_NUMBER:
        violations.append(Pr165CombinedViolation(code="pr_number", message="pr_number"))
    if doc.get("live_verified") is True:
        violations.append(Pr165CombinedViolation(code="live_verified", message="false"))
    if doc.get("live_api_called") is True:
        violations.append(Pr165CombinedViolation(code="live_api", message="false"))
    if doc.get("chronicle_label") != CHRONICLE_LABEL:
        violations.append(Pr165CombinedViolation(code="chronicle_label", message="label"))
    prior = doc.get("prior_gate_ids") or []
    for required in (PRIOR_GATE_ID, THEME_A_GATE_ID, THEME_B_GATE_ID, THEME_C_GATE_ID):
        if required not in prior:
            violations.append(Pr165CombinedViolation(code="prior_missing", message=required))
    return violations


def evaluate_pr165_combined_harden_era_chronicle(
    mode: EnvMatrixMode | None = None,
    environ: Mapping[str, str] | None = None,
) -> Pr165CombinedResult:
    env = environ if environ is not None else os.environ
    resolved = mode if mode is not None else detect_matrix_mode(env)
    violations: list[Pr165CombinedViolation] = []

    theme_a = hermetic_live_smoke_audit_flip_harden_check(env)
    if not theme_a.ok:
        violations.append(Pr165CombinedViolation(code="theme_a", message=THEME_A_GATE_ID))
    theme_b = hermetic_control_plane_post164_deepen_check(env)
    if not theme_b.ok:
        violations.append(Pr165CombinedViolation(code="theme_b", message=THEME_B_GATE_ID))
    theme_c = hermetic_receipt_chain_end_link_season_harden_check(env)
    if not theme_c.ok:
        violations.append(Pr165CombinedViolation(code="theme_c", message=THEME_C_GATE_ID))

    checklist = REPO_ROOT / CHECKLIST_REL
    if checklist.is_file():
        violations.extend(validate_checklist_document(json.loads(checklist.read_text())))
    else:
        violations.append(Pr165CombinedViolation(code="checklist", message="missing"))

    chronicle_ok = False
    pack_path = REPO_ROOT / ERA_154_164_PACK_REL
    if pack_path.is_file():
        pack = load_era_154_164_chronicle_pack()
        cv = validate_era_154_164_chronicle_pack(pack)
        if cv:
            violations.append(Pr165CombinedViolation(code="chronicle_pack", message=cv[0].code))
        else:
            chronicle_ok = True
    else:
        violations.append(Pr165CombinedViolation(code="chronicle_pack_missing", message=str(ERA_154_164_PACK_REL)))

    audit = REPO_ROOT / PR165_PASS_REL
    if audit.is_file():
        body = json.loads(audit.read_text(encoding="utf-8"))
        if body.get("live_verified") is True or body.get("live_api_called") is True:
            violations.append(Pr165CombinedViolation(code="audit_honesty", message="audit pass"))
    else:
        violations.append(Pr165CombinedViolation(code="audit_pass_missing", message=str(PR165_PASS_REL)))

    ok = theme_a.ok and theme_b.ok and theme_c.ok and chronicle_ok and len(violations) == 0
    evidence = Pr165CombinedEvidence(
        gate_id=GATE_ID,
        pr_number=PR_NUMBER,
        theme_a_ok=theme_a.ok,
        theme_b_ok=theme_b.ok,
        theme_c_ok=theme_c.ok,
        chronicle_pack_ok=chronicle_ok,
    )
    return Pr165CombinedResult(
        mode=resolved,
        ok=ok,
        violations=violations if not ok else [],
        evidence=evidence,
    )


def hermetic_pr165_combined_harden_era_chronicle_check(
    environ: Mapping[str, str] | None = None,
) -> Pr165CombinedResult:
    env = environ if environ is not None else os.environ
    return evaluate_pr165_combined_harden_era_chronicle(detect_matrix_mode(env), env)


def pr165_combined_harden_era_chronicle_gate_closed() -> bool:
    return hermetic_pr165_combined_harden_era_chronicle_check(minimal_pr165_combined_environ()).ok


def pr165_combined_harden_era_chronicle_contract_summary(
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    env = environ if environ is not None else os.environ
    result = hermetic_pr165_combined_harden_era_chronicle_check(env)
    return {
        "gate_id": GATE_ID,
        "pr_number": PR_NUMBER,
        "pr165_gate_id": GATE_ID,
        "chronicle_label": CHRONICLE_LABEL,
        "chronicle_version": CHRONICLE_VERSION,
        "theme_a": live_smoke_audit_flip_harden_contract_summary(env),
        "theme_b": control_plane_post164_deepen_contract_summary(env),
        "theme_c": receipt_chain_end_link_season_harden_contract_summary(env),
        "detected_mode": detect_matrix_mode(env).value,
        "hermetic_operator_ok": result.ok,
        "live_verified": False,
        "live_api_called": False,
        "four_state_max": "TEST_VERIFIED",
        "live_proof_in_this_pr": False,
        "gate_closed_default": pr165_combined_harden_era_chronicle_gate_closed(),
        "verify_script": str(VERIFY_SCRIPT_REL),
        "era_chronicle_pack": str(ERA_154_164_PACK_REL),
        "audit_pass": str(PR165_PASS_REL),
        "contract_snippet": chronicle_contract_snippet(),
        "hermetic_violation_codes": sorted({v.code for v in result.violations}),
    }
