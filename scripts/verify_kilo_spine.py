#!/usr/bin/env python3
"""Print KILO Live-proof readiness spine contract summary (PR #141, hermetic)."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from thinkbox.kilo_hermetic_subprocess import enable_nested_e2e_unittest
from thinkbox.kilo_live_proof_readiness import spine_contract_summary

_SPINE_BLOCKS: tuple[tuple[str, str], ...] = (
    ("env_matrix", "hermetic_operator_ok"),
    ("substrate_checklist", "hermetic_operator_ok"),
    ("governance_evidence", "hermetic_operator_ok"),
    ("mercury_hermetic", "hermetic_operator_ok"),
    ("swarm_instrumentation", "hermetic_operator_ok"),
    ("proof_schema", "hermetic_operator_ok"),
    ("dashboard_slots", "hermetic_operator_ok"),
    ("live_proof_exec", "hermetic_operator_ok"),
    ("post_season_harden", "hermetic_operator_ok"),
    ("live_smoke_evidence", "hermetic_operator_ok"),
    ("live_smoke_operator", "hermetic_operator_ok"),
    ("control_plane_api", "hermetic_operator_ok"),
    ("receipt_chain_etag", "hermetic_operator_ok"),
    ("dashboard_receipt_chain_bind", "hermetic_operator_ok"),
    ("api_ops_harden", "hermetic_operator_ok"),
    ("end_link_deepen", "hermetic_operator_ok"),
    ("end_link_operator_ux", "hermetic_operator_ok"),
    ("receipt_chain_end_link_docs", "hermetic_operator_ok"),
    ("end_link_api_ops_harden", "hermetic_operator_ok"),
    ("receipt_chain_end_link_era_close", "hermetic_operator_ok"),
    ("control_plane_e2e_deepen", "hermetic_operator_ok"),
    ("governance_evidence_live_proof_readiness", "hermetic_operator_ok"),
    ("pr165_combined_harden_era_chronicle", "hermetic_operator_ok"),
    ("pr166_combined_post165_lane", "hermetic_operator_ok"),
    ("pr167_combined_post166_lane", "hermetic_operator_ok"),
    ("pr168_combined_post167_lane", "hermetic_operator_ok"),
    ("pr169_combined_post168_lane", "hermetic_operator_ok"),
    ("beyond_kilo_lint_readiness", "hermetic_operator_ok"),
)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="KILO Live-proof spine hermetic verify")
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Skip nested control-plane e2e unittest subprocess (default unless --e2e)",
    )
    parser.add_argument(
        "--e2e",
        action="store_true",
        help="Run full spine including nested e2e unittest subprocess (slower)",
    )
    return parser.parse_args(argv)


def _resolve_fast_mode(args: argparse.Namespace) -> bool:
    if args.e2e:
        return False
    return True


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    fast_mode = _resolve_fast_mode(args)
    if not fast_mode:
        enable_nested_e2e_unittest()
    print(
        f"phase: spine verify start (fast={fast_mode}, e2e_nested_unittest={not fast_mode})",
        flush=True,
    )
    summary = spine_contract_summary(fast=fast_mode)
    print("phase: spine contract summary built", flush=True)
    print(json.dumps(summary, indent=2, sort_keys=True), flush=True)
    if summary.get("missing_spine_docs") or summary.get("missing_runbook_headings"):
        return 1
    for block_name, ok_field in _SPINE_BLOCKS:
        block = summary.get(block_name) or {}
        if not block.get(ok_field):
            print(f"phase: failed block {block_name}.{ok_field}", flush=True)
            return 1
    print("phase: spine verify ok", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
