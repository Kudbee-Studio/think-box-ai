"""Hermetic Think Job POST /run contract deepen (PR #184, ``think-job-post-run-deepen``)."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from thinkbox.kilo_live_proof_readiness import REPO_ROOT
from thinkbox.think_job_post_run_deepen.negotiation import THINK_JOB_POST_RUN_DEEPEN_VERSION

__all__ = (
    "EXPECTED_FEATURE_COUNT",
    "EXPECTED_ENHANCEMENT_COUNT",
    "EXPECTED_FIX_COUNT",
    "ENHANCEMENTS_MANIFEST_REL",
    "FEATURES_MANIFEST_REL",
    "FIXES_MANIFEST_REL",
    "GATE_ID",
    "PR184_PASS_REL",
    "PR_NUMBER",
    "ThinkJobPostRunDeepenViolation",
    "load_features_manifest",
    "load_enhancements_manifest",
    "load_fixes_manifest",
    "think_job_post_run_deepen_contract_summary",
    "validate_enhancements_manifest",
    "validate_features_manifest",
    "validate_fixes_manifest",
)

GATE_ID = "think-job-post-run-deepen"
PR_NUMBER = 184
EXPECTED_FEATURE_COUNT = 25
EXPECTED_FIX_COUNT = 10
EXPECTED_ENHANCEMENT_COUNT = 10

FEATURES_MANIFEST_REL = Path("data/think_job_post_run/pr184_features.json")
FIXES_MANIFEST_REL = Path("data/think_job_post_run/pr184_fixes.json")
ENHANCEMENTS_MANIFEST_REL = Path("data/think_job_post_run/pr184_enhancements.json")
PR184_PASS_REL = Path("docs/audit/passes/2026-09-24-pr184.json")


@dataclass(frozen=True)
class ThinkJobPostRunDeepenViolation:
    code: str
    message: str
    path: str | None = None


def load_features_manifest(repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root if repo_root is not None else REPO_ROOT
    return json.loads((root / FEATURES_MANIFEST_REL).read_text(encoding="utf-8"))


def load_fixes_manifest(repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root if repo_root is not None else REPO_ROOT
    return json.loads((root / FIXES_MANIFEST_REL).read_text(encoding="utf-8"))


def load_enhancements_manifest(repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root if repo_root is not None else REPO_ROOT
    return json.loads((root / ENHANCEMENTS_MANIFEST_REL).read_text(encoding="utf-8"))


def validate_features_manifest(
    doc: Mapping[str, Any] | None = None,
    repo_root: Path | None = None,
) -> tuple[bool, tuple[ThinkJobPostRunDeepenViolation, ...]]:
    root = repo_root if repo_root is not None else REPO_ROOT
    violations: list[ThinkJobPostRunDeepenViolation] = []
    if doc is None:
        doc = load_features_manifest(root)

    if doc.get("gate_id") != GATE_ID:
        violations.append(ThinkJobPostRunDeepenViolation("gate_id", "gate_id mismatch"))
    if doc.get("pr_number") != PR_NUMBER:
        violations.append(ThinkJobPostRunDeepenViolation("pr_number", "pr_number mismatch"))
    if doc.get("live_verified") is True:
        violations.append(ThinkJobPostRunDeepenViolation("live_verified", "must be false"))
    features = list(doc.get("features") or [])
    if len(features) != EXPECTED_FEATURE_COUNT:
        violations.append(
            ThinkJobPostRunDeepenViolation("feature_count", f"expected {EXPECTED_FEATURE_COUNT} features"),
        )
    seen: set[str] = set()
    for feat in features:
        fid = str(feat.get("id", ""))
        if fid in seen:
            violations.append(ThinkJobPostRunDeepenViolation("duplicate_feature_id", fid))
        seen.add(fid)
        rel = feat.get("module")
        if not rel or not (root / str(rel)).is_file():
            violations.append(
                ThinkJobPostRunDeepenViolation("feature_module_missing", f"missing {fid}", path=str(rel)),
            )

    quickstart = root / "docs/guides/think_job_post_run_deepen_quickstart.md"
    if not quickstart.is_file():
        violations.append(ThinkJobPostRunDeepenViolation("quickstart_doc", "missing quickstart"))

    example = root / "examples/think_job_post_run_deepen_quickstart.py"
    if not example.is_file():
        violations.append(ThinkJobPostRunDeepenViolation("quickstart_example", "missing example"))

    cassette = root / "data/think_job_post_run/cassettes/post_run_flow.json"
    if not cassette.is_file():
        violations.append(ThinkJobPostRunDeepenViolation("cassette_fixture", "missing cassette"))

    checklist = root / "data/think_job_post_run/pr184_checklist.json"
    if not checklist.is_file():
        violations.append(ThinkJobPostRunDeepenViolation("checklist", "missing pr184 checklist"))

    return (len(violations) == 0, tuple(violations))


def validate_fixes_manifest(
    doc: Mapping[str, Any] | None = None,
    repo_root: Path | None = None,
) -> tuple[bool, tuple[ThinkJobPostRunDeepenViolation, ...]]:
    root = repo_root if repo_root is not None else REPO_ROOT
    violations: list[ThinkJobPostRunDeepenViolation] = []
    if doc is None:
        doc = load_fixes_manifest(root)
    if doc.get("gate_id") != GATE_ID:
        violations.append(ThinkJobPostRunDeepenViolation("fixes_gate_id", "gate_id mismatch"))
    fixes = list(doc.get("fixes") or [])
    if len(fixes) != EXPECTED_FIX_COUNT:
        violations.append(ThinkJobPostRunDeepenViolation("fix_count", "fix count mismatch"))
    for fix in fixes:
        rel = fix.get("module")
        if not rel or not (root / str(rel)).is_file():
            violations.append(ThinkJobPostRunDeepenViolation("fix_module_missing", str(rel)))
    return (len(violations) == 0, tuple(violations))


def validate_enhancements_manifest(
    doc: Mapping[str, Any] | None = None,
    repo_root: Path | None = None,
) -> tuple[bool, tuple[ThinkJobPostRunDeepenViolation, ...]]:
    root = repo_root if repo_root is not None else REPO_ROOT
    violations: list[ThinkJobPostRunDeepenViolation] = []
    if doc is None:
        doc = load_enhancements_manifest(root)
    items = list(doc.get("enhancements") or [])
    if len(items) != EXPECTED_ENHANCEMENT_COUNT:
        violations.append(ThinkJobPostRunDeepenViolation("enhancement_count", "enhancement count mismatch"))
    for item in items:
        rel = item.get("module")
        if not rel or not (root / str(rel)).is_file():
            violations.append(ThinkJobPostRunDeepenViolation("enhancement_module_missing", str(rel)))
    return (len(violations) == 0, tuple(violations))


def think_job_post_run_deepen_contract_summary(repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root if repo_root is not None else REPO_ROOT
    features_ok, feature_violations = validate_features_manifest(repo_root=root)
    fixes_ok, fix_violations = validate_fixes_manifest(repo_root=root)
    enhancements_ok, enhancement_violations = validate_enhancements_manifest(repo_root=root)
    ok = features_ok and fixes_ok and enhancements_ok
    violations = (*feature_violations, *fix_violations, *enhancement_violations)
    return {
        "gate_id": GATE_ID,
        "pr_number": PR_NUMBER,
        "pr184_gate_id": GATE_ID,
        "hermetic_operator_ok": ok,
        "live_verified": False,
        "live_api_called": False,
        "four_state_max": "TEST_VERIFIED",
        "combined_umbrella_nested": False,
        "feature_count": EXPECTED_FEATURE_COUNT,
        "fix_count": EXPECTED_FIX_COUNT,
        "fixes_manifest_ok": fixes_ok,
        "enhancement_count": EXPECTED_ENHANCEMENT_COUNT,
        "enhancements_manifest_ok": enhancements_ok,
        "think_job_post_run_deepen_version": THINK_JOB_POST_RUN_DEEPEN_VERSION,
        "primary_surface": "thinkbox/think_job_post_run_deepen + POST /api/v1/run (F131)",
        "features_manifest_rel": str(FEATURES_MANIFEST_REL),
        "fixes_manifest_rel": str(FIXES_MANIFEST_REL),
        "enhancements_manifest_rel": str(ENHANCEMENTS_MANIFEST_REL),
        "violation_count": len(violations),
        "violation_codes": [v.code for v in violations],
    }
