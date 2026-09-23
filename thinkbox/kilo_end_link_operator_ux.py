"""Hermetic END LINK operator UX gate (PR #159, ``end-link-operator-ux``).

Layers on PR #158 ``end-link-deepen``. Default: no network; ``live_api_called=False``.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, MutableMapping

from thinkbox.agent.control_plane.store import ActionReceiptStore
from thinkbox.end_link_api import END_LINK_API_LABEL
from thinkbox.end_link_deepen import END_LINK_DEEPEN_LABEL, run_end_link_batch_validate
from thinkbox.end_link_operator_ux import (
    END_LINK_OPERATOR_UX_LABEL,
    END_LINK_OPERATOR_UX_VERSION,
    ChainFilterParams,
    build_chain_filter_query,
    end_link_operator_ux_contract_snippet,
    four_state_honesty_copy,
    summarize_end_link_batch,
)
from thinkbox.kilo_end_link_deepen import (
    GATE_ID as PRIOR_GATE_ID,
    hermetic_end_link_deepen_check,
    minimal_end_link_deepen_environ,
)
from thinkbox.kilo_env_matrix import EnvMatrixMode, detect_matrix_mode
from thinkbox.kilo_live_proof_readiness import REPO_ROOT

__all__ = (
    "CHECKLIST_REL",
    "FIXTURES_REL",
    "GATE_ID",
    "PR_NUMBER",
    "VERIFY_SCRIPT_REL",
    "EndLinkOperatorUxEvidence",
    "EndLinkOperatorUxResult",
    "EndLinkOperatorUxViolation",
    "end_link_operator_ux_contract_summary",
    "end_link_operator_ux_gate_closed",
    "evaluate_end_link_operator_ux",
    "hermetic_end_link_operator_ux_check",
    "minimal_end_link_operator_ux_environ",
    "run_operator_ux_fixture_suite",
    "validate_checklist_document",
)

GATE_ID = "end-link-operator-ux"
PR_NUMBER = 159

VERIFY_SCRIPT_REL = Path("scripts/verify_kilo_end_link_operator_ux.py")
CHECKLIST_REL = Path("data/kilo_end_link_operator_ux/checklist.json")
FIXTURES_REL = Path("data/kilo_end_link_operator_ux/fixtures")

_REQUIRED_MARKERS: tuple[str, ...] = (
    END_LINK_OPERATOR_UX_LABEL,
    END_LINK_DEEPEN_LABEL,
    "endLinkBatchSummary",
    "chainFilterStatus",
    "chainFilterEvidenceLabel",
    "renderBatchResults",
    "four_state_honesty",
    "prev_receipt_id",
    "failure_code",
    "link_integrity",
)

_REQUIRED_MODULES: tuple[Path, ...] = (
    Path("thinkbox/end_link_operator_ux.py"),
    Path("thinkbox/kilo_end_link_operator_ux.py"),
    Path("public/control-plane/control_plane_end_link_operator_ux.js"),
    Path("public/control-plane/receipt_chain_dashboard.html"),
    Path("tests/unit/test_end_link_operator_ux.py"),
    Path("tests/unit/test_dashboard_end_link_operator_ux_pr159.py"),
    Path("tests/unit/test_kilo_live_proof_readiness_pr159.py"),
)


@dataclass(frozen=True)
class EndLinkOperatorUxViolation:
    code: str
    message: str
    path: str | None = None


@dataclass(frozen=True)
class EndLinkOperatorUxEvidence:
    gate_id: str
    pr_number: int
    end_link_deepen_ok: bool
    module_markers_ok: bool
    fixture_suite_ok: bool
    live_api_called: bool = False
    four_state_max: str = "TEST_VERIFIED"


@dataclass(frozen=True)
class EndLinkOperatorUxResult:
    mode: EnvMatrixMode
    ok: bool
    end_link_deepen_ok: bool
    violations: list[EndLinkOperatorUxViolation]
    evidence: EndLinkOperatorUxEvidence | None = None


def minimal_end_link_operator_ux_environ(
    extra: Mapping[str, str] | None = None,
) -> dict[str, str]:
    base: MutableMapping[str, str] = dict(minimal_end_link_deepen_environ())
    if extra:
        base.update(extra)
    return dict(base)


def validate_checklist_document(doc: Mapping[str, Any]) -> list[EndLinkOperatorUxViolation]:
    violations: list[EndLinkOperatorUxViolation] = []
    if doc.get("gate_id") != GATE_ID:
        violations.append(EndLinkOperatorUxViolation(code="gate_id_mismatch", message="checklist gate_id"))
    if doc.get("pr_number") != PR_NUMBER:
        violations.append(EndLinkOperatorUxViolation(code="pr_number_mismatch", message="checklist pr_number"))
    if doc.get("live_verified") is True:
        violations.append(EndLinkOperatorUxViolation(code="live_verified_true", message="must stay false"))
    if doc.get("four_state_max") != "TEST_VERIFIED":
        violations.append(
            EndLinkOperatorUxViolation(code="four_state", message="four_state_max must be TEST_VERIFIED"),
        )
    if doc.get("end_link_operator_ux_version") != END_LINK_OPERATOR_UX_VERSION:
        violations.append(
            EndLinkOperatorUxViolation(code="ux_version", message="end_link_operator_ux_version mismatch"),
        )
    prior = doc.get("prior_gate_ids") or []
    if PRIOR_GATE_ID not in prior:
        violations.append(
            EndLinkOperatorUxViolation(code="prior_gate_missing", message=f"must list {PRIOR_GATE_ID}"),
        )
    if doc.get("end_link_api") != END_LINK_API_LABEL:
        violations.append(EndLinkOperatorUxViolation(code="end_link_api", message="end_link_api label"))
    return violations


def _check_files() -> list[EndLinkOperatorUxViolation]:
    violations: list[EndLinkOperatorUxViolation] = []
    for rel in _REQUIRED_MODULES:
        if not (REPO_ROOT / rel).is_file():
            violations.append(
                EndLinkOperatorUxViolation(code="module_missing", message=f"missing {rel}", path=str(rel)),
            )
    if not (REPO_ROOT / VERIFY_SCRIPT_REL).is_file():
        violations.append(
            EndLinkOperatorUxViolation(code="verify_script_missing", message=str(VERIFY_SCRIPT_REL)),
        )
    checklist = REPO_ROOT / CHECKLIST_REL
    if checklist.is_file():
        try:
            doc = json.loads(checklist.read_text(encoding="utf-8"))
            violations.extend(validate_checklist_document(doc))
        except json.JSONDecodeError:
            violations.append(EndLinkOperatorUxViolation(code="checklist_json", message="invalid JSON"))
    else:
        violations.append(EndLinkOperatorUxViolation(code="checklist_missing", message=str(CHECKLIST_REL)))
    return violations


def _check_markers() -> list[EndLinkOperatorUxViolation]:
    violations: list[EndLinkOperatorUxViolation] = []
    html = (REPO_ROOT / "public/control-plane/receipt_chain_dashboard.html").read_text(encoding="utf-8")
    ux_js = (REPO_ROOT / "public/control-plane/control_plane_end_link_operator_ux.js").read_text(
        encoding="utf-8",
    )
    client_js = (REPO_ROOT / "public/control-plane/control_plane_end_link_client.js").read_text(
        encoding="utf-8",
    )
    models = (REPO_ROOT / "thinkbox/dashboard_receipt_chain_models.py").read_text(encoding="utf-8")
    blob = html + ux_js + client_js + models
    for marker in _REQUIRED_MARKERS:
        if marker not in blob:
            violations.append(
                EndLinkOperatorUxViolation(code="marker_missing", message=f"missing {marker!r}"),
            )
    return violations


def run_operator_ux_fixture_suite() -> tuple[int, int, list[str]]:
    errors: list[str] = []
    positive = 0
    negative = 0

    store = ActionReceiptStore(":memory:")
    receipt = store.append("act", "OK", "r", "simulated", metadata={})
    rid = receipt.receipt_id
    batch = run_end_link_batch_validate(store, [rid, "missing_rcpt"])
    summary = summarize_end_link_batch(batch.to_dict())
    if summary.valid_count == 1 and summary.invalid_count == 1 and summary.fail_closed:
        positive += 1
    else:
        errors.append("batch_summary")

    filt = ChainFilterParams(status_filter="OK", evidence_label="simulated")
    q = build_chain_filter_query(filt)
    if "status=OK" in q and "evidence_label=simulated" in q:
        positive += 1
    else:
        errors.append("chain_filter_query")

    copy = four_state_honesty_copy()
    if copy.get("four_state_max") == "TEST_VERIFIED" and copy.get("live_api_called") == "false":
        positive += 1
    else:
        errors.append("honesty_copy")

    snippet = end_link_operator_ux_contract_snippet()
    if snippet.get("end_link_operator_ux") == END_LINK_OPERATOR_UX_LABEL:
        positive += 1
    else:
        errors.append("contract_snippet")

    if summary.rows and summary.rows[0].prev_receipt_id is None and summary.rows[0].link_integrity == "ok":
        positive += 1
    else:
        errors.append("row_integrity_fields")

    fixtures_dir = REPO_ROOT / FIXTURES_REL
    if fixtures_dir.is_dir():
        for path in sorted(fixtures_dir.glob("*.json")):
            doc = json.loads(path.read_text(encoding="utf-8"))
            if doc.get("expect_ok"):
                positive += 1
            if doc.get("expect_fail"):
                negative += 1

    return positive, negative, errors


def evaluate_end_link_operator_ux(
    mode: EnvMatrixMode | None = None,
    environ: Mapping[str, str] | None = None,
) -> EndLinkOperatorUxResult:
    env: Mapping[str, str] = environ if environ is not None else os.environ
    resolved = mode if mode is not None else detect_matrix_mode(env)
    violations: list[EndLinkOperatorUxViolation] = []

    prior = hermetic_end_link_deepen_check(env)
    if not prior.ok:
        violations.append(
            EndLinkOperatorUxViolation(
                code="end_link_deepen_failed",
                message=f"prior gate {PRIOR_GATE_ID} must pass",
            ),
        )

    file_violations = _check_files()
    violations.extend(file_violations)
    marker_violations = _check_markers()
    violations.extend(marker_violations)

    pos, neg, fixture_errors = run_operator_ux_fixture_suite()
    for err in fixture_errors:
        violations.append(EndLinkOperatorUxViolation(code="fixture_failed", message=err))

    fixture_ok = not fixture_errors and pos >= 4 and neg >= 0
    if not fixture_ok:
        violations.append(EndLinkOperatorUxViolation(code="fixture_suite_weak", message="operator ux fixtures weak"))

    markers_ok = len(marker_violations) == 0
    ok = prior.ok and fixture_ok and markers_ok and not file_violations and not fixture_errors
    evidence = EndLinkOperatorUxEvidence(
        gate_id=GATE_ID,
        pr_number=PR_NUMBER,
        end_link_deepen_ok=prior.ok,
        module_markers_ok=markers_ok,
        fixture_suite_ok=fixture_ok,
    )
    return EndLinkOperatorUxResult(
        mode=resolved,
        ok=ok,
        end_link_deepen_ok=prior.ok,
        violations=violations if not ok else [],
        evidence=evidence,
    )


def hermetic_end_link_operator_ux_check(
    environ: Mapping[str, str] | None = None,
) -> EndLinkOperatorUxResult:
    env: Mapping[str, str] = environ if environ is not None else os.environ
    return evaluate_end_link_operator_ux(detect_matrix_mode(env), env)


def end_link_operator_ux_gate_closed() -> bool:
    return hermetic_end_link_operator_ux_check(minimal_end_link_operator_ux_environ()).ok


def end_link_operator_ux_contract_summary(
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    env: Mapping[str, str] = environ if environ is not None else os.environ
    result = hermetic_end_link_operator_ux_check(env)
    return {
        "gate_id": GATE_ID,
        "pr_number": PR_NUMBER,
        "pr159_gate_id": GATE_ID,
        "pr158_layer_gate_id": PRIOR_GATE_ID,
        "end_link_operator_ux": END_LINK_OPERATOR_UX_LABEL,
        "end_link_operator_ux_version": END_LINK_OPERATOR_UX_VERSION,
        "end_link_deepen": END_LINK_DEEPEN_LABEL,
        "end_link_api": END_LINK_API_LABEL,
        "detected_mode": detect_matrix_mode(env).value,
        "hermetic_operator_ok": result.ok,
        "end_link_deepen_ok": result.end_link_deepen_ok,
        "live_api_called": False,
        "four_state_max": "TEST_VERIFIED",
        "live_proof_in_this_pr": False,
        "gate_closed_default": end_link_operator_ux_gate_closed(),
        "verify_script": str(VERIFY_SCRIPT_REL),
        "verify_script_present": (REPO_ROOT / VERIFY_SCRIPT_REL).is_file(),
        "checklist_rel": str(CHECKLIST_REL),
        "fixtures_rel": str(FIXTURES_REL),
        "hermetic_violation_codes": sorted({v.code for v in result.violations}),
    }
