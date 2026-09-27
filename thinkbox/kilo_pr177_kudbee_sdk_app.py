"""Hermetic Kudbee SDK app contracts (PR #177, ``kudbee-sdk-app``).

Validates ~25 SDK features for the kudbEE web shell: Python package under
``thinkbox/kudbee_sdk/``, TypeScript surface under ``apps/web/sdk/``, manifest
at ``data/kudbee_sdk/pr177_features.json``.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from thinkbox.kudbee_sdk.negotiation import SDK_VERSION
from thinkbox.kilo_live_proof_readiness import REPO_ROOT

__all__ = (
    "EXPECTED_FEATURE_COUNT",
    "FEATURES_MANIFEST_REL",
    "GATE_ID",
    "PR177_PASS_REL",
    "PR_NUMBER",
    "KudbeeSdkAppViolation",
    "kudbee_sdk_app_contract_summary",
    "load_features_manifest",
    "validate_features_manifest",
)

GATE_ID = "kudbee-sdk-app"
PR_NUMBER = 177
EXPECTED_FEATURE_COUNT = 25

FEATURES_MANIFEST_REL = Path("data/kudbee_sdk/pr177_features.json")
PR177_PASS_REL = Path("docs/audit/passes/2026-09-24-pr177.json")


@dataclass(frozen=True)
class KudbeeSdkAppViolation:
    code: str
    message: str
    path: str | None = None


def load_features_manifest(repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root if repo_root is not None else REPO_ROOT
    return json.loads((root / FEATURES_MANIFEST_REL).read_text(encoding="utf-8"))


def validate_features_manifest(
    doc: Mapping[str, Any] | None = None,
    repo_root: Path | None = None,
) -> tuple[bool, tuple[KudbeeSdkAppViolation, ...]]:
    root = repo_root if repo_root is not None else REPO_ROOT
    violations: list[KudbeeSdkAppViolation] = []
    if doc is None:
        doc = load_features_manifest(root)

    if doc.get("gate_id") != GATE_ID:
        violations.append(KudbeeSdkAppViolation("gate_id", "gate_id mismatch"))
    if doc.get("pr_number") != PR_NUMBER:
        violations.append(KudbeeSdkAppViolation("pr_number", "pr_number mismatch"))
    if doc.get("live_verified") is True:
        violations.append(KudbeeSdkAppViolation("live_verified", "must be false"))
    features = list(doc.get("features") or [])
    if len(features) != EXPECTED_FEATURE_COUNT:
        violations.append(
            KudbeeSdkAppViolation(
                "feature_count",
                f"expected {EXPECTED_FEATURE_COUNT} features",
            ),
        )
    seen_ids: set[str] = set()
    for feat in features:
        fid = str(feat.get("id", ""))
        if fid in seen_ids:
            violations.append(KudbeeSdkAppViolation("duplicate_feature_id", fid))
        seen_ids.add(fid)
        rel = feat.get("module")
        if not rel or not (root / str(rel)).is_file():
            violations.append(
                KudbeeSdkAppViolation(
                    "feature_module_missing",
                    f"missing module for {fid}",
                    path=str(rel),
                ),
            )

    sdk_init = root / "thinkbox/kudbee_sdk/__init__.py"
    if not sdk_init.is_file():
        violations.append(KudbeeSdkAppViolation("sdk_init", "kudbee_sdk package missing"))

    quickstart = root / "docs/guides/kudbee_sdk_quickstart.md"
    if not quickstart.is_file():
        violations.append(KudbeeSdkAppViolation("quickstart_doc", "missing quickstart guide"))

    example = root / "examples/kudbee_sdk_quickstart.py"
    if not example.is_file():
        violations.append(KudbeeSdkAppViolation("quickstart_example", "missing example"))

    return (len(violations) == 0, tuple(violations))


def kudbee_sdk_app_contract_summary(repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root if repo_root is not None else REPO_ROOT
    ok, violations = validate_features_manifest(repo_root=root)
    return {
        "gate_id": GATE_ID,
        "pr_number": PR_NUMBER,
        "pr177_gate_id": GATE_ID,
        "hermetic_operator_ok": ok,
        "live_verified": False,
        "live_api_called": False,
        "four_state_max": "TEST_VERIFIED",
        "combined_umbrella_nested": False,
        "feature_count": EXPECTED_FEATURE_COUNT,
        "sdk_version": SDK_VERSION,
        "primary_surface": "thinkbox/kudbee_sdk + apps/web/sdk",
        "features_manifest_rel": str(FEATURES_MANIFEST_REL),
        "violation_count": len(violations),
        "violation_codes": [v.code for v in violations],
    }
