"""Hermetic Think Job e2e deepen contracts (PR #183, ``think-job-hermetic-e2e``).

Validates ~25 deepen features under ``thinkbox/think_job_e2e_deepen/`` and manifest
at ``data/think_job/pr183_features.json``.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from thinkbox.kilo_live_proof_readiness import REPO_ROOT
from thinkbox.think_job_e2e_deepen.negotiation import THINK_JOB_E2E_DEEPEN_VERSION

__all__ = (
    "EXPECTED_FEATURE_COUNT",
    "FEATURES_MANIFEST_REL",
    "GATE_ID",
    "PR183_PASS_REL",
    "PR_NUMBER",
    "ThinkJobHermeticE2eViolation",
    "load_features_manifest",
    "think_job_hermetic_e2e_contract_summary",
    "validate_features_manifest",
)

GATE_ID = "think-job-hermetic-e2e"
PR_NUMBER = 183
EXPECTED_FEATURE_COUNT = 25

FEATURES_MANIFEST_REL = Path("data/think_job/pr183_features.json")
PR183_PASS_REL = Path("docs/audit/passes/2026-09-24-pr183.json")


@dataclass(frozen=True)
class ThinkJobHermeticE2eViolation:
    code: str
    message: str
    path: str | None = None


def load_features_manifest(repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root if repo_root is not None else REPO_ROOT
    return json.loads((root / FEATURES_MANIFEST_REL).read_text(encoding="utf-8"))


def validate_features_manifest(
    doc: Mapping[str, Any] | None = None,
    repo_root: Path | None = None,
) -> tuple[bool, tuple[ThinkJobHermeticE2eViolation, ...]]:
    root = repo_root if repo_root is not None else REPO_ROOT
    violations: list[ThinkJobHermeticE2eViolation] = []
    if doc is None:
        doc = load_features_manifest(root)

    if doc.get("gate_id") != GATE_ID:
        violations.append(ThinkJobHermeticE2eViolation("gate_id", "gate_id mismatch"))
    if doc.get("pr_number") != PR_NUMBER:
        violations.append(ThinkJobHermeticE2eViolation("pr_number", "pr_number mismatch"))
    if doc.get("live_verified") is True:
        violations.append(ThinkJobHermeticE2eViolation("live_verified", "must be false"))
    features = list(doc.get("features") or [])
    if len(features) != EXPECTED_FEATURE_COUNT:
        violations.append(
            ThinkJobHermeticE2eViolation(
                "feature_count",
                f"expected {EXPECTED_FEATURE_COUNT} features",
            ),
        )
    seen_ids: set[str] = set()
    for feat in features:
        fid = str(feat.get("id", ""))
        if fid in seen_ids:
            violations.append(ThinkJobHermeticE2eViolation("duplicate_feature_id", fid))
        seen_ids.add(fid)
        rel = feat.get("module")
        if not rel or not (root / str(rel)).is_file():
            violations.append(
                ThinkJobHermeticE2eViolation(
                    "feature_module_missing",
                    f"missing module for {fid}",
                    path=str(rel),
                ),
            )

    quickstart = root / "docs/guides/think_job_hermetic_e2e_quickstart.md"
    if not quickstart.is_file():
        violations.append(ThinkJobHermeticE2eViolation("quickstart_doc", "missing quickstart guide"))

    example = root / "examples/think_job_hermetic_e2e_quickstart.py"
    if not example.is_file():
        violations.append(ThinkJobHermeticE2eViolation("quickstart_example", "missing example"))

    status_mod = root / "thinkbox/think_job_e2e_deepen/deepen_status_report.py"
    if not status_mod.is_file():
        violations.append(ThinkJobHermeticE2eViolation("status_report", "missing status module"))

    cassette = root / "data/think_job/cassettes/job_lifecycle_flow.json"
    if not cassette.is_file():
        violations.append(ThinkJobHermeticE2eViolation("cassette_fixture", "missing default cassette"))

    return (len(violations) == 0, tuple(violations))


def think_job_hermetic_e2e_contract_summary(repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root if repo_root is not None else REPO_ROOT
    ok, violations = validate_features_manifest(repo_root=root)
    return {
        "gate_id": GATE_ID,
        "pr_number": PR_NUMBER,
        "pr183_gate_id": GATE_ID,
        "hermetic_operator_ok": ok,
        "live_verified": False,
        "live_api_called": False,
        "four_state_max": "TEST_VERIFIED",
        "combined_umbrella_nested": False,
        "feature_count": EXPECTED_FEATURE_COUNT,
        "think_job_e2e_deepen_version": THINK_JOB_E2E_DEEPEN_VERSION,
        "primary_surface": "thinkbox/think_job_e2e_deepen + think_job_status/stream bridges",
        "features_manifest_rel": str(FEATURES_MANIFEST_REL),
        "violation_count": len(violations),
        "violation_codes": [v.code for v in violations],
    }
