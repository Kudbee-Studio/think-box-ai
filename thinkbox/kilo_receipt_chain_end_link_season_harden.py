"""Hermetic receipt-chain / END_LINK season harden gate (PR #165 theme C)."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from thinkbox.kilo_env_matrix import EnvMatrixMode, detect_matrix_mode
from thinkbox.kilo_governance_evidence_live_proof_readiness import (
    GATE_ID as PRIOR_GATE_ID,
)
from thinkbox.kilo_governance_evidence_live_proof_readiness import (
    hermetic_governance_evidence_live_proof_readiness_check,
    minimal_governance_evidence_live_proof_readiness_environ,
)
from thinkbox.kilo_live_proof_readiness import REPO_ROOT
from thinkbox.kilo_receipt_chain_end_link_era_close import (
    GATE_ID as ERA_CLOSE_GATE_ID,
)
from thinkbox.kilo_receipt_chain_end_link_era_close import (
    hermetic_receipt_chain_end_link_era_close_check,
)
from thinkbox.receipt_chain_end_link_season_harden import (
    SEASON_HARDEN_LABEL,
    SEASON_HARDEN_VERSION,
    receipt_chain_season_contract_snippet,
    validate_receipt_chain_season_document,
)

__all__ = (
    "CHECKLIST_REL",
    "FIXTURES_REL",
    "GATE_ID",
    "PR_NUMBER",
    "VERIFY_SCRIPT_REL",
    "ReceiptChainEndLinkSeasonHardenEvidence",
    "ReceiptChainEndLinkSeasonHardenResult",
    "ReceiptChainEndLinkSeasonHardenViolation",
    "evaluate_receipt_chain_end_link_season_harden",
    "hermetic_receipt_chain_end_link_season_harden_check",
    "minimal_receipt_chain_end_link_season_harden_environ",
    "receipt_chain_end_link_season_harden_contract_summary",
    "receipt_chain_end_link_season_harden_gate_closed",
    "run_season_harden_fixture_suite",
    "validate_checklist_document",
)

GATE_ID = "receipt-chain-end-link-season-harden"
PR_NUMBER = 165

VERIFY_SCRIPT_REL = Path("scripts/verify_kilo_receipt_chain_end_link_season_harden.py")
CHECKLIST_REL = Path("data/kilo_receipt_chain_end_link_season_harden/checklist.json")
FIXTURES_REL = Path("data/kilo_receipt_chain_end_link_season_harden/fixtures")


@dataclass(frozen=True)
class ReceiptChainEndLinkSeasonHardenViolation:
    code: str
    message: str
    path: str | None = None


@dataclass(frozen=True)
class ReceiptChainEndLinkSeasonHardenEvidence:
    gate_id: str
    pr_number: int
    era_close_ok: bool
    governance_readiness_ok: bool
    season_doc_ok: bool
    live_api_called: bool = False
    four_state_max: str = "TEST_VERIFIED"


@dataclass(frozen=True)
class ReceiptChainEndLinkSeasonHardenResult:
    mode: EnvMatrixMode
    ok: bool
    violations: list[ReceiptChainEndLinkSeasonHardenViolation]
    evidence: ReceiptChainEndLinkSeasonHardenEvidence | None = None


def minimal_receipt_chain_end_link_season_harden_environ(
    extra: Mapping[str, str] | None = None,
) -> dict[str, str]:
    base: MutableMapping[str, str] = dict(
        minimal_governance_evidence_live_proof_readiness_environ()
    )
    if extra:
        base.update(extra)
    return dict(base)


def validate_checklist_document(
    doc: Mapping[str, Any],
) -> list[ReceiptChainEndLinkSeasonHardenViolation]:
    violations: list[ReceiptChainEndLinkSeasonHardenViolation] = []
    if doc.get("gate_id") != GATE_ID:
        violations.append(
            ReceiptChainEndLinkSeasonHardenViolation(code="gate_id", message="gate_id")
        )
    if doc.get("live_verified") is True:
        violations.append(
            ReceiptChainEndLinkSeasonHardenViolation(code="live_verified", message="false")
        )
    if doc.get("season_harden_label") != SEASON_HARDEN_LABEL:
        violations.append(ReceiptChainEndLinkSeasonHardenViolation(code="label", message="label"))
    prior = doc.get("prior_gate_ids") or []
    for required in (ERA_CLOSE_GATE_ID, PRIOR_GATE_ID):
        if required not in prior:
            violations.append(
                ReceiptChainEndLinkSeasonHardenViolation(code="prior", message=required),
            )
    return violations


def run_season_harden_fixture_suite() -> tuple[int, int, list[str]]:
    errors: list[str] = []
    positive = negative = 0
    snippet = receipt_chain_season_contract_snippet()
    if snippet.get("live_verified") is False:
        positive += 1
    else:
        errors.append("snippet_honesty")
    fixtures_dir = REPO_ROOT / FIXTURES_REL
    if not fixtures_dir.is_dir():
        errors.append("fixtures_dir_missing")
        return positive, negative, errors
    for path in sorted(fixtures_dir.glob("*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        if doc.get("expect_ok"):
            v = validate_receipt_chain_season_document(doc)
            if v:
                errors.append(f"{path.name}: {v[0].code}")
            else:
                positive += 1
        if doc.get("expect_fail"):
            v = validate_receipt_chain_season_document(doc)
            if v:
                negative += 1
            else:
                errors.append(f"{path.name}: expected fail")
    return positive, negative, errors


def evaluate_receipt_chain_end_link_season_harden(
    mode: EnvMatrixMode | None = None,
    environ: Mapping[str, str] | None = None,
) -> ReceiptChainEndLinkSeasonHardenResult:
    env = environ if environ is not None else os.environ
    resolved = mode if mode is not None else detect_matrix_mode(env)
    violations: list[ReceiptChainEndLinkSeasonHardenViolation] = []

    era = hermetic_receipt_chain_end_link_era_close_check(env)
    if not era.ok:
        violations.append(
            ReceiptChainEndLinkSeasonHardenViolation(code="era_close", message=ERA_CLOSE_GATE_ID),
        )
    gov = hermetic_governance_evidence_live_proof_readiness_check(env)
    if not gov.ok:
        violations.append(
            ReceiptChainEndLinkSeasonHardenViolation(code="gov_readiness", message=PRIOR_GATE_ID),
        )

    checklist = REPO_ROOT / CHECKLIST_REL
    season_doc_ok = False
    if checklist.is_file():
        doc = json.loads(checklist.read_text(encoding="utf-8"))
        cv = validate_checklist_document(doc)
        violations.extend(cv)
        season_doc_ok = len(cv) == 0
    else:
        violations.append(
            ReceiptChainEndLinkSeasonHardenViolation(code="checklist", message="missing")
        )

    pos, neg, fixture_errors = run_season_harden_fixture_suite()
    for err in fixture_errors:
        violations.append(ReceiptChainEndLinkSeasonHardenViolation(code="fixture", message=err))

    ok = (
        era.ok
        and gov.ok
        and season_doc_ok
        and pos >= 1
        and neg >= 1
        and not fixture_errors
        and len(violations) == 0
    )
    evidence = ReceiptChainEndLinkSeasonHardenEvidence(
        gate_id=GATE_ID,
        pr_number=PR_NUMBER,
        era_close_ok=era.ok,
        governance_readiness_ok=gov.ok,
        season_doc_ok=season_doc_ok,
    )
    return ReceiptChainEndLinkSeasonHardenResult(
        mode=resolved,
        ok=ok,
        violations=violations if not ok else [],
        evidence=evidence,
    )


def hermetic_receipt_chain_end_link_season_harden_check(
    environ: Mapping[str, str] | None = None,
) -> ReceiptChainEndLinkSeasonHardenResult:
    env = environ if environ is not None else os.environ
    return evaluate_receipt_chain_end_link_season_harden(detect_matrix_mode(env), env)


def receipt_chain_end_link_season_harden_gate_closed() -> bool:
    return hermetic_receipt_chain_end_link_season_harden_check(
        minimal_receipt_chain_end_link_season_harden_environ(),
    ).ok


def receipt_chain_end_link_season_harden_contract_summary(
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    env = environ if environ is not None else os.environ
    result = hermetic_receipt_chain_end_link_season_harden_check(env)
    return {
        "gate_id": GATE_ID,
        "pr_number": PR_NUMBER,
        "pr165_theme_c_gate_id": GATE_ID,
        "season_harden_label": SEASON_HARDEN_LABEL,
        "season_harden_version": SEASON_HARDEN_VERSION,
        "prior_gate_ids": [ERA_CLOSE_GATE_ID, PRIOR_GATE_ID],
        "detected_mode": detect_matrix_mode(env).value,
        "hermetic_operator_ok": result.ok,
        "live_verified": False,
        "live_api_called": False,
        "four_state_max": "TEST_VERIFIED",
        "gate_closed_default": receipt_chain_end_link_season_harden_gate_closed(),
        "verify_script": str(VERIFY_SCRIPT_REL),
        "contract_snippet": receipt_chain_season_contract_snippet(),
        "hermetic_violation_codes": sorted({v.code for v in result.violations}),
    }
