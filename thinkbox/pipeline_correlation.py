"""Cross-PR blast-radius correlation for admission incidents."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from thinkbox.pipeline_rollup import summarize_pr_from_receipts

from thinkbox.pipeline_dashboard import PipelineDashboardAggregator


def compute_blast_radius(
    aggregator: PipelineDashboardAggregator,
    *,
    receipt_limit: int = 400,
) -> dict[str, Any]:
    """Cluster PRs by shared denial reasons and branch families."""
    store = aggregator._store  # noqa: SLF001
    rows = store.query(limit=receipt_limit)
    by_reason: dict[str, list[int]] = defaultdict(list)
    by_branch_family: dict[str, list[int]] = defaultdict(list)
    prs_with_denials: set[int] = set()

    for row in rows:
        pr = int(row.get("pr_number") or 0)
        if pr <= 0:
            continue
        action = str(row.get("action") or "")
        if action in ("admission_denied", "merge_request_denied"):
            prs_with_denials.add(pr)
            evidence = row.get("evidence") or {}
            reason = str(
                evidence.get("admission_reason") or evidence.get("reason") or action
            )
            if pr not in by_reason[reason]:
                by_reason[reason].append(pr)

    for pr in aggregator._store.distinct_pr_numbers():  # noqa: SLF001
        receipts = store.query(pr_number=pr, limit=5)
        if not receipts:
            continue
        branch = str(receipts[0].get("branch") or "")
        family = branch.split("/")[0] if "/" in branch else branch or "unknown"
        by_branch_family[family].append(pr)

    hotspots: list[dict[str, Any]] = []
    for reason, prs in sorted(by_reason.items(), key=lambda kv: -len(kv[1])):
        if len(prs) < 2:
            continue
        hotspots.append({"kind": "denial_reason", "key": reason, "pr_numbers": sorted(prs), "count": len(prs)})

    for family, prs in sorted(by_branch_family.items(), key=lambda kv: -len(kv[1])):
        denied = [p for p in prs if p in prs_with_denials]
        if len(denied) >= 2:
            hotspots.append(
                {
                    "kind": "branch_family",
                    "key": family,
                    "pr_numbers": sorted(denied),
                    "count": len(denied),
                }
            )

    summaries = {
        pr: summarize_pr_from_receipts(pr, store.query(pr_number=pr, limit=50)).to_dict()
        for pr in prs_with_denials
    }
    return {
        "hotspots": hotspots,
        "prs_with_denials": sorted(prs_with_denials),
        "pr_summaries": summaries,
        "evidence_label": "simulated",
        "auto_merge": False,
    }
