"""Hermetic receipt-chain / END_LINK era audit close gate (PR #162).

Layers on PR #161 ``end-link-api-ops-harden``. Validates consolidated era pack
#154–#161 and spine honesty — no live HTTP.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, MutableMapping

from thinkbox.kilo_end_link_api_ops_harden import (
    GATE_ID as PRIOR_GATE_ID,
    hermetic_end_link_api_ops_harden_check,
    minimal_end_link_api_ops_harden_environ,
)
from thinkbox.kilo_env_matrix import EnvMatrixMode, detect_matrix_mode
from thinkbox.kilo_live_proof_readiness import REPO_ROOT
from thinkbox.receipt_chain_end_link_era_close import (
    ERA_CLOSE_LABEL,
    ERA_CLOSE_VERSION,
    ERA_CONSOLIDATED_154_161_REL,
    ERA_GATE_SPECS,
    era_close_contract_snippet,
    load_era_consolidated_pack,
    validate_era_consolidated_154_161_pack,
)

__all__ = (
    "CHECKLIST_REL",
    "FIXTURES_REL",
    "GATE_ID",
    "PR_NUMBER",
    "VERIFY_SCRIPT_REL",
    "ReceiptChainEndLinkEraCloseEvidence",
    "ReceiptChainEndLinkEraCloseResult",
    "ReceiptChainEndLinkEraCloseViolation",
    "evaluate_receipt_chain_end_link_era_close",
    "hermetic_receipt_chain_end_link_era_close_check",
    "minimal_receipt_chain_end_link_era_close_environ",
    "receipt_chain_end_link_era_close_contract_summary",
    "receipt_chain_end_link_era_close_gate_closed",
    "run_era_close_fixture_suite",
    "validate_checklist_document",
)

GATE_ID = "receipt-chain-end-link-era-close"
PR_NUMBER = 162

VERIFY_SCRIPT_REL = Path("scripts/verify_kilo_receipt_chain_end_link_era_close.py")
CHECKLIST_REL = Path("data/kilo_receipt_chain_end_link_era_close/checklist.json")
FIXTURES_REL = Path("data/kilo_receipt_chain_end_link_era_close/fixtures")
PR162_PASS_REL = Path("docs/audit/passes/2026-09-23-pr162.json")
OPERATOR_GUIDE_REL = Path("docs/guides/kilo_receipt_chain_end_link_operator.md")
AUDIT_INDEX_REL = Path("docs/audit/AUDIT_INDEX.json")

_REQUIRED_MARKERS: tuple[str, ...] = (
    ERA_CLOSE_LABEL,
    "pr154-pr161-era-consolidated",
    "live_verified: false",
    "live_api_called: false",
    "four_state_max",
    "TEST_VERIFIED",
    "Era audit close",
)

_REQUIRED_MODULES: tuple[Path, ...] = (
    Path("thinkbox/receipt_chain_end_link_era_close.py"),
    Path("thinkbox/kilo_receipt_chain_end_link_era_close.py"),
    Path("docs/audit/passes/2026-09-23-pr154-161-era-consolidated.json"),
    Path("tests/unit/test_receipt_chain_end_link_era_close.py"),
    Path("tests/unit/test_kilo_live_proof_readiness_pr162.py"),
)


@dataclass(frozen=True)
class ReceiptChainEndLinkEraCloseViolation:
    code: str
    message: str
    path: str | None = None


@dataclass(frozen=True)
class ReceiptChainEndLinkEraCloseEvidence:
    gate_id: str
    pr_number: int
    end_link_api_ops_harden_ok: bool
    era_pack_ok: bool
    audit_index_ok: bool
    live_api_called: bool = False
    four_state_max: str = "TEST_VERIFIED"


@dataclass(frozen=True)
class ReceiptChainEndLinkEraCloseResult:
    mode: EnvMatrixMode
    ok: bool
    end_link_api_ops_harden_ok: bool
    violations: list[ReceiptChainEndLinkEraCloseViolation]
    evidence: ReceiptChainEndLinkEraCloseEvidence | None = None


def minimal_receipt_chain_end_link_era_close_environ(
    extra: Mapping[str, str] | None = None,
) -> dict[str, str]:
    base: MutableMapping[str, str] = dict(minimal_end_link_api_ops_harden_environ())
    if extra:
        base.update(extra)
    return dict(base)


def validate_checklist_document(doc: Mapping[str, Any]) -> list[ReceiptChainEndLinkEraCloseViolation]:
    violations: list[ReceiptChainEndLinkEraCloseViolation] = []
    if doc.get("gate_id") != GATE_ID:
        violations.append(ReceiptChainEndLinkEraCloseViolation(code="gate_id_mismatch", message="gate_id"))
    if doc.get("pr_number") != PR_NUMBER:
        violations.append(ReceiptChainEndLinkEraCloseViolation(code="pr_number_mismatch", message="pr_number"))
    if doc.get("live_verified") is True:
        violations.append(ReceiptChainEndLinkEraCloseViolation(code="live_verified_true", message="must stay false"))
    if doc.get("live_api_called") is True:
        violations.append(ReceiptChainEndLinkEraCloseViolation(code="live_api_called_true", message="must stay false"))
    if doc.get("four_state_max") != "TEST_VERIFIED":
        violations.append(ReceiptChainEndLinkEraCloseViolation(code="four_state", message="four_state_max"))
    if doc.get("receipt_chain_end_link_era_close_version") != ERA_CLOSE_VERSION:
        violations.append(ReceiptChainEndLinkEraCloseViolation(code="version_mismatch", message="version"))
    prior = doc.get("prior_gate_ids") or []
    if PRIOR_GATE_ID not in prior:
        violations.append(
            ReceiptChainEndLinkEraCloseViolation(code="prior_gate_missing", message=f"must list {PRIOR_GATE_ID}"),
        )
    return violations


def _check_files() -> list[ReceiptChainEndLinkEraCloseViolation]:
    violations: list[ReceiptChainEndLinkEraCloseViolation] = []
    for rel in _REQUIRED_MODULES:
        if not (REPO_ROOT / rel).is_file():
            violations.append(
                ReceiptChainEndLinkEraCloseViolation(code="module_missing", message=f"missing {rel}", path=str(rel)),
            )
    if not (REPO_ROOT / VERIFY_SCRIPT_REL).is_file():
        violations.append(
            ReceiptChainEndLinkEraCloseViolation(code="verify_script_missing", message=str(VERIFY_SCRIPT_REL)),
        )
    checklist = REPO_ROOT / CHECKLIST_REL
    if checklist.is_file():
        try:
            violations.extend(validate_checklist_document(json.loads(checklist.read_text(encoding="utf-8"))))
        except json.JSONDecodeError:
            violations.append(ReceiptChainEndLinkEraCloseViolation(code="checklist_json", message="invalid JSON"))
    else:
        violations.append(ReceiptChainEndLinkEraCloseViolation(code="checklist_missing", message=str(CHECKLIST_REL)))
    if not (REPO_ROOT / PR162_PASS_REL).is_file():
        violations.append(
            ReceiptChainEndLinkEraCloseViolation(code="pr162_pass_missing", message="pr162 audit pass"),
        )
    return violations


def _check_markers() -> list[ReceiptChainEndLinkEraCloseViolation]:
    violations: list[ReceiptChainEndLinkEraCloseViolation] = []
    guide = (REPO_ROOT / OPERATOR_GUIDE_REL).read_text(encoding="utf-8")
    for marker in _REQUIRED_MARKERS:
        if marker not in guide:
            violations.append(
                ReceiptChainEndLinkEraCloseViolation(
                    code="guide_marker_missing",
                    message=f"operator guide missing: {marker}",
                    path=str(OPERATOR_GUIDE_REL),
                ),
            )
    return violations


def _check_audit_index() -> list[ReceiptChainEndLinkEraCloseViolation]:
    violations: list[ReceiptChainEndLinkEraCloseViolation] = []
    index_path = REPO_ROOT / AUDIT_INDEX_REL
    if not index_path.is_file():
        violations.append(ReceiptChainEndLinkEraCloseViolation(code="audit_index_missing", message="AUDIT_INDEX"))
        return violations
    passes = json.loads(index_path.read_text(encoding="utf-8")).get("passes") or []
    for suffix in ("pr161.json", "pr154-161-era-consolidated.json", "pr162.json"):
        if not any(str(p).endswith(suffix) for p in passes):
            violations.append(
                ReceiptChainEndLinkEraCloseViolation(
                    code="audit_index_gap",
                    message=f"missing *{suffix}",
                    path=str(AUDIT_INDEX_REL),
                ),
            )
    return violations


def run_era_close_fixture_suite() -> tuple[int, int, list[str]]:
    errors: list[str] = []
    positive = 0
    negative = 0

    pack = load_era_consolidated_pack()
    pack_violations = validate_era_consolidated_154_161_pack(pack)
    if not pack_violations:
        positive += 1
    else:
        errors.extend(v.message for v in pack_violations)

    snippet = era_close_contract_snippet()
    if snippet.get("era_gate_count") == len(ERA_GATE_SPECS):
        positive += 1
    else:
        errors.append("era_gate_count snippet")

    if pack.get("audit_pack") == "pr154-pr161-era-consolidated":
        positive += 1
    else:
        errors.append("audit_pack id")

    fixtures_dir = REPO_ROOT / FIXTURES_REL
    if fixtures_dir.is_dir():
        for path in sorted(fixtures_dir.glob("*.json")):
            doc = json.loads(path.read_text(encoding="utf-8"))
            if doc.get("expect_ok"):
                positive += 1
            if doc.get("expect_fail"):
                negative += 1

    return positive, negative, errors


def evaluate_receipt_chain_end_link_era_close(
    mode: EnvMatrixMode | None = None,
    environ: Mapping[str, str] | None = None,
) -> ReceiptChainEndLinkEraCloseResult:
    env: Mapping[str, str] = environ if environ is not None else os.environ
    resolved = mode if mode is not None else detect_matrix_mode(env)
    violations: list[ReceiptChainEndLinkEraCloseViolation] = []

    prior = hermetic_end_link_api_ops_harden_check(env)
    if not prior.ok:
        violations.append(
            ReceiptChainEndLinkEraCloseViolation(
                code="prior_api_ops_harden_failed",
                message=f"prior gate {PRIOR_GATE_ID} must pass",
            ),
        )

    violations.extend(_check_files())
    violations.extend(_check_markers())
    index_violations = _check_audit_index()
    violations.extend(index_violations)

    pos, _neg, fixture_errors = run_era_close_fixture_suite()
    for err in fixture_errors:
        violations.append(ReceiptChainEndLinkEraCloseViolation(code="fixture_failed", message=err))

    fixture_ok = not fixture_errors and pos >= 3
    if not fixture_ok:
        violations.append(ReceiptChainEndLinkEraCloseViolation(code="fixture_suite_weak", message="era fixtures weak"))

    era_pack_ok = not validate_era_consolidated_154_161_pack(load_era_consolidated_pack())
    audit_index_ok = not index_violations
    ok = prior.ok and fixture_ok and not violations

    evidence = ReceiptChainEndLinkEraCloseEvidence(
        gate_id=GATE_ID,
        pr_number=PR_NUMBER,
        end_link_api_ops_harden_ok=prior.ok,
        era_pack_ok=era_pack_ok,
        audit_index_ok=audit_index_ok,
    )
    return ReceiptChainEndLinkEraCloseResult(
        mode=resolved,
        ok=ok,
        end_link_api_ops_harden_ok=prior.ok,
        violations=violations if not ok else [],
        evidence=evidence,
    )


def hermetic_receipt_chain_end_link_era_close_check(
    environ: Mapping[str, str] | None = None,
) -> ReceiptChainEndLinkEraCloseResult:
    env: Mapping[str, str] = environ if environ is not None else os.environ
    return evaluate_receipt_chain_end_link_era_close(detect_matrix_mode(env), env)


def receipt_chain_end_link_era_close_gate_closed() -> bool:
    return hermetic_receipt_chain_end_link_era_close_check(
        minimal_receipt_chain_end_link_era_close_environ(),
    ).ok


def receipt_chain_end_link_era_close_contract_summary(
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    env: Mapping[str, str] = environ if environ is not None else os.environ
    result = hermetic_receipt_chain_end_link_era_close_check(env)
    return {
        "gate_id": GATE_ID,
        "pr_number": PR_NUMBER,
        "pr162_gate_id": GATE_ID,
        "pr161_layer_gate_id": PRIOR_GATE_ID,
        "receipt_chain_end_link_era_close": ERA_CLOSE_LABEL,
        "receipt_chain_end_link_era_close_version": ERA_CLOSE_VERSION,
        "detected_mode": detect_matrix_mode(env).value,
        "hermetic_operator_ok": result.ok,
        "end_link_api_ops_harden_ok": result.end_link_api_ops_harden_ok,
        "era_consolidated_rel": str(ERA_CONSOLIDATED_154_161_REL),
        "era_gate_count": len(ERA_GATE_SPECS),
        "live_api_called": False,
        "live_verified": False,
        "four_state_max": "TEST_VERIFIED",
        "live_proof_in_this_pr": False,
        "gate_closed_default": receipt_chain_end_link_era_close_gate_closed(),
        "verify_script": str(VERIFY_SCRIPT_REL),
        "verify_script_present": (REPO_ROOT / VERIFY_SCRIPT_REL).is_file(),
        "checklist_rel": str(CHECKLIST_REL),
        "hermetic_violation_codes": sorted({v.code for v in result.violations}),
    }
