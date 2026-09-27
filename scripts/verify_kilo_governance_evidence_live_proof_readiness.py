#!/usr/bin/env python3
"""Hermetic operator gate: governance-evidence Live-proof readiness (PR #164)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from thinkbox.kilo_governance_evidence_live_proof_readiness import (
    governance_evidence_live_proof_readiness_contract_summary,
)


def main() -> int:
    summary = governance_evidence_live_proof_readiness_contract_summary()
    print(json.dumps(summary, indent=2, sort_keys=True))
    if not summary.get("hermetic_operator_ok"):
        return 1
    if summary.get("live_verified", True):
        return 1
    if summary.get("live_api_called", True):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
