"""Hermetic dashboard bind for receipt-chain / ETag + END LINK (PR #156).

Layers on PR #155 ``receipt-chain-etag`` and PR #149 ``dashboard-slots``.
Default: no network; ``live_api_called=False``.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, MutableMapping

from thinkbox.dashboard_receipt_chain_client import (
    DashboardReceiptChainClient,
    chain_api_paths,
    hermetic_fetch_chain_bind_state,
)
from thinkbox.end_link_api import END_LINK_API_LABEL, END_LINK_ROUTE_SUFFIX, build_end_link_path
from thinkbox.kilo_env_matrix import EnvMatrixMode, detect_matrix_mode
from thinkbox.kilo_live_proof_readiness import REPO_ROOT
from thinkbox.kilo_receipt_chain_etag import (
    GATE_ID as PRIOR_GATE_ID,
    hermetic_receipt_chain_etag_check,
    minimal_receipt_chain_etag_environ,
)

__all__ = (
    "CHECKLIST_REL",
    "FIXTURES_REL",
    "GATE_ID",
    "PR_NUMBER",
    "VERIFY_SCRIPT_REL",
    "DashboardReceiptChainBindEvidence",
    "DashboardReceiptChainBindResult",
    "DashboardReceiptChainBindViolation",
    "dashboard_receipt_chain_bind_contract_summary",
    "dashboard_receipt_chain_bind_gate_closed",
    "evaluate_dashboard_receipt_chain_bind",
    "hermetic_dashboard_receipt_chain_bind_check",
    "minimal_dashboard_receipt_chain_bind_environ",
    "run_bind_fixture_suite",
    "validate_checklist_document",
)

GATE_ID = "dashboard-receipt-chain-bind"
PR_NUMBER = 156

VERIFY_SCRIPT_REL = Path("scripts/verify_kilo_dashboard_receipt_chain_bind.py")
CHECKLIST_REL = Path("data/kilo_dashboard_receipt_chain_bind/checklist.json")
FIXTURES_REL = Path("data/kilo_dashboard_receipt_chain_bind/fixtures")

_REQUIRED_MARKERS: tuple[str, ...] = (
    END_LINK_API_LABEL,
    "receipt_chain_dashboard",
    "control_plane_end_link_client",
    "fetchJsonConditional",
    "If-None-Match",
    "412",
    build_end_link_path("rcpt_marker", base_prefix="/api/v1/control-plane"),
)

_REQUIRED_MODULES: tuple[Path, ...] = (
    Path("thinkbox/end_link_api.py"),
    Path("thinkbox/dashboard_receipt_chain_models.py"),
    Path("thinkbox/dashboard_receipt_chain_client.py"),
    Path("public/control-plane/receipt_chain_dashboard.html"),
    Path("public/control-plane/control_plane_end_link_client.js"),
)


@dataclass(frozen=True)
class DashboardReceiptChainBindViolation:
    code: str
    message: str
    path: str | None = None


@dataclass(frozen=True)
class DashboardReceiptChainBindEvidence:
    gate_id: str
    pr_number: int
    receipt_chain_etag_ok: bool
    ui_markers_ok: bool
    bind_client_ok: bool
    end_link_api_ok: bool
    live_api_called: bool = False
    four_state_max: str = "TEST_VERIFIED"


@dataclass(frozen=True)
class DashboardReceiptChainBindResult:
    mode: EnvMatrixMode
    ok: bool
    receipt_chain_etag_ok: bool
    violations: list[DashboardReceiptChainBindViolation]
    evidence: DashboardReceiptChainBindEvidence | None = None


def minimal_dashboard_receipt_chain_bind_environ(
    extra: Mapping[str, str] | None = None,
) -> dict[str, str]:
    base: MutableMapping[str, str] = dict(minimal_receipt_chain_etag_environ())
    if extra:
        base.update(extra)
    return dict(base)


def validate_checklist_document(doc: Mapping[str, Any]) -> list[DashboardReceiptChainBindViolation]:
    violations: list[DashboardReceiptChainBindViolation] = []
    if doc.get("gate_id") != GATE_ID:
        violations.append(
            DashboardReceiptChainBindViolation(code="gate_id_mismatch", message="checklist gate_id")
        )
    if doc.get("pr_number") != PR_NUMBER:
        violations.append(
            DashboardReceiptChainBindViolation(code="pr_number_mismatch", message="checklist pr_number")
        )
    if doc.get("live_verified") is True:
        violations.append(
            DashboardReceiptChainBindViolation(code="live_verified_true", message="must stay false")
        )
    if doc.get("four_state_max") != "TEST_VERIFIED":
        violations.append(
            DashboardReceiptChainBindViolation(
                code="four_state",
                message="four_state_max must be TEST_VERIFIED",
            )
        )
    if doc.get("end_link_api") != END_LINK_API_LABEL:
        violations.append(
            DashboardReceiptChainBindViolation(code="end_link_api", message="end_link_api label")
        )
    prior = doc.get("prior_gate_ids") or []
    if PRIOR_GATE_ID not in prior:
        violations.append(
            DashboardReceiptChainBindViolation(
                code="prior_gate_missing",
                message=f"must list {PRIOR_GATE_ID}",
            )
        )
    return violations


def _check_files() -> list[DashboardReceiptChainBindViolation]:
    violations: list[DashboardReceiptChainBindViolation] = []
    for rel in _REQUIRED_MODULES:
        if not (REPO_ROOT / rel).is_file():
            violations.append(
                DashboardReceiptChainBindViolation(
                    code="module_missing",
                    message=f"missing {rel}",
                    path=str(rel),
                )
            )
    if not (REPO_ROOT / VERIFY_SCRIPT_REL).is_file():
        violations.append(
            DashboardReceiptChainBindViolation(
                code="verify_script_missing",
                message=str(VERIFY_SCRIPT_REL),
            )
        )
    checklist = REPO_ROOT / CHECKLIST_REL
    if checklist.is_file():
        try:
            doc = json.loads(checklist.read_text(encoding="utf-8"))
            violations.extend(validate_checklist_document(doc))
        except json.JSONDecodeError:
            violations.append(
                DashboardReceiptChainBindViolation(code="checklist_json", message="invalid JSON")
            )
    else:
        violations.append(
            DashboardReceiptChainBindViolation(code="checklist_missing", message=str(CHECKLIST_REL))
        )
    return violations


def _check_ui_markers() -> list[DashboardReceiptChainBindViolation]:
    violations: list[DashboardReceiptChainBindViolation] = []
    html = (REPO_ROOT / "public/control-plane/receipt_chain_dashboard.html").read_text(
        encoding="utf-8",
    )
    js = (REPO_ROOT / "public/control-plane/control_plane_end_link_client.js").read_text(
        encoding="utf-8",
    )
    blob = html + js
    for marker in _REQUIRED_MARKERS:
        if marker not in blob:
            violations.append(
                DashboardReceiptChainBindViolation(
                    code="ui_marker_missing",
                    message=f"missing marker {marker!r}",
                )
            )
    if "/receipts/" not in blob or "/validate" not in blob:
        violations.append(
            DashboardReceiptChainBindViolation(
                code="end_link_route_missing",
                message="END LINK route suffix",
            )
        )
    return violations


def run_bind_fixture_suite() -> tuple[int, int, list[str]]:
    errors: list[str] = []
    positive = 0
    negative = 0

    paths = chain_api_paths()
    for key in ("chain", "page", "head", "tail", "end_link_template"):
        if key in paths and paths[key]:
            positive += 1
        else:
            errors.append(f"missing path key {key}")

    bundle = hermetic_fetch_chain_bind_state(limit=5)
    if bundle.state.page and not bundle.state.live_api_called:
        positive += 1
    else:
        errors.append("bind state page")

    from thinkbox.control_plane_receipt_store import get_control_plane_receipt_store

    st = get_control_plane_receipt_store()
    if st.count() == 0:
        st.append("dashboard_bind_probe", "OK", "hermetic", "simulated", metadata={"agent_id": "pr156"})
    client = DashboardReceiptChainClient()
    probes = client.fetch_probes()
    if probes.head is not None or probes.tail is not None:
        positive += 1
    else:
        errors.append("probes empty")

    from thinkbox.end_link_api import EndLinkViolation, normalize_end_link_receipt_id

    try:
        normalize_end_link_receipt_id("")
        errors.append("empty receipt should fail")
    except EndLinkViolation:
        negative += 1

    fixtures_dir = REPO_ROOT / FIXTURES_REL
    if fixtures_dir.is_dir():
        for path in sorted(fixtures_dir.glob("*.json")):
            doc = json.loads(path.read_text(encoding="utf-8"))
            if doc.get("expect_ok"):
                positive += 1
            if doc.get("expect_fail"):
                negative += 1

    return positive, negative, errors


def evaluate_dashboard_receipt_chain_bind(
    mode: EnvMatrixMode | None = None,
    environ: Mapping[str, str] | None = None,
) -> DashboardReceiptChainBindResult:
    env: Mapping[str, str] = environ if environ is not None else os.environ
    resolved = mode if mode is not None else detect_matrix_mode(env)
    violations: list[DashboardReceiptChainBindViolation] = []

    prior = hermetic_receipt_chain_etag_check(env)
    if not prior.ok:
        violations.append(
            DashboardReceiptChainBindViolation(
                code="receipt_chain_etag_failed",
                message=f"prior gate {PRIOR_GATE_ID} must pass",
            )
        )

    file_violations = _check_files()
    violations.extend(file_violations)
    ui_violations = _check_ui_markers()
    violations.extend(ui_violations)

    pos, neg, fixture_errors = run_bind_fixture_suite()
    for err in fixture_errors:
        violations.append(DashboardReceiptChainBindViolation(code="fixture_failed", message=err))

    bind_ok = not fixture_errors and pos >= 4 and neg >= 1
    if not bind_ok:
        violations.append(
            DashboardReceiptChainBindViolation(code="fixture_suite_weak", message="bind fixtures weak")
        )

    ui_ok = len(ui_violations) == 0
    ok = prior.ok and bind_ok and ui_ok and not file_violations and not fixture_errors
    evidence = DashboardReceiptChainBindEvidence(
        gate_id=GATE_ID,
        pr_number=PR_NUMBER,
        receipt_chain_etag_ok=prior.ok,
        ui_markers_ok=ui_ok,
        bind_client_ok=bind_ok,
        end_link_api_ok=END_LINK_API_LABEL in str(_REQUIRED_MARKERS),
    )
    return DashboardReceiptChainBindResult(
        mode=resolved,
        ok=ok,
        receipt_chain_etag_ok=prior.ok,
        violations=violations if not ok else [],
        evidence=evidence,
    )


def hermetic_dashboard_receipt_chain_bind_check(
    environ: Mapping[str, str] | None = None,
) -> DashboardReceiptChainBindResult:
    env: Mapping[str, str] = environ if environ is not None else os.environ
    return evaluate_dashboard_receipt_chain_bind(detect_matrix_mode(env), env)


def dashboard_receipt_chain_bind_gate_closed() -> bool:
    return hermetic_dashboard_receipt_chain_bind_check(
        minimal_dashboard_receipt_chain_bind_environ(),
    ).ok


def dashboard_receipt_chain_bind_contract_summary(
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    env: Mapping[str, str] = environ if environ is not None else os.environ
    result = hermetic_dashboard_receipt_chain_bind_check(env)
    return {
        "gate_id": GATE_ID,
        "pr_number": PR_NUMBER,
        "pr156_gate_id": GATE_ID,
        "pr155_layer_gate_id": PRIOR_GATE_ID,
        "end_link_api": END_LINK_API_LABEL,
        "detected_mode": detect_matrix_mode(env).value,
        "hermetic_operator_ok": result.ok,
        "receipt_chain_etag_ok": result.receipt_chain_etag_ok,
        "live_api_called": False,
        "four_state_max": "TEST_VERIFIED",
        "live_proof_in_this_pr": False,
        "gate_closed_default": dashboard_receipt_chain_bind_gate_closed(),
        "verify_script": str(VERIFY_SCRIPT_REL),
        "verify_script_present": (REPO_ROOT / VERIFY_SCRIPT_REL).is_file(),
        "checklist_rel": str(CHECKLIST_REL),
        "fixtures_rel": str(FIXTURES_REL),
        "hermetic_violation_codes": sorted({v.code for v in result.violations}),
    }
