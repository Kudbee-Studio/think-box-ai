"""Lazy gate summary bridge (PR #186)."""
from __future__ import annotations
from typing import Any

def gate_summary() -> dict[str, Any]:
    from thinkbox.kilo_pr186_think_job_run_receipt_deepen import think_job_run_receipt_deepen_contract_summary
    return think_job_run_receipt_deepen_contract_summary()
