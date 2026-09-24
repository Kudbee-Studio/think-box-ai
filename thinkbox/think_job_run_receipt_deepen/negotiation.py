"""Capability negotiation (PR #186 F03)."""
from __future__ import annotations
THINK_JOB_RUN_RECEIPT_DEEPEN_VERSION = 1
GATE_ID = "think-job-run-receipt-deepen"

def negotiate_caps(client: tuple[str, ...], server: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(sorted(set(client) & set(server)))
