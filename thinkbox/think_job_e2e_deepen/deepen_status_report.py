"""Aggregate status report for PR #183 (F25)."""

from __future__ import annotations

from typing import Any

from thinkbox.think_job_e2e_deepen.deep_link_bridge import deep_link_bridge_summary
from thinkbox.think_job_e2e_deepen.gate_summary import gate_summary
from thinkbox.think_job_e2e_deepen.integrate import integration_summary
from thinkbox.think_job_e2e_deepen.negotiation import THINK_JOB_E2E_DEEPEN_VERSION
from thinkbox.think_job_e2e_deepen.run_job_bridge import run_job_bridge_summary
from thinkbox.think_job_e2e_deepen.status_catalog import status_catalog
from thinkbox.think_job_e2e_deepen.status_ui_bridge import status_ui_bridge_summary
from thinkbox.think_job_e2e_deepen.fixes.fix_registry_integrate import run_all_fixes
from thinkbox.think_job_e2e_deepen.stream_bridge import stream_bridge_summary


def route_catalog_deepen() -> list[dict[str, str]]:
    return [
        {"id": "think-job/deepen/status", "method": "GET", "hermetic": "true"},
        {"id": "think-job/deepen/cassette", "method": "GET", "hermetic": "true"},
        {"id": "think-job/deepen/dry-run", "method": "GET", "hermetic": "true"},
    ]


def think_job_e2e_deepen_status_report() -> dict[str, Any]:
    return {
        "think_job_e2e_deepen_version": THINK_JOB_E2E_DEEPEN_VERSION,
        "integration": integration_summary(),
        "status_catalog": status_catalog(),
        "stream_bridge": stream_bridge_summary(),
        "status_ui_bridge": status_ui_bridge_summary(),
        "run_job_bridge": run_job_bridge_summary(),
        "deep_link_bridge": deep_link_bridge_summary(),
        "gate_summary": gate_summary(),
        "major_fixes": run_all_fixes(),
        "live_verified": False,
        "live_api_called": False,
        "four_state_max": "TEST_VERIFIED",
    }


def run_hermetic_deepen_demo() -> dict[str, Any]:
    report = think_job_e2e_deepen_status_report()
    report["demo"] = True
    return report
