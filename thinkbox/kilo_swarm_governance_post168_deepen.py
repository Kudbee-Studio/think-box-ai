"""Hermetic swarm / governance post-#168 deepen gate (PR #169 theme D)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, MutableMapping

from thinkbox.kilo_env_matrix import EnvMatrixMode, detect_matrix_mode
from thinkbox.kilo_hermetic_gate_memo import memoized_hermetic_check
from thinkbox.kilo_live_proof_readiness import REPO_ROOT
from thinkbox.kilo_swarm_governance_post167_deepen import (
    GATE_ID as POST167_SWARM_GATE,
    hermetic_swarm_governance_post167_deepen_check,
    minimal_swarm_governance_post167_deepen_environ,
)
from thinkbox.swarm_governance_post168_deepen import (
    SWARM_GOV_POST168_LABEL,
    SWARM_GOV_POST168_VERSION,
    admission_evidence_shape_ok,
    swarm_governance_post168_contract_snippet,
)

__all__ = (
    "CHECKLIST_REL",
    "GATE_ID",
    "PR_NUMBER",
    "VERIFY_SCRIPT_REL",
    "SwarmGovPost168Evidence",
    "SwarmGovPost168Result",
    "SwarmGovPost168Violation",
    "evaluate_swarm_governance_post168_deepen",
    "hermetic_swarm_governance_post168_deepen_check",
    "minimal_swarm_governance_post168_deepen_environ",
    "swarm_governance_post168_deepen_contract_summary",
    "swarm_governance_post168_deepen_gate_closed",
    "validate_checklist_document",
)

GATE_ID = "swarm-governance-post168-deepen"
PR_NUMBER = 169

VERIFY_SCRIPT_REL = Path("scripts/verify_kilo_swarm_governance_post168_deepen.py")
CHECKLIST_REL = Path("data/kilo_swarm_governance_post168_deepen/checklist.json")


@dataclass(frozen=True)
class SwarmGovPost168Violation:
    code: str
    message: str
    path: str | None = None


@dataclass(frozen=True)
class SwarmGovPost168Evidence:
    gate_id: str
    pr_number: int
    post167_swarm_ok: bool
    shape_ok: bool
    live_api_called: bool = False
    four_state_max: str = "TEST_VERIFIED"


@dataclass(frozen=True)
class SwarmGovPost168Result:
    mode: EnvMatrixMode
    ok: bool
    violations: list[SwarmGovPost168Violation]
    evidence: SwarmGovPost168Evidence | None = None


def minimal_swarm_governance_post168_deepen_environ(
    extra: Mapping[str, str] | None = None,
) -> dict[str, str]:
    base: MutableMapping[str, str] = dict(minimal_swarm_governance_post167_deepen_environ())
    if extra:
        base.update(extra)
    return dict(base)


def validate_checklist_document(doc: Mapping[str, Any]) -> list[SwarmGovPost168Violation]:
    violations: list[SwarmGovPost168Violation] = []
    if doc.get("gate_id") != GATE_ID:
        violations.append(SwarmGovPost168Violation(code="gate_id", message="gate_id"))
    if doc.get("live_verified") is True:
        violations.append(SwarmGovPost168Violation(code="live_verified", message="false"))
    prior = doc.get("prior_gate_ids") or []
    if POST167_SWARM_GATE not in prior:
        violations.append(SwarmGovPost168Violation(code="prior_missing", message=POST167_SWARM_GATE))
    return violations


def evaluate_swarm_governance_post168_deepen(
    mode: EnvMatrixMode | None = None,
    environ: Mapping[str, str] | None = None,
) -> SwarmGovPost168Result:
    env = environ if environ is not None else os.environ
    resolved = mode if mode is not None else detect_matrix_mode(env)
    violations: list[SwarmGovPost168Violation] = []

    post167 = hermetic_swarm_governance_post167_deepen_check(env)
    if not post167.ok:
        violations.append(SwarmGovPost168Violation(code="post167_swarm", message=POST167_SWARM_GATE))

    checklist = REPO_ROOT / CHECKLIST_REL
    if checklist.is_file():
        violations.extend(validate_checklist_document(json.loads(checklist.read_text())))
    else:
        violations.append(SwarmGovPost168Violation(code="checklist_missing", message=""))

    snippet = swarm_governance_post168_contract_snippet()
    shape_ok = admission_evidence_shape_ok(snippet)
    if not shape_ok:
        violations.append(SwarmGovPost168Violation(code="shape", message="contract_snippet"))

    ok = post167.ok and shape_ok and len(violations) == 0
    evidence = SwarmGovPost168Evidence(
        gate_id=GATE_ID,
        pr_number=PR_NUMBER,
        post167_swarm_ok=post167.ok,
        shape_ok=shape_ok,
    )
    return SwarmGovPost168Result(
        mode=resolved,
        ok=ok,
        violations=violations if not ok else [],
        evidence=evidence,
    )


def hermetic_swarm_governance_post168_deepen_check(
    environ: Mapping[str, str] | None = None,
) -> SwarmGovPost168Result:
    env = environ if environ is not None else os.environ
    return memoized_hermetic_check(
        GATE_ID,
        env,
        lambda: evaluate_swarm_governance_post168_deepen(detect_matrix_mode(env), env),
    )


def swarm_governance_post168_deepen_gate_closed() -> bool:
    return hermetic_swarm_governance_post168_deepen_check(
        minimal_swarm_governance_post168_deepen_environ(),
    ).ok


def swarm_governance_post168_deepen_contract_summary(
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    env = environ if environ is not None else os.environ
    result = hermetic_swarm_governance_post168_deepen_check(env)
    return {
        "gate_id": GATE_ID,
        "pr_number": PR_NUMBER,
        "pr169_theme_d_gate_id": GATE_ID,
        "swarm_gov_label": SWARM_GOV_POST168_LABEL,
        "swarm_gov_version": SWARM_GOV_POST168_VERSION,
        "prior_gate_ids": [POST167_SWARM_GATE],
        "detected_mode": detect_matrix_mode(env).value,
        "hermetic_operator_ok": result.ok,
        "live_verified": False,
        "live_api_called": False,
        "four_state_max": "TEST_VERIFIED",
        "gate_closed_default": result.ok,
        "verify_script": str(VERIFY_SCRIPT_REL),
        "contract_snippet": swarm_governance_post168_contract_snippet(),
        "hermetic_violation_codes": sorted({v.code for v in result.violations}),
    }
