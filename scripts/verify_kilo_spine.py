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
    # PR #147 swarm-instrumentation layers on mercury-hermetic.
    if not mercury_block.get("hermetic_operator_ok"):
        return 1
    swarm_block = summary.get("swarm_instrumentation") or {}
    if not swarm_block.get("hermetic_operator_ok"):
        return 1
    proof_block = summary.get("proof_schema") or {}
    if not proof_block.get("hermetic_operator_ok"):
        return 1
    dashboard_block = summary.get("dashboard_slots") or {}
    if not dashboard_block.get("hermetic_operator_ok"):
        return 1
    live_exec_block = summary.get("live_proof_exec") or {}
    if not live_exec_block.get("hermetic_operator_ok"):
        return 1
    post_season_block = summary.get("post_season_harden") or {}
    if not post_season_block.get("hermetic_operator_ok"):
        return 1
    smoke_block = summary.get("live_smoke_evidence") or {}
    if not smoke_block.get("hermetic_operator_ok"):
        return 1
    operator_block = summary.get("live_smoke_operator") or {}
    if not operator_block.get("hermetic_operator_ok"):
        return 1
    control_plane_block = summary.get("control_plane_api") or {}
    if not control_plane_block.get("hermetic_operator_ok"):
        return 1
    receipt_chain_block = summary.get("receipt_chain_etag") or {}
    if not receipt_chain_block.get("hermetic_operator_ok"):
        return 1
    dashboard_bind_block = summary.get("dashboard_receipt_chain_bind") or {}
    if not dashboard_bind_block.get("hermetic_operator_ok"):
        return 1
    api_ops_harden_block = summary.get("api_ops_harden") or {}
    if not api_ops_harden_block.get("hermetic_operator_ok"):
        return 1
    end_link_deepen_block = summary.get("end_link_deepen") or {}
    if not end_link_deepen_block.get("hermetic_operator_ok"):
        return 1
    end_link_operator_ux_block = summary.get("end_link_operator_ux") or {}
    if not end_link_operator_ux_block.get("hermetic_operator_ok"):
        return 1
    receipt_chain_end_link_docs_block = summary.get("receipt_chain_end_link_docs") or {}
    if not receipt_chain_end_link_docs_block.get("hermetic_operator_ok"):
        return 1
    end_link_api_ops_harden_block = summary.get("end_link_api_ops_harden") or {}
    if not end_link_api_ops_harden_block.get("hermetic_operator_ok"):
        return 1
    era_close_block = summary.get("receipt_chain_end_link_era_close") or {}
    if not era_close_block.get("hermetic_operator_ok"):
        return 1
    e2e_deepen_block = summary.get("control_plane_e2e_deepen") or {}
    if not e2e_deepen_block.get("hermetic_operator_ok"):
        return 1
    gov_evidence_readiness_block = summary.get("governance_evidence_live_proof_readiness") or {}
    if not gov_evidence_readiness_block.get("hermetic_operator_ok"):
        return 1
    pr165_block = summary.get("pr165_combined_harden_era_chronicle") or {}
    if not pr165_block.get("hermetic_operator_ok"):
        return 1
    pr166_block = summary.get("pr166_combined_post165_lane") or {}
    if not pr166_block.get("hermetic_operator_ok"):
        return 1
    pr167_block = summary.get("pr167_combined_post166_lane") or {}
    if not pr167_block.get("hermetic_operator_ok"):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
