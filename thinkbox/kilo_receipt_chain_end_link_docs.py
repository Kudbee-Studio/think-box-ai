"""Hermetic receipt-chain / END_LINK docs + audit pack gate (PR #160).

Layers on PR #159 ``end-link-operator-ux``. Validates consolidated operator docs,
era audit index (#155–#159), and spine honesty — no live HTTP.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, MutableMapping

from thinkbox.kilo_end_link_operator_ux import (
    GATE_ID as PRIOR_GATE_ID,
    hermetic_end_link_operator_ux_check,
    minimal_end_link_operator_ux_environ,
)
from thinkbox.kilo_env_matrix import EnvMatrixMode, detect_matrix_mode
from thinkbox.kilo_live_proof_readiness import REPO_ROOT

__all__ = (
    "CHECKLIST_REL",
    "ERA_CONSOLIDATED_REL",
    "FIXTURES_REL",
    "GATE_ID",
    "PR_NUMBER",
    "RECEIPT_CHAIN_END_LINK_DOCS_LABEL",
    "RECEIPT_CHAIN_END_LINK_DOCS_VERSION",
    "VERIFY_SCRIPT_REL",
    "ReceiptChainEndLinkDocsEvidence",
    "ReceiptChainEndLinkDocsResult",
    "ReceiptChainEndLinkDocsViolation",
    "evaluate_receipt_chain_end_link_docs",
    "hermetic_receipt_chain_end_link_docs_check",
    "minimal_receipt_chain_end_link_docs_environ",
    "receipt_chain_end_link_docs_contract_summary",
    "receipt_chain_end_link_docs_gate_closed",
    "run_docs_fixture_suite",
    "validate_checklist_document",
    "validate_era_consolidated_pack",
)

GATE_ID = "receipt-chain-end-link-docs"
PR_NUMBER = 160
RECEIPT_CHAIN_END_LINK_DOCS_LABEL = "receipt-chain-end-link-docs"
RECEIPT_CHAIN_END_LINK_DOCS_VERSION = "1.0.0"

VERIFY_SCRIPT_REL = Path("scripts/verify_kilo_receipt_chain_end_link_docs.py")
CHECKLIST_REL = Path("data/kilo_receipt_chain_end_link_docs/checklist.json")
FIXTURES_REL = Path("data/kilo_receipt_chain_end_link_docs/fixtures")
ERA_CONSOLIDATED_REL = Path("docs/audit/passes/2026-09-23-pr155-159-era-consolidated.json")
OPERATOR_GUIDE_REL = Path("docs/guides/kilo_receipt_chain_end_link_operator.md")
AUDIT_INDEX_REL = Path("docs/audit/AUDIT_INDEX.json")
PR160_PASS_REL = Path("docs/audit/passes/2026-09-23-pr160.json")

_ERA_PASS_RELS: tuple[Path, ...] = tuple(
    Path(f"docs/audit/passes/2026-09-23-pr{n}.json") for n in (155, 156, 157, 158, 159)
)

_REQUIRED_MARKERS: tuple[str, ...] = (
    RECEIPT_CHAIN_END_LINK_DOCS_LABEL,
    "live_verified: false",
    "live_api_called: false",
    "four_state_max",
    "TEST_VERIFIED",
    "END_LINK",
    "prev_receipt_id",
    "evidence_label",
    "batch validate",
)

_REQUIRED_MODULES: tuple[Path, ...] = (
    Path("thinkbox/kilo_receipt_chain_end_link_docs.py"),
    Path("docs/guides/kilo_receipt_chain_end_link_operator.md"),
    Path("docs/decisions/019-kilo-receipt-chain-end-link-docs-audit.md"),
    Path("docs/audit/checklists/kilo-receipt-chain-end-link-docs-pr160.md"),
    Path("tests/unit/test_kilo_live_proof_readiness_pr160.py"),
    Path("tests/unit/test_receipt_chain_end_link_docs.py"),
)


@dataclass(frozen=True)
class ReceiptChainEndLinkDocsViolation:
    code: str
    message: str
    path: str | None = None


@dataclass(frozen=True)
class ReceiptChainEndLinkDocsEvidence:
    gate_id: str
    pr_number: int
    end_link_operator_ux_ok: bool
    era_pack_ok: bool
    audit_index_ok: bool
    operator_guide_ok: bool
    live_api_called: bool = False
    four_state_max: str = "TEST_VERIFIED"


@dataclass(frozen=True)
class ReceiptChainEndLinkDocsResult:
    mode: EnvMatrixMode
    ok: bool
    end_link_operator_ux_ok: bool
    violations: list[ReceiptChainEndLinkDocsViolation]
    evidence: ReceiptChainEndLinkDocsEvidence | None = None


def minimal_receipt_chain_end_link_docs_environ(
    extra: Mapping[str, str] | None = None,
) -> dict[str, str]:
    base: MutableMapping[str, str] = dict(minimal_end_link_operator_ux_environ())
    if extra:
        base.update(extra)
    return dict(base)


def validate_checklist_document(doc: Mapping[str, Any]) -> list[ReceiptChainEndLinkDocsViolation]:
    violations: list[ReceiptChainEndLinkDocsViolation] = []
    if doc.get("gate_id") != GATE_ID:
        violations.append(ReceiptChainEndLinkDocsViolation(code="gate_id_mismatch", message="checklist gate_id"))
    if doc.get("pr_number") != PR_NUMBER:
        violations.append(ReceiptChainEndLinkDocsViolation(code="pr_number_mismatch", message="checklist pr_number"))
    if doc.get("live_verified") is True:
        violations.append(ReceiptChainEndLinkDocsViolation(code="live_verified_true", message="must stay false"))
    if doc.get("live_api_called") is True:
        violations.append(ReceiptChainEndLinkDocsViolation(code="live_api_called_true", message="must stay false"))
    if doc.get("four_state_max") != "TEST_VERIFIED":
        violations.append(
            ReceiptChainEndLinkDocsViolation(code="four_state", message="four_state_max must be TEST_VERIFIED"),
        )
    if doc.get("receipt_chain_end_link_docs_version") != RECEIPT_CHAIN_END_LINK_DOCS_VERSION:
        violations.append(
            ReceiptChainEndLinkDocsViolation(code="docs_version", message="version mismatch"),
        )
    prior = doc.get("prior_gate_ids") or []
    if PRIOR_GATE_ID not in prior:
        violations.append(
            ReceiptChainEndLinkDocsViolation(code="prior_gate_missing", message=f"must list {PRIOR_GATE_ID}"),
        )
    return violations


def validate_era_consolidated_pack(doc: Mapping[str, Any]) -> list[ReceiptChainEndLinkDocsViolation]:
    violations: list[ReceiptChainEndLinkDocsViolation] = []
    if doc.get("live_verified") is True:
        violations.append(ReceiptChainEndLinkDocsViolation(code="era_live_verified", message="era pack live_verified"))
    if doc.get("live_api_called") is True:
        violations.append(
            ReceiptChainEndLinkDocsViolation(code="era_live_api", message="era pack live_api_called"),
        )
    gates = doc.get("gates") or []
    if len(gates) != 5:
        violations.append(
            ReceiptChainEndLinkDocsViolation(code="era_gate_count", message="expected 5 gates in era pack"),
        )
    for entry in gates:
        if entry.get("live_verified") is True:
            violations.append(
                ReceiptChainEndLinkDocsViolation(
                    code="era_gate_live",
                    message=f"gate pr{entry.get('pr_number')} live_verified true",
                ),
            )
        pass_rel = entry.get("pass_file")
        if pass_rel:
            path = REPO_ROOT / "docs/audit" / str(pass_rel)
            if not path.is_file():
                violations.append(
                    ReceiptChainEndLinkDocsViolation(
                        code="era_pass_missing",
                        message=f"missing {pass_rel}",
                        path=str(pass_rel),
                    ),
                )
    return violations


def _check_files() -> list[ReceiptChainEndLinkDocsViolation]:
    violations: list[ReceiptChainEndLinkDocsViolation] = []
    for rel in _REQUIRED_MODULES:
        if not (REPO_ROOT / rel).is_file():
            violations.append(
                ReceiptChainEndLinkDocsViolation(code="module_missing", message=f"missing {rel}", path=str(rel)),
            )
    for rel in _ERA_PASS_RELS:
        if not (REPO_ROOT / rel).is_file():
            violations.append(
                ReceiptChainEndLinkDocsViolation(code="era_pass_file", message=f"missing {rel}", path=str(rel)),
            )
    if not (REPO_ROOT / ERA_CONSOLIDATED_REL).is_file():
        violations.append(
            ReceiptChainEndLinkDocsViolation(code="era_pack_missing", message="era consolidated pack"),
        )
    if not (REPO_ROOT / PR160_PASS_REL).is_file():
        violations.append(
            ReceiptChainEndLinkDocsViolation(code="pr160_pass_missing", message="pr160 audit pass"),
        )
    return violations


def _check_markers() -> list[ReceiptChainEndLinkDocsViolation]:
    violations: list[ReceiptChainEndLinkDocsViolation] = []
    guide_path = REPO_ROOT / OPERATOR_GUIDE_REL
    if guide_path.is_file():
        text = guide_path.read_text(encoding="utf-8")
        for marker in _REQUIRED_MARKERS:
            if marker not in text:
                violations.append(
                    ReceiptChainEndLinkDocsViolation(
                        code="guide_marker_missing",
                        message=f"operator guide missing: {marker}",
                        path=str(OPERATOR_GUIDE_REL),
                    ),
                )
    return violations


def _check_audit_index() -> list[ReceiptChainEndLinkDocsViolation]:
    violations: list[ReceiptChainEndLinkDocsViolation] = []
    index_path = REPO_ROOT / AUDIT_INDEX_REL
    if not index_path.is_file():
        violations.append(ReceiptChainEndLinkDocsViolation(code="audit_index_missing", message="AUDIT_INDEX"))
        return violations
    doc = json.loads(index_path.read_text(encoding="utf-8"))
    passes = doc.get("passes") or []
    required_suffixes = (
        "pr153.json",
        "pr154.json",
        "pr155.json",
        "pr156.json",
        "pr157.json",
        "pr158.json",
        "pr159.json",
        "pr160.json",
        "pr155-159-era-consolidated.json",
    )
    for suffix in required_suffixes:
        if not any(str(p).endswith(suffix) for p in passes):
            violations.append(
                ReceiptChainEndLinkDocsViolation(
                    code="audit_index_gap",
                    message=f"AUDIT_INDEX missing pass *{suffix}",
                    path=str(AUDIT_INDEX_REL),
                ),
            )
    return violations


def _check_per_pr_pass_honesty() -> list[ReceiptChainEndLinkDocsViolation]:
    violations: list[ReceiptChainEndLinkDocsViolation] = []
    for rel in _ERA_PASS_RELS:
        path = REPO_ROOT / rel
        if not path.is_file():
            continue
        body = json.loads(path.read_text(encoding="utf-8"))
        if body.get("live_verified") is True:
            violations.append(
                ReceiptChainEndLinkDocsViolation(
                    code="pass_live_verified",
                    message=f"{rel} live_verified true",
                    path=str(rel),
                ),
            )
        if body.get("live_api_called") is True:
            violations.append(
                ReceiptChainEndLinkDocsViolation(
                    code="pass_live_api",
                    message=f"{rel} live_api_called true",
                    path=str(rel),
                ),
            )
    return violations


def run_docs_fixture_suite() -> tuple[int, int, list[str]]:
    """Load JSON fixtures; return (positive_checks, negative_checks, errors)."""
    errors: list[str] = []
    positive = 0
    negative = 0
    honesty_path = REPO_ROOT / FIXTURES_REL / "honesty_copy_expect.json"
    era_path = REPO_ROOT / FIXTURES_REL / "era_gate_index_expect.json"
    try:
        honesty = json.loads(honesty_path.read_text(encoding="utf-8"))
        if honesty.get("live_verified") is False:
            positive += 1
        else:
            errors.append("honesty_copy_expect live_verified must be false")
        if honesty.get("four_state_max") == "TEST_VERIFIED":
            positive += 1
        era = json.loads(era_path.read_text(encoding="utf-8"))
        if era.get("all_live_verified_false"):
            positive += 1
        if era.get("gate_count") == 5:
            positive += 1
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(str(exc))
    checklist_path = REPO_ROOT / CHECKLIST_REL
    if checklist_path.is_file():
        cl_violations = validate_checklist_document(json.loads(checklist_path.read_text(encoding="utf-8")))
        if not cl_violations:
            positive += 1
        else:
            errors.extend(v.message for v in cl_violations)
    era_pack_path = REPO_ROOT / ERA_CONSOLIDATED_REL
    if era_pack_path.is_file():
        era_violations = validate_era_consolidated_pack(
            json.loads(era_pack_path.read_text(encoding="utf-8")),
        )
        if not era_violations:
            positive += 1
        else:
            errors.extend(v.message for v in era_violations)
    return positive, negative, errors


def evaluate_receipt_chain_end_link_docs(
    mode: EnvMatrixMode,
    environ: Mapping[str, str],
) -> ReceiptChainEndLinkDocsResult:
    resolved = mode
    violations: list[ReceiptChainEndLinkDocsViolation] = []

    prior = hermetic_end_link_operator_ux_check(environ)
    if not prior.ok:
        violations.append(
            ReceiptChainEndLinkDocsViolation(
                code="end_link_operator_ux_failed",
                message=f"prior gate {PRIOR_GATE_ID} must pass",
            ),
        )

    violations.extend(_check_files())
    violations.extend(_check_markers())
    violations.extend(_check_audit_index())
    violations.extend(_check_per_pr_pass_honesty())

    pos, _neg, fixture_errors = run_docs_fixture_suite()
    for err in fixture_errors:
        violations.append(ReceiptChainEndLinkDocsViolation(code="fixture_failed", message=err))

    fixture_ok = not fixture_errors and pos >= 5
    if not fixture_ok:
        violations.append(ReceiptChainEndLinkDocsViolation(code="fixture_suite_weak", message="docs fixtures weak"))

    audit_index_ok = not _check_audit_index()
    era_pack_ok = not validate_era_consolidated_pack(
        json.loads((REPO_ROOT / ERA_CONSOLIDATED_REL).read_text(encoding="utf-8")),
    ) if (REPO_ROOT / ERA_CONSOLIDATED_REL).is_file() else False
    operator_guide_ok = not _check_markers()

    ok = prior.ok and fixture_ok and not violations
    evidence = ReceiptChainEndLinkDocsEvidence(
        gate_id=GATE_ID,
        pr_number=PR_NUMBER,
        end_link_operator_ux_ok=prior.ok,
        era_pack_ok=era_pack_ok,
        audit_index_ok=audit_index_ok,
        operator_guide_ok=operator_guide_ok,
    )
    return ReceiptChainEndLinkDocsResult(
        mode=resolved,
        ok=ok,
        end_link_operator_ux_ok=prior.ok,
        violations=violations if not ok else [],
        evidence=evidence,
    )


def hermetic_receipt_chain_end_link_docs_check(
    environ: Mapping[str, str] | None = None,
) -> ReceiptChainEndLinkDocsResult:
    env: Mapping[str, str] = environ if environ is not None else os.environ
    return evaluate_receipt_chain_end_link_docs(detect_matrix_mode(env), env)


def receipt_chain_end_link_docs_gate_closed() -> bool:
    return hermetic_receipt_chain_end_link_docs_check(
        minimal_receipt_chain_end_link_docs_environ(),
    ).ok


def receipt_chain_end_link_docs_contract_summary(
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    env: Mapping[str, str] = environ if environ is not None else os.environ
    result = hermetic_receipt_chain_end_link_docs_check(env)
    return {
        "gate_id": GATE_ID,
        "pr_number": PR_NUMBER,
        "pr160_gate_id": GATE_ID,
        "pr159_layer_gate_id": PRIOR_GATE_ID,
        "receipt_chain_end_link_docs": RECEIPT_CHAIN_END_LINK_DOCS_LABEL,
        "receipt_chain_end_link_docs_version": RECEIPT_CHAIN_END_LINK_DOCS_VERSION,
        "detected_mode": detect_matrix_mode(env).value,
        "hermetic_operator_ok": result.ok,
        "end_link_operator_ux_ok": result.end_link_operator_ux_ok,
        "live_api_called": False,
        "four_state_max": "TEST_VERIFIED",
        "live_proof_in_this_pr": False,
        "live_verified": False,
        "gate_closed_default": receipt_chain_end_link_docs_gate_closed(),
        "verify_script": str(VERIFY_SCRIPT_REL),
        "verify_script_present": (REPO_ROOT / VERIFY_SCRIPT_REL).is_file(),
        "checklist_rel": str(CHECKLIST_REL),
        "era_consolidated_rel": str(ERA_CONSOLIDATED_REL),
        "operator_guide_rel": str(OPERATOR_GUIDE_REL),
        "hermetic_violation_codes": sorted({v.code for v in result.violations}),
    }
