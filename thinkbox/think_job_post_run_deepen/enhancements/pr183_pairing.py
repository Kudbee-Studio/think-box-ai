"""Pairing stub with PR #183 think_job_e2e_deepen."""

from __future__ import annotations

from typing import Any

from thinkbox.think_job_e2e_deepen.negotiation import THINK_JOB_E2E_DEEPEN_VERSION


def pr183_pairing_summary() -> dict[str, Any]:
    return {
        "paired_pr": 183,
        "think_job_e2e_deepen_version": THINK_JOB_E2E_DEEPEN_VERSION,
        "live_api_called": False,
    }
