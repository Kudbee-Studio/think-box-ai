"""Hermetic Kudbee SDK follow-up wave 3 major fixes (PR #192, ``kudbee-sdk-followup-w3-major-fixes``)."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from thinkbox.kilo_live_proof_readiness import REPO_ROOT
from thinkbox.kudbee_sdk_followup_w3_major_fixes.negotiation import KUDBEE_SDK_FOLLOWUP_W3_MAJOR_FIXES_VERSION

__all__ = (
    "EXPECTED_FIX_COUNT",
    "FIXES_MANIFEST_REL",
    "GATE_ID",
    "PR192_PASS_REL",
    "PR_NUMBER",
    "KudbeeSdkFollowupW3MajorFixViolation",
    "kudbee_sdk_followup_w3_major_fixes_contract_summary",
    "load_fixes_manifest",
    "validate_fixes_manifest",
)

GATE_ID = "kudbee-sdk-followup-w3-major-fixes"
PR_NUMBER = 192
EXPECTED_FIX_COUNT = 35

FIXES_MANIFEST_REL = Path("data/kudbee_sdk_followup_w3_major/pr192_fixes.json")
PR192_PASS_REL = Path("docs/audit/passes/2026-09-24-pr192.json")


@dataclass(frozen=True)
class KudbeeSdkFollowupW3MajorFixViolation:
    code: str
    message: str
    path: str | None = None


def load_fixes_manifest(repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root if repo_root is not None else REPO_ROOT
    return json.loads((root / FIXES_MANIFEST_REL).read_text(encoding="utf-8"))


def validate_fixes_manifest(
    doc: Mapping[str, Any] | None = None,
    repo_root: Path | None = None,
) -> tuple[bool, tuple[KudbeeSdkFollowupW3MajorFixViolation, ...]]:
    root = repo_root if repo_root is not None else REPO_ROOT
    violations: list[KudbeeSdkFollowupW3MajorFixViolation] = []
    if doc is None:
        doc = load_fixes_manifest(root)

    if doc.get("gate_id") != GATE_ID:
        violations.append(KudbeeSdkFollowupW3MajorFixViolation("gate_id", "gate_id mismatch"))
    if doc.get("pr_number") != PR_NUMBER:
        violations.append(KudbeeSdkFollowupW3MajorFixViolation("pr_number", "pr_number mismatch"))
    if doc.get("live_verified") is True:
        violations.append(KudbeeSdkFollowupW3MajorFixViolation("live_verified", "must be false"))
    fixes = list(doc.get("fixes") or [])
    if len(fixes) != EXPECTED_FIX_COUNT:
        violations.append(KudbeeSdkFollowupW3MajorFixViolation("fix_count", "fix count mismatch"))
    seen: set[str] = set()
    for fix in fixes:
        fid = str(fix.get("id", ""))
        if fid in seen:
            violations.append(KudbeeSdkFollowupW3MajorFixViolation("duplicate_fix_id", fid))
        seen.add(fid)
        rel = fix.get("module")
        if not rel or not (root / str(rel)).is_file():
            violations.append(
                KudbeeSdkFollowupW3MajorFixViolation("fix_module_missing", str(rel), path=str(rel)),
            )

    checklist = root / "data/kudbee_sdk_followup_w3_major/pr192_checklist.json"
    if not checklist.is_file():
        violations.append(KudbeeSdkFollowupW3MajorFixViolation("checklist", "missing pr192 checklist"))

    quickstart = root / "docs/guides/kudbee_sdk_followup_w3_major_fixes_quickstart.md"
    if not quickstart.is_file():
        violations.append(KudbeeSdkFollowupW3MajorFixViolation("quickstart_doc", "missing quickstart"))

    audit = root / PR192_PASS_REL
    if not audit.is_file():
        violations.append(KudbeeSdkFollowupW3MajorFixViolation("audit_pass", "missing audit pass"))

    cassette = root / "data/kudbee_sdk_followup_w3_major/cassettes/w3_major_flow.json"
    if not cassette.is_file():
        violations.append(KudbeeSdkFollowupW3MajorFixViolation("cassette", "missing w3 major cassette"))

    from thinkbox import kilo_pr191_kudbee_sdk_followup_w3 as pr191

    features_ok, _ = pr191.validate_features_manifest(repo_root=root)
    if not features_ok:
        violations.append(KudbeeSdkFollowupW3MajorFixViolation("pr191_features", "pr191 features invalid"))

    return (len(violations) == 0, tuple(violations))


def kudbee_sdk_followup_w3_major_fixes_contract_summary(repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root if repo_root is not None else REPO_ROOT
    fixes_ok, violations = validate_fixes_manifest(repo_root=root)
    return {
        "gate_id": GATE_ID,
        "pr_number": PR_NUMBER,
        "pr192_gate_id": GATE_ID,
        "hermetic_operator_ok": fixes_ok,
        "live_verified": False,
        "live_api_called": False,
        "four_state_max": "TEST_VERIFIED",
        "combined_umbrella_nested": False,
        "fix_count": EXPECTED_FIX_COUNT,
        "fixes_manifest_ok": fixes_ok,
        "kudbee_sdk_followup_w3_major_fixes_version": KUDBEE_SDK_FOLLOWUP_W3_MAJOR_FIXES_VERSION,
        "primary_surface": "thinkbox/kudbee_sdk_followup_w3_major_fixes + wave 3 SDK (#191)",
        "fixes_manifest_rel": str(FIXES_MANIFEST_REL),
        "violation_count": len(violations),
        "violation_codes": [v.code for v in violations],
        "upstream_pr": 191,
    }
