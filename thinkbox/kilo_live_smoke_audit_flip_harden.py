"""Hermetic live-smoke ↔ audit-flip harden gate (PR #165 theme A)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, MutableMapping

from thinkbox.kilo_env_matrix import EnvMatrixMode, detect_matrix_mode
from thinkbox.kilo_governance_evidence_live_proof_readiness import (
    GATE_ID as PRIOR_GATE_ID,
    hermetic_governance_evidence_live_proof_readiness_check,
    minimal_governance_evidence_live_proof_readiness_environ,
)
from thinkbox.kilo_live_proof_readiness import REPO_ROOT
from thinkbox.kilo_live_smoke_evidence import (
    GATE_ID as SMOKE_GATE_ID,
    audit_flip_candidate,
    hermetic_live_smoke_evidence_operator_check,
    minimal_valid_smoke_evidence_document,
)
from thinkbox.kilo_live_smoke_operator import (
    GATE_ID as OPERATOR_GATE_ID,
    hermetic_live_smoke_operator_check,
)
from thinkbox.live_smoke_audit_flip_correlation import (
    CORRELATION_LABEL,
    CORRELATION_VERSION,
    correlation_contract_snippet,
)

__all__ = (
    "CHECKLIST_REL",
    "FIXTURES_REL",
    "GATE_ID",
    "PR_NUMBER",
    "VERIFY_SCRIPT_REL",
    "LiveSmokeAuditFlipHardenEvidence",
    "LiveSmokeAuditFlipHardenResult",
    "LiveSmokeAuditFlipHardenViolation",
    "evaluate_live_smoke_audit_flip_harden",
    "hermetic_live_smoke_audit_flip_harden_check",
    "live_smoke_audit_flip_harden_contract_summary",
    "live_smoke_audit_flip_harden_gate_closed",
    "minimal_live_smoke_audit_flip_harden_environ",
    "run_audit_flip_harden_fixture_suite",
    "validate_checklist_document",
)

GATE_ID = "live-smoke-audit-flip-harden"
PR_NUMBER = 165

VERIFY_SCRIPT_REL = Path("scripts/verify_kilo_live_smoke_audit_flip_harden.py")
CHECKLIST_REL = Path("data/kilo_live_smoke_audit_flip_harden/checklist.json")
FIXTURES_REL = Path("data/kilo_live_smoke_audit_flip_harden/fixtures")


@dataclass(frozen=True)
class LiveSmokeAuditFlipHardenViolation:
    code: str
    message: str
    path: str | None = None


@dataclass(frozen=True)
class LiveSmokeAuditFlipHardenEvidence:
    gate_id: str
    pr_number: int
    governance_readiness_ok: bool
    smoke_evidence_ok: bool
    smoke_operator_ok: bool
    correlation_snippet_ok: bool
    live_api_called: bool = False
    four_state_max: str = "TEST_VERIFIED"


@dataclass(frozen=True)
class LiveSmokeAuditFlipHardenResult:
    mode: EnvMatrixMode
    ok: bool
    violations: list[LiveSmokeAuditFlipHardenViolation]
    evidence: LiveSmokeAuditFlipHardenEvidence | None = None


def minimal_live_smoke_audit_flip_harden_environ(
    extra: Mapping[str, str] | None = None,
) -> dict[str, str]:
    base: MutableMapping[str, str] = dict(minimal_governance_evidence_live_proof_readiness_environ())
    if extra:
        base.update(extra)
    return dict(base)


def validate_checklist_document(doc: Mapping[str, Any]) -> list[LiveSmokeAuditFlipHardenViolation]:
    violations: list[LiveSmokeAuditFlipHardenViolation] = []
    if doc.get("gate_id") != GATE_ID:
        violations.append(LiveSmokeAuditFlipHardenViolation(code="gate_id", message="gate_id"))
    if doc.get("pr_number") != PR_NUMBER:
        violations.append(LiveSmokeAuditFlipHardenViolation(code="pr_number", message="pr_number"))
    if doc.get("live_verified") is True:
        violations.append(LiveSmokeAuditFlipHardenViolation(code="live_verified", message="false"))
    if doc.get("live_api_called") is True:
        violations.append(LiveSmokeAuditFlipHardenViolation(code="live_api", message="false"))
    if doc.get("correlation_label") != CORRELATION_LABEL:
        violations.append(LiveSmokeAuditFlipHardenViolation(code="correlation_label", message="label"))
    prior = doc.get("prior_gate_ids") or []
    for required in (PRIOR_GATE_ID, SMOKE_GATE_ID, OPERATOR_GATE_ID):
        if required not in prior:
            violations.append(
                LiveSmokeAuditFlipHardenViolation(code="prior_missing", message=required),
            )
    return violations


def run_audit_flip_harden_fixture_suite() -> tuple[int, int, list[str]]:
    errors: list[str] = []
    positive = negative = 0
    snippet = correlation_contract_snippet()
    if snippet.get("live_verified") is False:
        positive += 1
    else:
        errors.append("correlation_snippet_honesty")
    minimal = minimal_valid_smoke_evidence_document()
    flip = audit_flip_candidate(minimal, {"pr_number": 152, "gate_id": SMOKE_GATE_ID})
    if flip.get("audit_flip_status") == "refused" and flip.get("smoke_audit_correlation"):
        positive += 1
    else:
        errors.append("hermetic_flip_refused_with_correlation")
    fixtures_dir = REPO_ROOT / FIXTURES_REL
    if fixtures_dir.is_dir():
        for path in sorted(fixtures_dir.glob("*.json")):
            doc = json.loads(path.read_text(encoding="utf-8"))
            if doc.get("expect_refused_flip"):
                if doc.get("audit_flip_status") != "refused":
                    errors.append(f"{path.name}: expected refused flip")
                else:
                    negative += 1
    return positive, negative, errors


def evaluate_live_smoke_audit_flip_harden(
    mode: EnvMatrixMode | None = None,
    environ: Mapping[str, str] | None = None,
) -> LiveSmokeAuditFlipHardenResult:
    env = environ if environ is not None else os.environ
    resolved = mode if mode is not None else detect_matrix_mode(env)
    violations: list[LiveSmokeAuditFlipHardenViolation] = []

    gov = hermetic_governance_evidence_live_proof_readiness_check(env)
    if not gov.ok:
        violations.append(
            LiveSmokeAuditFlipHardenViolation(code="prior_gov_readiness", message=PRIOR_GATE_ID),
        )
    smoke = hermetic_live_smoke_evidence_operator_check(env)
    if not smoke.ok:
        violations.append(
            LiveSmokeAuditFlipHardenViolation(code="smoke_evidence", message=SMOKE_GATE_ID),
        )
    op = hermetic_live_smoke_operator_check(env)
    if not op.ok:
        violations.append(
            LiveSmokeAuditFlipHardenViolation(code="smoke_operator", message=OPERATOR_GATE_ID),
        )

    checklist = REPO_ROOT / CHECKLIST_REL
    if checklist.is_file():
        violations.extend(validate_checklist_document(json.loads(checklist.read_text())))
    else:
        violations.append(LiveSmokeAuditFlipHardenViolation(code="checklist_missing", message=""))

    pos, neg, fixture_errors = run_audit_flip_harden_fixture_suite()
    for err in fixture_errors:
        violations.append(LiveSmokeAuditFlipHardenViolation(code="fixture", message=err))

    snippet_ok = correlation_contract_snippet().get("live_verified") is False
    ok = gov.ok and smoke.ok and op.ok and snippet_ok and not fixture_errors and pos >= 2 and len(violations) == 0
    evidence = LiveSmokeAuditFlipHardenEvidence(
        gate_id=GATE_ID,
        pr_number=PR_NUMBER,
        governance_readiness_ok=gov.ok,
        smoke_evidence_ok=smoke.ok,
        smoke_operator_ok=op.ok,
        correlation_snippet_ok=snippet_ok,
    )
    return LiveSmokeAuditFlipHardenResult(
        mode=resolved,
        ok=ok,
        violations=violations if not ok else [],
        evidence=evidence,
    )


def hermetic_live_smoke_audit_flip_harden_check(
    environ: Mapping[str, str] | None = None,
) -> LiveSmokeAuditFlipHardenResult:
    env = environ if environ is not None else os.environ
    return evaluate_live_smoke_audit_flip_harden(detect_matrix_mode(env), env)


def live_smoke_audit_flip_harden_gate_closed() -> bool:
    return hermetic_live_smoke_audit_flip_harden_check(
        minimal_live_smoke_audit_flip_harden_environ(),
    ).ok


def live_smoke_audit_flip_harden_contract_summary(
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    env = environ if environ is not None else os.environ
    result = hermetic_live_smoke_audit_flip_harden_check(env)
    return {
        "gate_id": GATE_ID,
        "pr_number": PR_NUMBER,
        "pr165_theme_a_gate_id": GATE_ID,
        "correlation_label": CORRELATION_LABEL,
        "correlation_version": CORRELATION_VERSION,
        "prior_gate_ids": [PRIOR_GATE_ID, SMOKE_GATE_ID, OPERATOR_GATE_ID],
        "detected_mode": detect_matrix_mode(env).value,
        "hermetic_operator_ok": result.ok,
        "live_verified": False,
        "live_api_called": False,
        "four_state_max": "TEST_VERIFIED",
        "gate_closed_default": live_smoke_audit_flip_harden_gate_closed(),
        "verify_script": str(VERIFY_SCRIPT_REL),
        "verify_script_present": (REPO_ROOT / VERIFY_SCRIPT_REL).is_file(),
        "contract_snippet": correlation_contract_snippet(),
        "hermetic_violation_codes": sorted({v.code for v in result.violations}),
    }
