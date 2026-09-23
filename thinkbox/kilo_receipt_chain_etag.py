"""Hermetic receipt-chain + ETag deepen gate (PR #155, ``receipt-chain-etag``).

Layers on PR #154 ``control-plane-api``. Default: no network; ``live_api_called=False``.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, MutableMapping

from thinkbox.kilo_control_plane_api import (
    GATE_ID as PRIOR_GATE_ID,
    hermetic_control_plane_api_operator_check,
    minimal_control_plane_api_environ,
)
from thinkbox.kilo_env_matrix import EnvMatrixMode, detect_matrix_mode
from thinkbox.kilo_live_proof_readiness import REPO_ROOT

__all__ = (
    "CHECKLIST_REL",
    "FIXTURES_REL",
    "GATE_ID",
    "PR_NUMBER",
    "VERIFY_SCRIPT_REL",
    "ReceiptChainEtagEvidence",
    "ReceiptChainEtagResult",
    "ReceiptChainEtagViolation",
    "evaluate_receipt_chain_etag",
    "hermetic_receipt_chain_etag_check",
    "minimal_receipt_chain_etag_environ",
    "receipt_chain_etag_contract_summary",
    "receipt_chain_etag_gate_closed",
    "run_chain_fixture_suite",
    "validate_checklist_document",
)

GATE_ID = "receipt-chain-etag"
PR_NUMBER = 155

VERIFY_SCRIPT_REL = Path("scripts/verify_kilo_receipt_chain_etag.py")
CHECKLIST_REL = Path("data/kilo_receipt_chain_etag/checklist.json")
FIXTURES_REL = Path("data/kilo_receipt_chain_etag/fixtures")

_REQUIRED_MARKERS: tuple[str, ...] = (
    "receipt_chain_query",
    "control_plane_conditional",
    "get_chain_payload",
    "/receipts/chain/page",
    "conditional_json_response_if_match",
    "if-none-match",
)

_REQUIRED_MODULES: tuple[Path, ...] = (
    Path("thinkbox/receipt_chain_query.py"),
    Path("thinkbox/control_plane_conditional.py"),
    Path("thinkbox/control_plane_receipt_store.py"),
    Path("backend/api/v1/control_plane.py"),
)


@dataclass(frozen=True)
class ReceiptChainEtagViolation:
    code: str
    message: str
    path: str | None = None


@dataclass(frozen=True)
class ReceiptChainEtagEvidence:
    gate_id: str
    pr_number: int
    control_plane_api_ok: bool
    route_markers_ok: bool
    fixture_suite_ok: bool
    live_api_called: bool = False
    four_state_max: str = "TEST_VERIFIED"


@dataclass(frozen=True)
class ReceiptChainEtagResult:
    mode: EnvMatrixMode
    ok: bool
    control_plane_api_ok: bool
    violations: list[ReceiptChainEtagViolation]
    evidence: ReceiptChainEtagEvidence | None = None


def minimal_receipt_chain_etag_environ(
    extra: Mapping[str, str] | None = None,
) -> dict[str, str]:
    base: MutableMapping[str, str] = dict(minimal_control_plane_api_environ())
    if extra:
        base.update(extra)
    return dict(base)


def validate_checklist_document(doc: Mapping[str, Any]) -> list[ReceiptChainEtagViolation]:
    violations: list[ReceiptChainEtagViolation] = []
    if doc.get("gate_id") != GATE_ID:
        violations.append(
            ReceiptChainEtagViolation(code="gate_id_mismatch", message="checklist gate_id")
        )
    if doc.get("pr_number") != PR_NUMBER:
        violations.append(
            ReceiptChainEtagViolation(code="pr_number_mismatch", message="checklist pr_number")
        )
    if doc.get("live_verified") is True:
        violations.append(
            ReceiptChainEtagViolation(code="live_verified_true", message="must stay false")
        )
    if doc.get("four_state_max") != "TEST_VERIFIED":
        violations.append(
            ReceiptChainEtagViolation(code="four_state", message="four_state_max must be TEST_VERIFIED")
        )
    prior = doc.get("prior_gate_ids") or []
    if PRIOR_GATE_ID not in prior:
        violations.append(
            ReceiptChainEtagViolation(
                code="prior_gate_missing",
                message=f"must list {PRIOR_GATE_ID}",
            )
        )
    return violations


def _check_files() -> list[ReceiptChainEtagViolation]:
    violations: list[ReceiptChainEtagViolation] = []
    for rel in _REQUIRED_MODULES:
        if not (REPO_ROOT / rel).is_file():
            violations.append(
                ReceiptChainEtagViolation(
                    code="module_missing",
                    message=f"missing {rel}",
                    path=str(rel),
                )
            )
    if not (REPO_ROOT / VERIFY_SCRIPT_REL).is_file():
        violations.append(
            ReceiptChainEtagViolation(code="verify_script_missing", message=str(VERIFY_SCRIPT_REL))
        )
    checklist = REPO_ROOT / CHECKLIST_REL
    if checklist.is_file():
        try:
            doc = json.loads(checklist.read_text(encoding="utf-8"))
            violations.extend(validate_checklist_document(doc))
        except json.JSONDecodeError:
            violations.append(
                ReceiptChainEtagViolation(code="checklist_json", message="invalid checklist JSON")
            )
    else:
        violations.append(
            ReceiptChainEtagViolation(code="checklist_missing", message=str(CHECKLIST_REL))
        )
    return violations


def _check_route_markers() -> list[ReceiptChainEtagViolation]:
    violations: list[ReceiptChainEtagViolation] = []
    cp = (REPO_ROOT / "backend/api/v1/control_plane.py").read_text(encoding="utf-8")
    hc = (REPO_ROOT / "backend/api/v1/http_conditional.py").read_text(encoding="utf-8")
    blob = cp + hc
    for marker in _REQUIRED_MARKERS:
        if marker not in blob:
            violations.append(
                ReceiptChainEtagViolation(
                    code="route_marker_missing",
                    message=f"missing marker {marker}",
                )
            )
    return violations


def run_chain_fixture_suite() -> tuple[int, int, list[str]]:
    from thinkbox.receipt_chain_query import (
        ReceiptChainValidationError,
        decode_cursor,
        encode_cursor,
        fetch_chain_page,
        validate_receipt_link,
    )
    from thinkbox.agent.control_plane.store import ActionReceiptStore

    errors: list[str] = []
    positive = 0
    negative = 0

    store = ActionReceiptStore(":memory:")
    store.append("a", "ok", "r", "simulated", metadata={"agent_id": "ag1"})
    store.append("b", "ok", "r", "simulated", metadata={"agent_id": "ag1"})
    page = fetch_chain_page(store, limit=1)
    if page.receipts and page.next_cursor:
        positive += 1
    else:
        errors.append("pagination positive")

    try:
        decode_cursor("not-valid!!!")
        negative += 0
        errors.append("cursor negative expected")
    except ReceiptChainValidationError:
        negative += 1

    rid = page.receipts[0]["receipt_id"]
    try:
        validate_receipt_link(store, rid)
        positive += 1
    except ReceiptChainValidationError:
        errors.append("validate link positive")

    try:
        validate_receipt_link(store, "missing")
        errors.append("missing receipt negative")
    except ReceiptChainValidationError:
        negative += 1

    c1 = encode_cursor(1)
    if decode_cursor(c1) == 1:
        positive += 1
    else:
        errors.append("cursor roundtrip")

    fixtures_dir = REPO_ROOT / FIXTURES_REL
    if fixtures_dir.is_dir():
        for path in sorted(fixtures_dir.glob("*.json")):
            doc = json.loads(path.read_text(encoding="utf-8"))
            expect_fail = doc.get("expect_validation_error", False)
            receipt_id = doc.get("receipt_id")
            if expect_fail and receipt_id:
                try:
                    validate_receipt_link(store, receipt_id)
                    errors.append(f"fixture {path.name} should fail")
                except ReceiptChainValidationError:
                    negative += 1
            elif doc.get("expect_ok"):
                positive += 1

    return positive, negative, errors


def evaluate_receipt_chain_etag(
    mode: EnvMatrixMode | None = None,
    environ: Mapping[str, str] | None = None,
) -> ReceiptChainEtagResult:
    env: Mapping[str, str] = environ if environ is not None else os.environ
    resolved = mode if mode is not None else detect_matrix_mode(env)
    violations: list[ReceiptChainEtagViolation] = []

    cp = hermetic_control_plane_api_operator_check(env)
    if not cp.ok:
        violations.append(
            ReceiptChainEtagViolation(
                code="control_plane_api_failed",
                message=f"prior gate {PRIOR_GATE_ID} must pass",
            )
        )

    file_violations = _check_files()
    violations.extend(file_violations)
    route_violations = _check_route_markers()
    violations.extend(route_violations)

    pos, neg, fixture_errors = run_chain_fixture_suite()
    for err in fixture_errors:
        violations.append(ReceiptChainEtagViolation(code="fixture_failed", message=err))

    fixture_ok = not fixture_errors and pos >= 3 and neg >= 2
    if not fixture_ok:
        violations.append(
            ReceiptChainEtagViolation(code="fixture_suite_weak", message="chain fixtures insufficient")
        )

    route_ok = len(route_violations) == 0
    ok = (
        cp.ok
        and fixture_ok
        and route_ok
        and not file_violations
        and not fixture_errors
    )
    evidence = ReceiptChainEtagEvidence(
        gate_id=GATE_ID,
        pr_number=PR_NUMBER,
        control_plane_api_ok=cp.ok,
        route_markers_ok=route_ok,
        fixture_suite_ok=fixture_ok,
    )
    return ReceiptChainEtagResult(
        mode=resolved,
        ok=ok,
        control_plane_api_ok=cp.ok,
        violations=violations if not ok else [],
        evidence=evidence,
    )


def hermetic_receipt_chain_etag_check(
    environ: Mapping[str, str] | None = None,
) -> ReceiptChainEtagResult:
    env: Mapping[str, str] = environ if environ is not None else os.environ
    return evaluate_receipt_chain_etag(detect_matrix_mode(env), env)


def receipt_chain_etag_gate_closed() -> bool:
    return hermetic_receipt_chain_etag_check(minimal_receipt_chain_etag_environ()).ok


def receipt_chain_etag_contract_summary(
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    env: Mapping[str, str] = environ if environ is not None else os.environ
    result = hermetic_receipt_chain_etag_check(env)
    return {
        "gate_id": GATE_ID,
        "pr_number": PR_NUMBER,
        "pr155_gate_id": GATE_ID,
        "pr154_layer_gate_id": PRIOR_GATE_ID,
        "detected_mode": detect_matrix_mode(env).value,
        "hermetic_operator_ok": result.ok,
        "control_plane_api_ok": result.control_plane_api_ok,
        "live_api_called": False,
        "four_state_max": "TEST_VERIFIED",
        "live_proof_in_this_pr": False,
        "gate_closed_default": receipt_chain_etag_gate_closed(),
        "verify_script": str(VERIFY_SCRIPT_REL),
        "verify_script_present": (REPO_ROOT / VERIFY_SCRIPT_REL).is_file(),
        "checklist_rel": str(CHECKLIST_REL),
        "fixtures_rel": str(FIXTURES_REL),
        "hermetic_violation_codes": sorted({v.code for v in result.violations}),
    }
