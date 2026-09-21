"""Pure helpers for KILO swarm reconciliation and proof validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence


def effective_rps(total_calls: int, elapsed_s: float) -> float:
    """Throughput for a swarm run; raises if elapsed is non-positive."""
    if elapsed_s <= 0:
        raise ValueError("elapsed_s must be positive")
    if total_calls < 0:
        raise ValueError("total_calls must be non-negative")
    return round(total_calls / elapsed_s, 2)


def latency_percentiles(
    latencies_s: Sequence[float],
    *,
    p50: float = 0.50,
    p95: float = 0.95,
) -> dict[str, float]:
    """Sorted-sample percentiles used by big_swarm reconciliation."""
    if not latencies_s:
        return {"p50_latency_s": 0.0, "p95_latency_s": 0.0, "max_latency_s": 0.0}
    ordered = sorted(latencies_s)
    n = len(ordered)

    def _at(frac: float) -> float:
        idx = min(n - 1, int(n * frac))
        return round(ordered[idx], 3)

    return {
        "p50_latency_s": _at(p50),
        "p95_latency_s": _at(p95),
        "max_latency_s": round(max(ordered), 3),
    }


def expected_live_calls(primary_workers: int, validator_workers: int) -> int:
    """Live HTTP compartments: one primary per claim plus validator wave."""
    if primary_workers < 1:
        raise ValueError("primary_workers must be >= 1")
    if validator_workers < 0:
        raise ValueError("validator_workers must be non-negative")
    return primary_workers + validator_workers


def validate_worker_rows(workers: Sequence[Mapping[str, Any]]) -> list[str]:
    """Check per-worker rows match global accounting."""
    errors: list[str] = []
    primary = [w for w in workers if w.get("role") == "PRIMARY"]
    validators = [w for w in workers if w.get("role") == "VALIDATOR"]
    total = len(workers)
    ok = sum(1 for w in workers if w.get("ok"))
    failed = total - ok
    if ok + failed != total:
        errors.append("ok+failed does not equal worker count")
    prim_ok = sum(1 for w in primary if w.get("ok"))
    if len(primary) + len(validators) != total:
        errors.append("primary+validator roles do not cover all workers")
    if prim_ok > len(primary):
        errors.append("primary ok count exceeds primary workers")
    return errors


def validate_reconciliation(recon: Mapping[str, Any], workers: Sequence[Mapping[str, Any]]) -> list[str]:
    """Validate reconciliation block against worker list."""
    errors: list[str] = []
    errors.extend(validate_worker_rows(workers))

    total_calls = int(recon.get("total_calls", -1))
    primary_calls = int(recon.get("primary_calls", -1))
    validator_calls = int(recon.get("validator_calls", -1))
    ok = int(recon.get("ok", -1))
    failed = int(recon.get("failed", -1))

    if primary_calls + validator_calls != total_calls:
        errors.append("primary_calls + validator_calls != total_calls")
    if ok + failed != total_calls:
        errors.append("ok + failed != total_calls")
    if len(workers) != total_calls:
        errors.append("len(workers) != total_calls")

    elapsed = float(recon.get("elapsed_s", 0))
    if elapsed > 0:
        expected_rps = effective_rps(total_calls, elapsed)
        reported = float(recon.get("effective_rps", -1))
        if abs(reported - expected_rps) > 0.02:
            errors.append(f"effective_rps {reported} != expected {expected_rps}")

    traces = int(recon.get("traces", -1))
    grounded = int(recon.get("traces_grounded", -1))
    if grounded > traces:
        errors.append("traces_grounded exceeds traces")
    if grounded > ok:
        errors.append("traces_grounded exceeds ok calls")

    ledger_this = recon.get("ledger_entries_this_run")
    ledger_total = recon.get("ledger_entries")
    if ledger_this is not None and ledger_total is not None:
        if int(ledger_this) > int(ledger_total):
            errors.append("ledger_entries_this_run exceeds ledger_entries")

    return errors


def validate_proof_document(payload: Mapping[str, Any]) -> list[str]:
    """Validate a big_swarm proof JSON document."""
    errors: list[str] = []
    required = ("run_id", "session_id", "reconciliation", "workers", "primary_workers", "validator_workers")
    for key in required:
        if key not in payload:
            errors.append(f"missing key: {key}")

    recon = payload.get("reconciliation") or {}
    workers = payload.get("workers") or []
    errors.extend(validate_reconciliation(recon, workers))

    prim = int(payload.get("primary_workers", 0))
    val = int(payload.get("validator_workers", 0))
    expected = expected_live_calls(prim, val)
    if int(recon.get("total_calls", 0)) != expected:
        errors.append(
            f"total_calls {recon.get('total_calls')} != primary+validators ({expected})"
        )

    return errors


def load_and_validate_proof(path: str | Path) -> tuple[dict[str, Any], list[str]]:
    """Load proof JSON from disk and return (payload, errors)."""
    data = json.loads(Path(path).read_text())
    return data, validate_proof_document(data)
