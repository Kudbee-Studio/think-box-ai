"""Hermetic KUDBEECLI Phase 3 contracts (PR #180, ``kudbee-cli-phase3``).

Validates ~25 CLI deepen features under ``thinkbox/cli_phase3/`` and manifest
at ``data/kudbee_cli/pr180_features.json``.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from thinkbox.cli_phase3.negotiation import CLI_PHASE3_VERSION
from thinkbox.kilo_live_proof_readiness import REPO_ROOT

__all__ = (
    "EXPECTED_FEATURE_COUNT",
    "FEATURES_MANIFEST_REL",
    "GATE_ID",
    "PR180_PASS_REL",
    "PR_NUMBER",
    "KudbeeCliPhase3Violation",
    "kudbee_cli_phase3_contract_summary",
    "load_features_manifest",
    "validate_features_manifest",
)

GATE_ID = "kudbee-cli-phase3"
PR_NUMBER = 180
EXPECTED_FEATURE_COUNT = 25

FEATURES_MANIFEST_REL = Path("data/kudbee_cli/pr180_features.json")
PR180_PASS_REL = Path("docs/audit/passes/2026-09-24-pr180.json")


@dataclass(frozen=True)
class KudbeeCliPhase3Violation:
    code: str
    message: str
    path: str | None = None


def load_features_manifest(repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root if repo_root is not None else REPO_ROOT
    return json.loads((root / FEATURES_MANIFEST_REL).read_text(encoding="utf-8"))


def validate_features_manifest(
    doc: Mapping[str, Any] | None = None,
    repo_root: Path | None = None,
) -> tuple[bool, tuple[KudbeeCliPhase3Violation, ...]]:
    root = repo_root if repo_root is not None else REPO_ROOT
    violations: list[KudbeeCliPhase3Violation] = []
    if doc is None:
        doc = load_features_manifest(root)

    if doc.get("gate_id") != GATE_ID:
        violations.append(KudbeeCliPhase3Violation("gate_id", "gate_id mismatch"))
    if doc.get("pr_number") != PR_NUMBER:
        violations.append(KudbeeCliPhase3Violation("pr_number", "pr_number mismatch"))
    if doc.get("live_verified") is True:
        violations.append(KudbeeCliPhase3Violation("live_verified", "must be false"))
    features = list(doc.get("features") or [])
    if len(features) != EXPECTED_FEATURE_COUNT:
        violations.append(
            KudbeeCliPhase3Violation(
                "feature_count",
                f"expected {EXPECTED_FEATURE_COUNT} features",
            ),
        )
    seen_ids: set[str] = set()
    for feat in features:
        fid = str(feat.get("id", ""))
        if fid in seen_ids:
            violations.append(KudbeeCliPhase3Violation("duplicate_feature_id", fid))
        seen_ids.add(fid)
        rel = feat.get("module")
        if not rel or not (root / str(rel)).is_file():
            violations.append(
                KudbeeCliPhase3Violation(
                    "feature_module_missing",
                    f"missing module for {fid}",
                    path=str(rel),
                ),
            )

    quickstart = root / "docs/guides/kudbee_cli_phase3_quickstart.md"
    if not quickstart.is_file():
        violations.append(KudbeeCliPhase3Violation("quickstart_doc", "missing quickstart guide"))

    example = root / "examples/kudbee_cli_phase3_quickstart.py"
    if not example.is_file():
        violations.append(KudbeeCliPhase3Violation("quickstart_example", "missing example"))

    cassette = root / "data/cli_phase3/cassettes/health_flow.json"
    if not cassette.is_file():
        violations.append(KudbeeCliPhase3Violation("cassette_fixture", "missing default cassette"))

    return (len(violations) == 0, tuple(violations))


def kudbee_cli_phase3_contract_summary(repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root if repo_root is not None else REPO_ROOT
    ok, violations = validate_features_manifest(repo_root=root)
    return {
        "gate_id": GATE_ID,
        "pr_number": PR_NUMBER,
        "pr180_gate_id": GATE_ID,
        "hermetic_operator_ok": ok,
        "live_verified": False,
        "live_api_called": False,
        "four_state_max": "TEST_VERIFIED",
        "combined_umbrella_nested": False,
        "feature_count": EXPECTED_FEATURE_COUNT,
        "cli_phase3_version": CLI_PHASE3_VERSION,
        "primary_surface": "thinkbox/cli.py + thinkbox/cli_phase3",
        "features_manifest_rel": str(FEATURES_MANIFEST_REL),
        "violation_count": len(violations),
        "violation_codes": [v.code for v in violations],
    }
