#!/usr/bin/env python3
"""Print KILO Live-proof readiness spine contract summary (PR #141, hermetic)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from thinkbox.kilo_live_proof_readiness import spine_contract_summary


def main() -> int:
    summary = spine_contract_summary()
    print(json.dumps(summary, indent=2, sort_keys=True))
    if summary.get("missing_spine_docs") or summary.get("missing_runbook_headings"):
        return 1
    env_block = summary.get("env_matrix") or {}
    if not env_block.get("hermetic_operator_ok"):
        return 1
    substrate_block = summary.get("substrate_checklist") or {}
    if not substrate_block.get("hermetic_operator_ok"):
        return 1
    governance_block = summary.get("governance_evidence") or {}
    if not governance_block.get("hermetic_operator_ok"):
        return 1
    mercury_block = summary.get("mercury_hermetic") or {}
    if not mercury_block.get("hermetic_operator_ok"):
        return 1
    swarm_block = summary.get("swarm_instrumentation") or {}
    if not swarm_block.get("hermetic_operator_ok"):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
