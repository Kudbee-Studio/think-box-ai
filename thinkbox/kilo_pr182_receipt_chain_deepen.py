"""Hermetic receipt-chain deepen contracts (PR #182, ``receipt-chain-deepen``).

Validates ~25 deepen features under ``thinkbox/receipt_chain_deepen/`` and manifest
at ``data/receipt_chain/pr182_features.json``.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from thinkbox.kilo_live_proof_readiness import REPO_ROOT
from thinkbox.receipt_chain_deepen.negotiation import RECEIPT_CHAIN_DEEPEN_VERSION

__all__ = (
    "EXPECTED_FEATURE_COUNT",
    "FEATURES_MANIFEST_REL",
    "GATE_ID",
    "PR182_PASS_REL",
    "PR_NUMBER",
    "ReceiptChainDeepenViolation",
    "load_features_manifest",
    "receipt_chain_deepen_contract_summary",
    "validate_features_manifest",
)

GATE_ID = "receipt-chain-deepen"
PR_NUMBER = 182
EXPECTED_FEATURE_COUNT = 25

FEATURES_MANIFEST_REL = Path("data/receipt_chain/pr182_features.json")
PR182_PASS_REL = Path("docs/audit/passes/2026-09-24-pr182.json")


@dataclass(frozen=True)
class ReceiptChainDeepenViolation:
    code: str
    message: str
    path: str | None = None


def load_features_manifest(repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root if repo_root is not None else REPO_ROOT
    return json.loads((root / FEATURES_MANIFEST_REL).read_text(encoding="utf-8"))


def validate_features_manifest(
    doc: Mapping[str, Any] | None = None,
    repo_root: Path | None = None,
) -> tuple[bool, tuple[ReceiptChainDeepenViolation, ...]]:
    root = repo_root if repo_root is not None else REPO_ROOT
    violations: list[ReceiptChainDeepenViolation] = []
    if doc is None:
        doc = load_features_manifest(root)

    if doc.get("gate_id") != GATE_ID:
        violations.append(ReceiptChainDeepenViolation("gate_id", "gate_id mismatch"))
    if doc.get("pr_number") != PR_NUMBER:
        violations.append(ReceiptChainDeepenViolation("pr_number", "pr_number mismatch"))
    if doc.get("live_verified") is True:
        violations.append(ReceiptChainDeepenViolation("live_verified", "must be false"))
    features = list(doc.get("features") or [])
    if len(features) != EXPECTED_FEATURE_COUNT:
        violations.append(
            ReceiptChainDeepenViolation(
                "feature_count",
                f"expected {EXPECTED_FEATURE_COUNT} features",
            ),
        )
    seen_ids: set[str] = set()
    for feat in features:
        fid = str(feat.get("id", ""))
        if fid in seen_ids:
            violations.append(ReceiptChainDeepenViolation("duplicate_feature_id", fid))
        seen_ids.add(fid)
        rel = feat.get("module")
        if not rel or not (root / str(rel)).is_file():
            violations.append(
                ReceiptChainDeepenViolation(
                    "feature_module_missing",
                    f"missing module for {fid}",
                    path=str(rel),
                ),
            )

    quickstart = root / "docs/guides/receipt_chain_deepen_quickstart.md"
    if not quickstart.is_file():
        violations.append(ReceiptChainDeepenViolation("quickstart_doc", "missing quickstart guide"))

    example = root / "examples/receipt_chain_deepen_quickstart.py"
    if not example.is_file():
        violations.append(ReceiptChainDeepenViolation("quickstart_example", "missing example"))

    status_mod = root / "thinkbox/receipt_chain_deepen/deepen_status_report.py"
    if not status_mod.is_file():
        violations.append(ReceiptChainDeepenViolation("status_report", "missing status module"))

    cassette = root / "data/receipt_chain/cassettes/chain_append_flow.json"
    if not cassette.is_file():
        violations.append(ReceiptChainDeepenViolation("cassette_fixture", "missing default cassette"))

    return (len(violations) == 0, tuple(violations))


def receipt_chain_deepen_contract_summary(repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root if repo_root is not None else REPO_ROOT
    ok, violations = validate_features_manifest(repo_root=root)
    return {
        "gate_id": GATE_ID,
        "pr_number": PR_NUMBER,
        "pr182_gate_id": GATE_ID,
        "hermetic_operator_ok": ok,
        "live_verified": False,
        "live_api_called": False,
        "four_state_max": "TEST_VERIFIED",
        "combined_umbrella_nested": False,
        "feature_count": EXPECTED_FEATURE_COUNT,
        "receipt_chain_deepen_version": RECEIPT_CHAIN_DEEPEN_VERSION,
        "primary_surface": "thinkbox/receipt_chain_deepen + receipt_chain_query bridges",
        "features_manifest_rel": str(FEATURES_MANIFEST_REL),
        "violation_count": len(violations),
        "violation_codes": [v.code for v in violations],
    }
