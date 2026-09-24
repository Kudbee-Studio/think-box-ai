"""Hermetic Kudbee SDK follow-up contracts (PR #179, ``kudbee-sdk-followup``).

Validates ~25 follow-up features building on merged #177: Python package under
``thinkbox/kudbee_sdk_followup/``, TypeScript deepen under ``apps/web/sdk/``,
manifest at ``data/kudbee_sdk/pr179_features.json``.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from thinkbox.kudbee_sdk_followup.negotiation import SDK_FOLLOWUP_VERSION
from thinkbox.kilo_live_proof_readiness import REPO_ROOT

__all__ = (
    "EXPECTED_FEATURE_COUNT",
    "FEATURES_MANIFEST_REL",
    "GATE_ID",
    "PR179_PASS_REL",
    "PR_NUMBER",
    "KudbeeSdkFollowupViolation",
    "kudbee_sdk_followup_contract_summary",
    "load_features_manifest",
    "validate_features_manifest",
)

GATE_ID = "kudbee-sdk-followup"
PR_NUMBER = 179
EXPECTED_FEATURE_COUNT = 25

FEATURES_MANIFEST_REL = Path("data/kudbee_sdk/pr179_features.json")
PR179_PASS_REL = Path("docs/audit/passes/2026-09-24-pr179.json")


@dataclass(frozen=True)
class KudbeeSdkFollowupViolation:
    code: str
    message: str
    path: str | None = None


def load_features_manifest(repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root if repo_root is not None else REPO_ROOT
    return json.loads((root / FEATURES_MANIFEST_REL).read_text(encoding="utf-8"))


def validate_features_manifest(
    doc: Mapping[str, Any] | None = None,
    repo_root: Path | None = None,
) -> tuple[bool, tuple[KudbeeSdkFollowupViolation, ...]]:
    root = repo_root if repo_root is not None else REPO_ROOT
    violations: list[KudbeeSdkFollowupViolation] = []
    if doc is None:
        doc = load_features_manifest(root)

    if doc.get("gate_id") != GATE_ID:
        violations.append(KudbeeSdkFollowupViolation("gate_id", "gate_id mismatch"))
    if doc.get("pr_number") != PR_NUMBER:
        violations.append(KudbeeSdkFollowupViolation("pr_number", "pr_number mismatch"))
    if doc.get("live_verified") is True:
        violations.append(KudbeeSdkFollowupViolation("live_verified", "must be false"))
    features = list(doc.get("features") or [])
    if len(features) != EXPECTED_FEATURE_COUNT:
        violations.append(
            KudbeeSdkFollowupViolation(
                "feature_count",
                f"expected {EXPECTED_FEATURE_COUNT} features",
            ),
        )
    seen_ids: set[str] = set()
    for feat in features:
        fid = str(feat.get("id", ""))
        if fid in seen_ids:
            violations.append(KudbeeSdkFollowupViolation("duplicate_feature_id", fid))
        seen_ids.add(fid)
        rel = feat.get("module")
        if not rel or not (root / str(rel)).is_file():
            violations.append(
                KudbeeSdkFollowupViolation(
                    "feature_module_missing",
                    f"missing module for {fid}",
                    path=str(rel),
                ),
            )

    quickstart = root / "docs/guides/kudbee_sdk_quickstart.md"
    if not quickstart.is_file():
        violations.append(KudbeeSdkFollowupViolation("quickstart_doc", "missing quickstart guide"))

    example = root / "examples/kudbee_sdk_followup_quickstart.py"
    if not example.is_file():
        violations.append(KudbeeSdkFollowupViolation("quickstart_example", "missing example"))

    status_mod = root / "thinkbox/kudbee_sdk_followup/sdk_status_report.py"
    if not status_mod.is_file():
        violations.append(KudbeeSdkFollowupViolation("sdk_status", "missing sdk status module"))

    return (len(violations) == 0, tuple(violations))


def kudbee_sdk_followup_contract_summary(repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root if repo_root is not None else REPO_ROOT
    ok, violations = validate_features_manifest(repo_root=root)
    return {
        "gate_id": GATE_ID,
        "pr_number": PR_NUMBER,
        "pr179_gate_id": GATE_ID,
        "hermetic_operator_ok": ok,
        "live_verified": False,
        "live_api_called": False,
        "four_state_max": "TEST_VERIFIED",
        "combined_umbrella_nested": False,
        "feature_count": EXPECTED_FEATURE_COUNT,
        "sdk_followup_version": SDK_FOLLOWUP_VERSION,
        "primary_surface": "thinkbox/kudbee_sdk_followup + apps/web/sdk",
        "features_manifest_rel": str(FEATURES_MANIFEST_REL),
        "violation_count": len(violations),
        "violation_codes": [v.code for v in violations],
    }
