"""Hermetic chronicle honesty contracts (PR #173, ``chronicle-honesty``).

Validates that spine-facing Markdown agrees on post-#170 era facts: #170–#172
merged on main, no stale draft labels for those PRs, no affirmative KILO LIVE
claims in spine docs, and README/runbook pointers to fast spine + explicit lint.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from thinkbox.kilo_live_proof_readiness import (
    REPO_ROOT,
    find_affirmative_kilo_live_claims,
    find_forbidden_literal_claims,
)

__all__ = (
    "AGENTS_KILO_TABLE_REL",
    "CHRONICLE_DOC_RELS",
    "GATE_ID",
    "PR_NUMBER",
    "PR173_PASS_REL",
    "README_REL",
    "ROADMAP_REL",
    "ChronicleHonestyViolation",
    "chronicle_honesty_contract_summary",
    "validate_chronicle_documents",
)

GATE_ID = "chronicle-honesty"
PR_NUMBER = 173

PR173_PASS_REL = Path("docs/audit/passes/2026-09-24-pr173.json")
AGENTS_KILO_TABLE_REL = Path("AGENTS.md")
README_REL = Path("README.md")
ROADMAP_REL = Path("docs/roadmaps/kilo-post-170-pr-roadmap.md")
CONTINUITY_REL = Path("docs/CONTINUITY.md")
RUNBOOK_REL = Path("docs/runbooks/kilo-live-proof-readiness.md")

CHRONICLE_DOC_RELS: tuple[Path, ...] = (
    AGENTS_KILO_TABLE_REL,
    CONTINUITY_REL,
    ROADMAP_REL,
    README_REL,
    RUNBOOK_REL,
)

README_HONESTY_MARKERS: tuple[str, ...] = (
    "one implementation PR at a time",
    "single-theme",
    "fast-by-default",
    "--e2e",
)


@dataclass(frozen=True)
class ChronicleHonestyViolation:
    """Single fail-closed chronicle doc violation."""

    code: str
    message: str
    path: str | None = None


def _read_rel(rel: Path) -> str:
    return (REPO_ROOT / rel).read_text(encoding="utf-8")


def _doc_text(docs: Mapping[str, str], rel: Path) -> str:
    for key, text in docs.items():
        if key.endswith(str(rel)):
            return text
    return docs.get(str(rel), docs.get(str(REPO_ROOT / rel), ""))


def validate_chronicle_documents(
    docs: Mapping[str, str] | None = None,
) -> tuple[bool, tuple[ChronicleHonestyViolation, ...]]:
    """Ensure post-#170 chronicle docs are internally consistent."""
    violations: list[ChronicleHonestyViolation] = []
    if docs is None:
        docs = {str(rel): _read_rel(rel) for rel in CHRONICLE_DOC_RELS}

    for rel in CHRONICLE_DOC_RELS:
        if not _doc_text(docs, rel):
            violations.append(
                ChronicleHonestyViolation(
                    code="chronicle_doc_missing",
                    message=f"Missing document {rel}",
                    path=str(rel),
                )
            )

    agents = _doc_text(docs, AGENTS_KILO_TABLE_REL)
    for stale in ("| **#170** (draft)", "| **#172** (draft)"):
        if stale in agents:
            violations.append(
                ChronicleHonestyViolation(
                    code="agents_kilo_table_stale_pr",
                    message=f"Remove stale KILO table row: {stale}",
                    path=str(AGENTS_KILO_TABLE_REL),
                )
            )
    if "| **#170** (merged)" not in agents or "| **#172** (merged)" not in agents:
        violations.append(
            ChronicleHonestyViolation(
                code="agents_kilo_table_missing_merged",
                message="AGENTS KILO table must list #170 and #172 as merged",
                path=str(AGENTS_KILO_TABLE_REL),
            )
        )

    roadmap = _doc_text(docs, ROADMAP_REL)
    if "Chronicle gap" in roadmap:
        violations.append(
            ChronicleHonestyViolation(
                code="roadmap_chronicle_gap_stale",
                message="Roadmap must not list open chronicle gap after #173",
                path=str(ROADMAP_REL),
            )
        )
    if "| **#172** (draft)" in roadmap or "| CI | **#172 draft:" in roadmap:
        violations.append(
            ChronicleHonestyViolation(
                code="roadmap_pr172_draft_stale",
                message="Roadmap must not call #172 draft after merge",
                path=str(ROADMAP_REL),
            )
        )
    if "**#172** (merged)" not in roadmap and "**#172 merged:**" not in roadmap:
        violations.append(
            ChronicleHonestyViolation(
                code="roadmap_pr172_merged_missing",
                message="Roadmap snapshot must state #172 merged",
                path=str(ROADMAP_REL),
            )
        )

    readme = _doc_text(docs, README_REL)
    for marker in README_HONESTY_MARKERS:
        if marker.lower() not in readme.lower():
            violations.append(
                ChronicleHonestyViolation(
                    code="readme_honesty_marker_missing",
                    message=f"README must mention: {marker}",
                    path=str(README_REL),
                )
            )
    for required in (
        "docs/roadmaps/kilo-post-170-pr-roadmap.md",
        "verify_kilo_spine.py",
        "verify_kilo_beyond_kilo_lint.py",
        "TEST VERIFIED",
    ):
        if required not in readme:
            violations.append(
                ChronicleHonestyViolation(
                    code="readme_required_pointer_missing",
                    message=f"README must reference: {required}",
                    path=str(README_REL),
                )
            )

    runbook = _doc_text(docs, RUNBOOK_REL)
    if "| H31 |" not in runbook or "verify_kilo_spine.py" not in runbook:
        violations.append(
            ChronicleHonestyViolation(
                code="runbook_spine_trust_stale",
                message="Runbook must document H31 PR CI spine-trust model",
                path=str(RUNBOOK_REL),
            )
        )

    continuity = _doc_text(docs, CONTINUITY_REL)
    if "#172** draft" in continuity or "PR #172 draft" in continuity:
        violations.append(
            ChronicleHonestyViolation(
                code="continuity_pr172_draft_stale",
                message="CONTINUITY must not label merged #172 as draft",
                path=str(CONTINUITY_REL),
            )
        )

    readme_scan = "\n".join(
        line
        for line in readme.splitlines()
        if "do not claim" not in line.lower() and "must not claim" not in line.lower()
    )
    for literal in find_forbidden_literal_claims(readme_scan):
        violations.append(
            ChronicleHonestyViolation(
                code="forbidden_literal_claim",
                message=f"Forbidden literal claim in README: {literal}",
                path=str(README_REL),
            )
        )
    for claim in find_affirmative_kilo_live_claims(readme_scan):
        violations.append(
            ChronicleHonestyViolation(
                code="affirmative_kilo_live_claim",
                message=f"Affirmative KILO LIVE claim in README: {claim}",
                path=str(README_REL),
            )
        )

    return (len(violations) == 0, tuple(violations))


def chronicle_honesty_contract_summary(
    docs: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Hermetic summary for PR #173 chronicle-honesty gate."""
    ok, violations = validate_chronicle_documents(docs)
    return {
        "gate_id": GATE_ID,
        "pr_number": PR_NUMBER,
        "pr173_gate_id": GATE_ID,
        "hermetic_operator_ok": ok,
        "live_verified": False,
        "live_api_called": False,
        "four_state_max": "TEST_VERIFIED",
        "combined_umbrella_nested": False,
        "chronicle_doc_count": len(CHRONICLE_DOC_RELS),
        "violation_count": len(violations),
        "violation_codes": [v.code for v in violations],
        "pr170_merged_required": True,
        "pr172_merged_required": True,
    }
