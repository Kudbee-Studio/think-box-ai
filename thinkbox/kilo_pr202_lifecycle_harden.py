"""Hermetic gate for PR #202 durable lifecycle harden pack."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from thinkbox.kilo_live_proof_readiness import REPO_ROOT
from thinkbox.lifecycle_harden import EXPECTED_HARDEN_COUNT, GATE_ID, HARDENS, PR_NUMBER, harden_ids

FEATURES_MANIFEST_REL = Path("data/lifecycle_harden/pr202_hardens.json")
PR202_PASS_REL = Path("docs/audit/passes/2026-09-24-pr202.json")


def load_hardens_manifest(repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root if repo_root is not None else REPO_ROOT
    return json.loads((root / FEATURES_MANIFEST_REL).read_text(encoding="utf-8"))


def validate_hardens_manifest(
    doc: Mapping[str, Any] | None = None,
    repo_root: Path | None = None,
) -> tuple[bool, tuple[str, ...]]:
    root = repo_root if repo_root is not None else REPO_ROOT
    violations: list[str] = []
    if doc is None:
        doc = load_hardens_manifest(root)
    if doc.get("gate_id") != GATE_ID:
        violations.append("gate_id")
    if doc.get("pr_number") != PR_NUMBER:
        violations.append("pr_number")
    if doc.get("live_verified") is True:
        violations.append("live_verified")
    hardens = list(doc.get("hardens") or [])
    if len(hardens) != EXPECTED_HARDEN_COUNT:
        violations.append("harden_count")
    ids = [str(item.get("id")) for item in hardens]
    if ids != list(harden_ids()):
        violations.append("harden_ids")
    for item in hardens:
        rel = item.get("module")
        if not rel or not (root / str(rel)).is_file():
            violations.append(f"module:{rel}")
    if not (root / PR202_PASS_REL).is_file():
        violations.append("audit_pass")
    names = {item[1] for item in HARDENS}
    for item in hardens:
        if item.get("name") not in names:
            violations.append(f"name:{item.get('name')}")
    return (len(violations) == 0, tuple(violations))


def lifecycle_harden_contract_summary(repo_root: Path | None = None) -> dict[str, Any]:
    ok, violations = validate_hardens_manifest(repo_root=repo_root)
    return {
        "gate_id": GATE_ID,
        "pr_number": PR_NUMBER,
        "harden_count": EXPECTED_HARDEN_COUNT,
        "hermetic_operator_ok": ok,
        "live_verified": False,
        "live_api_called": False,
        "four_state_max": "TEST_VERIFIED",
        "violations": list(violations),
        "primary_surface": "thinkbox/lifecycle_harden",
    }
