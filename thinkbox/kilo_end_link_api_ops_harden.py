"""Hermetic END LINK stack API / ops harden gate (PR #161).

Layers on PR #160 ``receipt-chain-end-link-docs``. Default: no network;
``live_api_called=False``.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from thinkbox.end_link_api_ops_harden import (
    END_LINK_API_OPS_HARDEN_LABEL,
    END_LINK_API_OPS_HARDEN_VERSION,
    OpsRouteTiming,
    end_link_api_ops_harden_contract_snippet,
    enrich_batch_validate_payload,
    enrich_validate_payload,
    normalize_failure_code,
    validate_chain_filter_query,
)
from thinkbox.kilo_env_matrix import EnvMatrixMode, detect_matrix_mode
from thinkbox.kilo_live_proof_readiness import REPO_ROOT
from thinkbox.kilo_receipt_chain_end_link_docs import (
    GATE_ID as PRIOR_GATE_ID,
)
from thinkbox.kilo_receipt_chain_end_link_docs import (
    hermetic_receipt_chain_end_link_docs_check,
    minimal_receipt_chain_end_link_docs_environ,
)

__all__ = (
    "CHECKLIST_REL",
    "FIXTURES_REL",
    "GATE_ID",
    "PR_NUMBER",
    "VERIFY_SCRIPT_REL",
    "EndLinkApiOpsHardenEvidence",
    "EndLinkApiOpsHardenResult",
    "EndLinkApiOpsHardenViolation",
    "end_link_api_ops_harden_contract_summary",
    "end_link_api_ops_harden_gate_closed",
    "evaluate_end_link_api_ops_harden",
    "hermetic_end_link_api_ops_harden_check",
    "minimal_end_link_api_ops_harden_environ",
    "run_api_ops_harden_fixture_suite",
    "validate_checklist_document",
)

GATE_ID = "end-link-api-ops-harden"
PR_NUMBER = 161

VERIFY_SCRIPT_REL = Path("scripts/verify_kilo_end_link_api_ops_harden.py")
CHECKLIST_REL = Path("data/kilo_end_link_api_ops_harden/checklist.json")
FIXTURES_REL = Path("data/kilo_end_link_api_ops_harden/fixtures")

_REQUIRED_MARKERS: tuple[str, ...] = (
    END_LINK_API_OPS_HARDEN_LABEL,
    "validate_chain_filter_query",
    "enrich_validate_payload",
    "enrich_batch_validate_payload",
    "normalize_failure_code",
    "OpsRouteTiming",
    "idempotent_retry_safe",
    "timing_ms",
    "failure_code",
    "Idempotency-Key",
    "chain_filter_invalid",
)

_REQUIRED_MODULES: tuple[Path, ...] = (
    Path("thinkbox/end_link_api_ops_harden.py"),
    Path("thinkbox/kilo_end_link_api_ops_harden.py"),
    Path("backend/api/v1/control_plane.py"),
    Path("tests/unit/test_end_link_api_ops_harden.py"),
    Path("tests/unit/test_backend_end_link_api_ops_harden_pr161.py"),
    Path("tests/unit/test_kilo_live_proof_readiness_pr161.py"),
)


@dataclass(frozen=True)
class EndLinkApiOpsHardenViolation:
    code: str
    message: str
    path: str | None = None


@dataclass(frozen=True)
class EndLinkApiOpsHardenEvidence:
    gate_id: str
    pr_number: int
    receipt_chain_end_link_docs_ok: bool
    module_markers_ok: bool
    fixture_suite_ok: bool
    live_api_called: bool = False
    four_state_max: str = "TEST_VERIFIED"


@dataclass(frozen=True)
class EndLinkApiOpsHardenResult:
    mode: EnvMatrixMode
    ok: bool
    receipt_chain_end_link_docs_ok: bool
    violations: list[EndLinkApiOpsHardenViolation]
    evidence: EndLinkApiOpsHardenEvidence | None = None


def minimal_end_link_api_ops_harden_environ(
    extra: Mapping[str, str] | None = None,
) -> dict[str, str]:
    base: MutableMapping[str, str] = dict(minimal_receipt_chain_end_link_docs_environ())
    if extra:
        base.update(extra)
    return dict(base)


def validate_checklist_document(doc: Mapping[str, Any]) -> list[EndLinkApiOpsHardenViolation]:
    violations: list[EndLinkApiOpsHardenViolation] = []
    if doc.get("gate_id") != GATE_ID:
        violations.append(
            EndLinkApiOpsHardenViolation(code="gate_id_mismatch", message="checklist gate_id")
        )
    if doc.get("pr_number") != PR_NUMBER:
        violations.append(
            EndLinkApiOpsHardenViolation(code="pr_number_mismatch", message="checklist pr_number")
        )
    if doc.get("live_verified") is True:
        violations.append(
            EndLinkApiOpsHardenViolation(code="live_verified_true", message="must stay false")
        )
    if doc.get("live_api_called") is True:
        violations.append(
            EndLinkApiOpsHardenViolation(code="live_api_called_true", message="must stay false")
        )
    if doc.get("four_state_max") != "TEST_VERIFIED":
        violations.append(
            EndLinkApiOpsHardenViolation(
                code="four_state", message="four_state_max must be TEST_VERIFIED"
            ),
        )
    if doc.get("end_link_api_ops_harden_version") != END_LINK_API_OPS_HARDEN_VERSION:
        violations.append(
            EndLinkApiOpsHardenViolation(
                code="version_mismatch", message="end_link_api_ops_harden_version"
            ),
        )
    prior = doc.get("prior_gate_ids") or []
    if PRIOR_GATE_ID not in prior:
        violations.append(
            EndLinkApiOpsHardenViolation(
                code="prior_gate_missing", message=f"must list {PRIOR_GATE_ID}"
            ),
        )
    return violations


def _check_files() -> list[EndLinkApiOpsHardenViolation]:
    violations: list[EndLinkApiOpsHardenViolation] = []
    for rel in _REQUIRED_MODULES:
        if not (REPO_ROOT / rel).is_file():
            violations.append(
                EndLinkApiOpsHardenViolation(
                    code="module_missing", message=f"missing {rel}", path=str(rel)
                ),
            )
    if not (REPO_ROOT / VERIFY_SCRIPT_REL).is_file():
        violations.append(
            EndLinkApiOpsHardenViolation(
                code="verify_script_missing", message=str(VERIFY_SCRIPT_REL)
            ),
        )
    checklist = REPO_ROOT / CHECKLIST_REL
    if checklist.is_file():
        try:
            doc = json.loads(checklist.read_text(encoding="utf-8"))
            violations.extend(validate_checklist_document(doc))
        except json.JSONDecodeError:
            violations.append(
                EndLinkApiOpsHardenViolation(code="checklist_json", message="invalid JSON")
            )
    else:
        violations.append(
            EndLinkApiOpsHardenViolation(code="checklist_missing", message=str(CHECKLIST_REL))
        )
    return violations


def _check_markers() -> list[EndLinkApiOpsHardenViolation]:
    violations: list[EndLinkApiOpsHardenViolation] = []
    backend = (REPO_ROOT / "backend/api/v1/control_plane.py").read_text(encoding="utf-8")
    harden = (REPO_ROOT / "thinkbox/end_link_api_ops_harden.py").read_text(encoding="utf-8")
    blob = backend + harden
    for marker in _REQUIRED_MARKERS:
        if marker not in blob:
            violations.append(
                EndLinkApiOpsHardenViolation(code="marker_missing", message=f"missing {marker!r}"),
            )
    return violations


def run_api_ops_harden_fixture_suite() -> tuple[int, int, list[str]]:
    errors: list[str] = []
    positive = 0
    negative = 0

    if normalize_failure_code("Receipt-Not-Found") == "receipt_not_found":
        positive += 1
    else:
        errors.append("normalize_failure_code")

    _params, errs = validate_chain_filter_query(status="OK")
    if not errs:
        positive += 1
    else:
        errors.append("chain_filter_ok")

    _bad, bad_errs = validate_chain_filter_query(status="bad filter!")
    if bad_errs:
        negative += 1
    else:
        errors.append("chain_filter_bad")

    timing = OpsRouteTiming.start("fixture")
    enriched = enrich_validate_payload({"valid": True, "receipt_id": "r1"}, timing=timing)
    ops = enriched.get("ops") or {}
    if ops.get("idempotent_retry_safe") and ops.get("timing_ms") is not None:
        positive += 1
    else:
        errors.append("enrich_validate")

    batch = enrich_batch_validate_payload(
        {"items": [], "total": 0}, timing=timing, idempotency_key="k1"
    )
    if batch.get("ops", {}).get("idempotency_key_present"):
        positive += 1
    else:
        errors.append("enrich_batch")

    snippet = end_link_api_ops_harden_contract_snippet()
    if snippet.get("live_verified") is False and snippet.get("four_state_max") == "TEST_VERIFIED":
        positive += 1
    else:
        errors.append("contract_snippet")

    fixtures_dir = REPO_ROOT / FIXTURES_REL
    if fixtures_dir.is_dir():
        for path in sorted(fixtures_dir.glob("*.json")):
            doc = json.loads(path.read_text(encoding="utf-8"))
            if doc.get("expect_ok"):
                positive += 1
            if doc.get("expect_fail"):
                negative += 1

    return positive, negative, errors


def evaluate_end_link_api_ops_harden(
    mode: EnvMatrixMode | None = None,
    environ: Mapping[str, str] | None = None,
) -> EndLinkApiOpsHardenResult:
    env: Mapping[str, str] = environ if environ is not None else os.environ
    resolved = mode if mode is not None else detect_matrix_mode(env)
    violations: list[EndLinkApiOpsHardenViolation] = []

    prior = hermetic_receipt_chain_end_link_docs_check(env)
    if not prior.ok:
        violations.append(
            EndLinkApiOpsHardenViolation(
                code="prior_docs_gate_failed",
                message=f"prior gate {PRIOR_GATE_ID} must pass",
            ),
        )

    file_violations = _check_files()
    violations.extend(file_violations)
    marker_violations = _check_markers()
    violations.extend(marker_violations)

    pos, neg, fixture_errors = run_api_ops_harden_fixture_suite()
    for err in fixture_errors:
        violations.append(EndLinkApiOpsHardenViolation(code="fixture_failed", message=err))

    fixture_ok = not fixture_errors and pos >= 4 and neg >= 1
    if not fixture_ok:
        violations.append(
            EndLinkApiOpsHardenViolation(code="fixture_suite_weak", message="api ops fixtures weak")
        )

    markers_ok = len(marker_violations) == 0
    ok = prior.ok and fixture_ok and markers_ok and not file_violations and not fixture_errors
    evidence = EndLinkApiOpsHardenEvidence(
        gate_id=GATE_ID,
        pr_number=PR_NUMBER,
        receipt_chain_end_link_docs_ok=prior.ok,
        module_markers_ok=markers_ok,
        fixture_suite_ok=fixture_ok,
    )
    return EndLinkApiOpsHardenResult(
        mode=resolved,
        ok=ok,
        receipt_chain_end_link_docs_ok=prior.ok,
        violations=violations if not ok else [],
        evidence=evidence,
    )


def hermetic_end_link_api_ops_harden_check(
    environ: Mapping[str, str] | None = None,
) -> EndLinkApiOpsHardenResult:
    env: Mapping[str, str] = environ if environ is not None else os.environ
    return evaluate_end_link_api_ops_harden(detect_matrix_mode(env), env)


def end_link_api_ops_harden_gate_closed() -> bool:
    return hermetic_end_link_api_ops_harden_check(minimal_end_link_api_ops_harden_environ()).ok


def end_link_api_ops_harden_contract_summary(
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    env: Mapping[str, str] = environ if environ is not None else os.environ
    result = hermetic_end_link_api_ops_harden_check(env)
    return {
        "gate_id": GATE_ID,
        "pr_number": PR_NUMBER,
        "pr161_gate_id": GATE_ID,
        "pr160_layer_gate_id": PRIOR_GATE_ID,
        "end_link_api_ops_harden": END_LINK_API_OPS_HARDEN_LABEL,
        "end_link_api_ops_harden_version": END_LINK_API_OPS_HARDEN_VERSION,
        "detected_mode": detect_matrix_mode(env).value,
        "hermetic_operator_ok": result.ok,
        "receipt_chain_end_link_docs_ok": result.receipt_chain_end_link_docs_ok,
        "live_api_called": False,
        "live_verified": False,
        "four_state_max": "TEST_VERIFIED",
        "live_proof_in_this_pr": False,
        "gate_closed_default": end_link_api_ops_harden_gate_closed(),
        "verify_script": str(VERIFY_SCRIPT_REL),
        "verify_script_present": (REPO_ROOT / VERIFY_SCRIPT_REL).is_file(),
        "checklist_rel": str(CHECKLIST_REL),
        "fixtures_rel": str(FIXTURES_REL),
        "hermetic_violation_codes": sorted({v.code for v in result.violations}),
    }
