"""Hermetic Upstash Box access-verification contracts (PR #201)."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from thinkbox.kilo_live_proof_readiness import REPO_ROOT

__all__ = (
    "EXPECTED_FEATURE_COUNT",
    "FEATURES_MANIFEST_REL",
    "GATE_ID",
    "PR201_PASS_REL",
    "PR_NUMBER",
    "THIS_RUN_EVIDENCE_REL",
    "UpstashBoxAccessViolation",
    "load_features_manifest",
    "upstash_box_access_contract_summary",
    "validate_features_manifest",
)

GATE_ID = "upstash-box-access-verification"
PR_NUMBER = 201
EXPECTED_FEATURE_COUNT = 5

FEATURES_MANIFEST_REL = Path("data/upstash_box_access/pr201_features.json")
PR201_PASS_REL = Path("docs/audit/passes/2026-09-24-pr201.json")
THIS_RUN_EVIDENCE_REL = Path("data/upstash_box_access/probe_20260924_pr201.json")
ADR_REL = Path("docs/decisions/024-upstash-box-access-verification.md")
GUIDE_REL = Path("docs/guides/upstash_box_access_verification.md")


@dataclass(frozen=True)
class UpstashBoxAccessViolation:
    code: str
    message: str
    path: str | None = None


def load_features_manifest(repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root if repo_root is not None else REPO_ROOT
    return json.loads((root / FEATURES_MANIFEST_REL).read_text(encoding="utf-8"))


def validate_features_manifest(
    doc: Mapping[str, Any] | None = None,
    repo_root: Path | None = None,
) -> tuple[bool, tuple[UpstashBoxAccessViolation, ...]]:
    root = repo_root if repo_root is not None else REPO_ROOT
    violations: list[UpstashBoxAccessViolation] = []
    if doc is None:
        if not (root / FEATURES_MANIFEST_REL).is_file():
            violations.append(UpstashBoxAccessViolation("features_manifest", "missing manifest"))
            return (False, tuple(violations))
        doc = load_features_manifest(root)

    if doc.get("gate_id") != GATE_ID:
        violations.append(UpstashBoxAccessViolation("gate_id", "gate_id mismatch"))
    if doc.get("pr_number") != PR_NUMBER:
        violations.append(UpstashBoxAccessViolation("pr_number", "pr_number mismatch"))
    if doc.get("live_verified") is True:
        violations.append(UpstashBoxAccessViolation("live_verified", "must be false"))
    if doc.get("live_api_called") is True:
        violations.append(UpstashBoxAccessViolation("live_api_called", "must be false"))
    if doc.get("this_run_classification") != "A":
        violations.append(
            UpstashBoxAccessViolation(
                "this_run_classification",
                "committed this-run evidence must remain A until a real Box execution exists",
            ),
        )

    features = list(doc.get("features") or [])
    if len(features) != EXPECTED_FEATURE_COUNT:
        violations.append(UpstashBoxAccessViolation("feature_count", "feature count mismatch"))
    for feat in features:
        rel = feat.get("module")
        if not rel or not (root / str(rel)).is_file():
            violations.append(
                UpstashBoxAccessViolation("feature_module_missing", str(rel), path=str(rel)),
            )

    if not (root / ADR_REL).is_file():
        violations.append(UpstashBoxAccessViolation("adr", "missing ADR 024"))
    if not (root / GUIDE_REL).is_file():
        violations.append(UpstashBoxAccessViolation("guide", "missing access guide"))
    if not (root / THIS_RUN_EVIDENCE_REL).is_file():
        violations.append(UpstashBoxAccessViolation("this_run_evidence", "missing probe artifact"))
    else:
        evidence = json.loads((root / THIS_RUN_EVIDENCE_REL).read_text(encoding="utf-8"))
        if evidence.get("live_verified") is True:
            violations.append(UpstashBoxAccessViolation("evidence_live_verified", "must be false"))
        if evidence.get("live_api_called") is True:
            violations.append(UpstashBoxAccessViolation("evidence_live_api_called", "must be false"))
        if evidence.get("classification") != "A":
            violations.append(
                UpstashBoxAccessViolation(
                    "evidence_classification",
                    "this-run artifact must stay A while required Box env is absent",
                ),
            )
        if evidence.get("http_called") is True:
            violations.append(
                UpstashBoxAccessViolation(
                    "evidence_http_called",
                    "this-run artifact must not claim HTTP when env is absent",
                ),
            )

    if not (root / PR201_PASS_REL).is_file():
        violations.append(UpstashBoxAccessViolation("audit_pass", "missing audit pass"))
    else:
        pass_doc = json.loads((root / PR201_PASS_REL).read_text(encoding="utf-8"))
        if pass_doc.get("live_verified") is True or pass_doc.get("live_api_called") is True:
            violations.append(UpstashBoxAccessViolation("audit_honesty", "audit pass over-claimed live"))

    from thinkbox import kilo_pr200_environmental_variables as pr200

    if not pr200.validate_features_manifest(repo_root=root)[0]:
        violations.append(UpstashBoxAccessViolation("pr200_upstream", "pr200 invalid"))

    return (len(violations) == 0, tuple(violations))


def upstash_box_access_contract_summary(repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root if repo_root is not None else REPO_ROOT
    ok, violations = validate_features_manifest(repo_root=root)
    return {
        "gate_id": GATE_ID,
        "pr_number": PR_NUMBER,
        "hermetic_operator_ok": ok,
        "live_verified": False,
        "live_api_called": False,
        "four_state_max": "TEST_VERIFIED",
        "feature_count": EXPECTED_FEATURE_COUNT,
        "upstream_pr": 200,
        "primary_surface": "thinkbox/upstash_box_access",
        "this_run_classification": "A",
        "violation_count": len(violations),
        "violation_codes": [v.code for v in violations],
    }
