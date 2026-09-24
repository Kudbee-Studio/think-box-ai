"""Hermetic KUDBEECLI Phase 2 contracts (PR #178, ``kudbee-cli-phase2``).

Validates ~25 CLI deepen features under ``thinkbox/cli_phase2/`` and manifest
at ``data/kudbee_cli/pr178_features.json``.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from thinkbox.cli_phase2.negotiation import CLI_PHASE2_VERSION
from thinkbox.kilo_live_proof_readiness import REPO_ROOT

__all__ = (
    "EXPECTED_FEATURE_COUNT",
    "FEATURES_MANIFEST_REL",
    "GATE_ID",
    "PR178_PASS_REL",
    "PR_NUMBER",
    "KudbeeCliPhase2Violation",
    "kudbee_cli_phase2_contract_summary",
    "load_features_manifest",
    "validate_features_manifest",
)

GATE_ID = "kudbee-cli-phase2"
PR_NUMBER = 178
EXPECTED_FEATURE_COUNT = 25

FEATURES_MANIFEST_REL = Path("data/kudbee_cli/pr178_features.json")
PR178_PASS_REL = Path("docs/audit/passes/2026-09-24-pr178.json")


@dataclass(frozen=True)
class KudbeeCliPhase2Violation:
    code: str
    message: str
    path: str | None = None


def load_features_manifest(repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root if repo_root is not None else REPO_ROOT
    return json.loads((root / FEATURES_MANIFEST_REL).read_text(encoding="utf-8"))


def validate_features_manifest(
    doc: Mapping[str, Any] | None = None,
    repo_root: Path | None = None,
) -> tuple[bool, tuple[KudbeeCliPhase2Violation, ...]]:
    root = repo_root if repo_root is not None else REPO_ROOT
    violations: list[KudbeeCliPhase2Violation] = []
    if doc is None:
        doc = load_features_manifest(root)

    if doc.get("gate_id") != GATE_ID:
        violations.append(KudbeeCliPhase2Violation("gate_id", "gate_id mismatch"))
    if doc.get("pr_number") != PR_NUMBER:
        violations.append(KudbeeCliPhase2Violation("pr_number", "pr_number mismatch"))
    if doc.get("live_verified") is True:
        violations.append(KudbeeCliPhase2Violation("live_verified", "must be false"))
    features = list(doc.get("features") or [])
    if len(features) != EXPECTED_FEATURE_COUNT:
        violations.append(
            KudbeeCliPhase2Violation(
                "feature_count",
                f"expected {EXPECTED_FEATURE_COUNT} features",
            ),
        )
    seen_ids: set[str] = set()
    for feat in features:
        fid = str(feat.get("id", ""))
        if fid in seen_ids:
            violations.append(KudbeeCliPhase2Violation("duplicate_feature_id", fid))
        seen_ids.add(fid)
        rel = feat.get("module")
        if not rel or not (root / str(rel)).is_file():
            violations.append(
                KudbeeCliPhase2Violation(
                    "feature_module_missing",
                    f"missing module for {fid}",
                    path=str(rel),
                ),
            )

    quickstart = root / "docs/guides/kudbee_cli_phase2_quickstart.md"
    if not quickstart.is_file():
        violations.append(KudbeeCliPhase2Violation("quickstart_doc", "missing quickstart guide"))

    example = root / "examples/kudbee_cli_phase2_quickstart.py"
    if not example.is_file():
        violations.append(KudbeeCliPhase2Violation("quickstart_example", "missing example"))

    integrate = root / "thinkbox/cli_phase2/integrate.py"
    if not integrate.is_file():
        violations.append(KudbeeCliPhase2Violation("integrate", "missing CLI integrate module"))

    return (len(violations) == 0, tuple(violations))


def kudbee_cli_phase2_contract_summary(repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root if repo_root is not None else REPO_ROOT
    ok, violations = validate_features_manifest(repo_root=root)
    return {
        "gate_id": GATE_ID,
        "pr_number": PR_NUMBER,
        "pr178_gate_id": GATE_ID,
        "hermetic_operator_ok": ok,
        "live_verified": False,
        "live_api_called": False,
        "four_state_max": "TEST_VERIFIED",
        "combined_umbrella_nested": False,
        "feature_count": EXPECTED_FEATURE_COUNT,
        "cli_phase2_version": CLI_PHASE2_VERSION,
        "primary_surface": "thinkbox/cli.py + thinkbox/cli_phase2",
        "features_manifest_rel": str(FEATURES_MANIFEST_REL),
        "violation_count": len(violations),
        "violation_codes": [v.code for v in violations],
    }
