"""Deterministic merge-readiness scoring from org-memory receipts (no ML)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from thinkbox.org_memory_receipts import OrgMemoryReceiptStore
from thinkbox.pipeline_rollup import summarize_pr_from_receipts


@dataclass(frozen=True)
class MergeReadinessRule:
    """One scored gate; weight contributes to 0–100 readiness."""

    code: str
    passed: bool
    weight: int
    detail: str


@dataclass
class MergeReadinessReport:
    pr_number: int
    score: int
    ready: bool
    blockers: list[str] = field(default_factory=list)
    rules: list[dict[str, Any]] = field(default_factory=list)
    evidence_label: str = "simulated"

    def to_dict(self) -> dict[str, Any]:
        return {
            "pr_number": self.pr_number,
            "score": self.score,
            "ready": self.ready,
            "blockers": self.blockers,
            "rules": self.rules,
            "evidence_label": self.evidence_label,
            "auto_merge": False,
            "github_merge_enabled": False,
        }


def _quarantine_active(store: OrgMemoryReceiptStore) -> bool:
    for row in store.query(limit=30):
        if str(row.get("action") or "") != "pipeline_quarantine":
            continue
        evidence = row.get("evidence") or {}
        if evidence.get("quarantined"):
            return True
    return False


def _ci_observations(receipts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in receipts:
        if str(row.get("action") or "") != "ci_status_observed":
            continue
        evidence = row.get("evidence") or {}
        out.append(
            {
                "conclusion": str(evidence.get("conclusion") or "").lower(),
                "workflow": evidence.get("workflow"),
            }
        )
    return out


def _evaluate_ci_gate(summary_last_ci: Optional[dict[str, Any]], receipts: list[dict[str, Any]]) -> MergeReadinessRule:
    """CI is not required when Actions are unavailable; explicit failure still blocks."""
    observations = _ci_observations(receipts)
    if not observations:
        return MergeReadinessRule(
            "ci_success",
            True,
            25,
            "CI not observed (local unittest gate; GitHub Actions optional)",
        )
    conclusion = str((summary_last_ci or {}).get("conclusion") or observations[0].get("conclusion") or "").lower()
    if conclusion == "success":
        return MergeReadinessRule("ci_success", True, 25, "last CI success")
    return MergeReadinessRule(
        "ci_success",
        False,
        25,
        f"last CI not success ({conclusion or 'unknown'})",
    )


def evaluate_merge_readiness(
    store: OrgMemoryReceiptStore,
    pr_number: int,
    *,
    receipt_limit: int = 200,
) -> MergeReadinessReport:
    """Score whether a PR is eligible to *request* founder merge (not auto-merge)."""
    chain_ok = store.verify()
    receipts = store.query(pr_number=pr_number, limit=receipt_limit)
    summary = summarize_pr_from_receipts(pr_number, receipts)
    rules: list[MergeReadinessRule] = []

    rules.append(
        MergeReadinessRule(
            "chain_verified",
            chain_ok,
            25,
            "org-memory hash chain intact" if chain_ok else "receipt chain broken",
        )
    )
    q_ok = not _quarantine_active(store)
    rules.append(
        MergeReadinessRule(
            "quarantine_clear",
            q_ok,
            20,
            "pipeline not quarantined" if q_ok else             "pipeline quarantine active",
        )
    )
    rules.append(_evaluate_ci_gate(summary.last_ci, receipts))
    adm_ok = summary.admission_denied_count == 0
    rules.append(
        MergeReadinessRule(
            "no_admission_denials",
            adm_ok,
            15,
            "no admission_denied receipts" if adm_ok else f"{summary.admission_denied_count} denials",
        )
    )
    verified_ok = summary.evidence_counts.verified >= 1
    rules.append(
        MergeReadinessRule(
            "verified_evidence",
            verified_ok,
            15,
            "≥1 verified receipt" if verified_ok else "no verified evidence",
        )
    )

    earned = sum(r.weight for r in rules if r.passed)
    total = sum(r.weight for r in rules)
    score = int(round(100 * earned / total)) if total else 0
    blockers = [r.detail for r in rules if not r.passed]
    ready = score == 100 and not blockers
    return MergeReadinessReport(
        pr_number=pr_number,
        score=score,
        ready=ready,
        blockers=blockers,
        rules=[{"code": r.code, "passed": r.passed, "weight": r.weight, "detail": r.detail} for r in rules],
    )
