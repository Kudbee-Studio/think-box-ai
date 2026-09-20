"""Admission denial anomaly detection (hermetic window compare)."""

from __future__ import annotations

from thinkbox.org_memory_receipts import OrgMemoryReceiptStore


def detect_denial_anomalies(
    store: OrgMemoryReceiptStore,
    *,
    window: int = 50,
    spike_ratio: float = 2.5,
    min_denials: int = 3,
) -> dict:
    """Flag when recent denial density exceeds prior window baseline."""
    rows = store.query(limit=window * 2)
    recent = rows[:window]
    prior = rows[window : window * 2]

    def _denial_count(batch: list) -> int:
        return sum(
            1
            for r in batch
            if str(r.get("action") or "") in ("admission_denied", "merge_request_denied", "merge_policy_denied")
        )

    recent_denials = _denial_count(recent)
    prior_denials = _denial_count(prior)
    baseline = max(prior_denials, 1)
    ratio = recent_denials / baseline if baseline else float(recent_denials)
    anomalous = recent_denials >= min_denials and ratio >= spike_ratio
    return {
        "anomalous": anomalous,
        "recent_denials": recent_denials,
        "prior_denials": prior_denials,
        "ratio": round(ratio, 2),
        "window": window,
        "spike_ratio_threshold": spike_ratio,
        "evidence_label": "simulated",
        "auto_merge": False,
    }
