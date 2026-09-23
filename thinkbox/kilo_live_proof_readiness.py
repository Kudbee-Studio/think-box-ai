"""KILO Live-proof readiness spine contracts (PR #141).

Hermetic documentation gates only — no live Mercury, GPU, or deploy side effects.
PR #143 adds ``substrate_checklist`` summary layered on ``env_matrix``.
PR #145 adds ``governance_evidence`` summary layered on env-matrix + substrate-checklist.
PR #150 adds ``live_proof_exec`` summary (arc season close; hermetic only).
PR #151 adds ``post_season_harden`` summary (ops CI + branch hygiene; not an arc gate).
PR #152 adds ``live_smoke_evidence`` summary (bounded smoke binder + audit flip; not Live proof).
PR #153 adds ``live_smoke_operator`` summary (hermetic CLI write + audit flip candidate; not Live proof).
PR #154 adds ``control_plane_api`` summary (HTTP surface upgrade; not Live proof).
PR #155 adds ``receipt_chain_etag`` summary (chain pagination + ETag deepen; not Live proof).
PR #156 adds ``dashboard_receipt_chain_bind`` (dashboard UI + END_LINK; not Live proof).
PR #157 adds ``api_ops_harden`` (control-plane ops harden after #156; not Live proof).
PR #158 adds ``end_link_deepen`` (END LINK batch + integrity deepen after #157; not Live proof).
PR #159 adds ``end_link_operator_ux`` (operator dashboard UX after #158; not Live proof).
PR #160 adds ``receipt_chain_end_link_docs`` (docs + audit pack after #159; not Live proof).
PR #161 adds ``end_link_api_ops_harden`` (API/ops harden after #160; not Live proof).
PR #162 adds ``control_plane_e2e_deepen`` (hermetic control-plane e2e suite after #161; not Live proof).
PR #162 also retains ``receipt_chain_end_link_era_close`` (era audit pack #154–#161; not Live proof).
PR #164 adds ``governance_evidence_live_proof_readiness`` (governance-evidence Live-proof readiness; not Live proof).
PR #165 adds ``pr165_combined_harden_era_chronicle`` (live-smoke audit-flip harden + post-#164 control-plane deepen + receipt-chain season harden + #154–#164 era chronicle; not Live proof).
PR #166 adds ``pr166_combined_post165_lane`` (operator prep deepen + api ops post165 + dashboard PR165 bind + swarm/governance post165; not Live proof).
PR #167 adds ``pr167_combined_post166_lane`` (operator audit-flip deepen + api ops post166 + dashboard PR166 bind + swarm/governance post166; not Live proof).
PR #146 adds ``mercury_hermetic`` summary layered on governance-evidence.
PR #147 adds ``swarm_instrumentation`` summary layered on mercury-hermetic.
PR #148 adds ``proof_schema`` summary layered on swarm-instrumentation.
PR #149 adds ``dashboard_slots`` summary layered on proof-schema.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

RUNBOOK_REL = Path("docs/runbooks/kilo-live-proof-readiness.md")
ARC_DOC_REL = Path("docs/kilo-live-proof-arc.md")

SPINE_DOC_PATHS: tuple[Path, ...] = (
    REPO_ROOT / "AGENTS.md",
    REPO_ROOT / "STATUS.md",
    REPO_ROOT / "docs/CONTINUITY.md",
    REPO_ROOT / "docs/STATUS.md",
    REPO_ROOT / RUNBOOK_REL,
    REPO_ROOT / ARC_DOC_REL,
)

FORBIDDEN_AFFIRMATIVE_CLAIMS: tuple[str, ...] = (
    "KILO LIVE VERIFIED",
    "KILO PRODUCTION READY",
    "KILO live build verified",
)

REQUIRED_RUNBOOK_HEADINGS: tuple[str, ...] = (
    "# KILO Live-proof readiness runbook",
    "## Four-state ladder",
    "## Forbidden claims until Live proof",
    "## Hermetic prerequisites",
    "## Arc gates (#141–#150)",
    "## Do not claim LIVE VERIFIED",
)

_AFFIRMATIVE_KILO_LIVE = re.compile(
    r"KILO.{0,40}(LIVE VERIFIED|PRODUCTION READY|live build verified)",
    re.IGNORECASE | re.DOTALL,
)

_NEGATION_PREFIX = re.compile(
    r"(do not|must not|never|forbidden|not)\s",
    re.IGNORECASE,
)


def _strip_markdown_section(text: str, section_heading: str) -> str:
    """Remove one ## section (used to skip explicit forbidden-example lists)."""
    start = text.find(section_heading)
    if start < 0:
        return text
    next_heading = text.find("\n## ", start + len(section_heading))
    if next_heading < 0:
        return text[:start]
    return text[:start] + text[next_heading:]


def _runbook_text_for_claim_scan(raw: str) -> str:
    """Runbook may quote forbidden literals inside the forbidden-claims section."""
    return _strip_markdown_section(raw, "## Forbidden claims until Live proof")


@dataclass(frozen=True)
class ArcGate:
    """One PR-sized gate in the #141–#150 readiness arc."""

    pr_number: int
    theme: str
    gate_id: str


ARC_GATES: tuple[ArcGate, ...] = (
    ArcGate(141, "Env docs + runbook spine", "spine-docs"),
    ArcGate(142, "Hermetic KILO env matrix", "env-matrix"),
    ArcGate(143, "Substrate readiness checklist", "substrate-checklist"),
    ArcGate(144, "CI/post-merge spine unittest green", "ci-post-merge"),
    ArcGate(145, "Governance admission evidence shape", "governance-evidence"),
    ArcGate(146, "Mercury hermetic mocks + live-gate stubs", "mercury-hermetic"),
    ArcGate(147, "Swarm instrumentation verify prereq", "swarm-instrumentation"),
    ArcGate(148, "KILO live proof JSON schema", "proof-schema"),
    ArcGate(149, "Dashboard Live proof slots (hermetic)", "dashboard-slots"),
    ArcGate(150, "Live proof execution + founder ack runbook", "live-proof-exec"),
)


def runbook_path() -> Path:
    """Absolute path to the KILO Live-proof readiness runbook."""
    return REPO_ROOT / RUNBOOK_REL


def arc_doc_path() -> Path:
    """Absolute path to the arc overview document."""
    return REPO_ROOT / ARC_DOC_REL


def load_text(path: Path) -> str:
    """Read UTF-8 text from *path*."""
    return path.read_text(encoding="utf-8")


def missing_spine_docs() -> list[str]:
    """Return repo-relative paths that are missing from disk."""
    missing: list[str] = []
    for path in SPINE_DOC_PATHS:
        if not path.is_file():
            missing.append(str(path.relative_to(REPO_ROOT)))
    return missing


def missing_runbook_headings(runbook_text: str | None = None) -> list[str]:
    """Return required headings absent from the runbook."""
    text = runbook_text if runbook_text is not None else load_text(runbook_path())
    return [heading for heading in REQUIRED_RUNBOOK_HEADINGS if heading not in text]


def find_forbidden_literal_claims(text: str) -> list[str]:
    """Find forbidden literal claim strings (case-sensitive markers)."""
    return [claim for claim in FORBIDDEN_AFFIRMATIVE_CLAIMS if claim in text]


def find_affirmative_kilo_live_claims(text: str) -> list[str]:
    """Find lines that affirm KILO Live/production status (negated lines excluded)."""
    hits: list[str] = []
    for line in text.splitlines():
        if not _AFFIRMATIVE_KILO_LIVE.search(line):
            continue
        stripped = line.strip()
        if _NEGATION_PREFIX.search(stripped):
            continue
        if stripped.startswith("- `") and "do not" in stripped.lower():
            continue
        hits.append(stripped[:120])
    return hits


def arc_pr_numbers() -> list[int]:
    """PR numbers in the readiness arc (#141–#150)."""
    return [gate.pr_number for gate in ARC_GATES]


def gate_ids() -> list[str]:
    """Stable gate identifiers for the arc."""
    return [gate.gate_id for gate in ARC_GATES]


def gate_for_pr(pr_number: int) -> ArcGate | None:
    """Return arc gate metadata for a PR number, if defined."""
    for gate in ARC_GATES:
        if gate.pr_number == pr_number:
            return gate
    return None


def spine_contract_summary() -> dict[str, object]:
    """Hermetic summary for CLI/dashboard consumers (no I/O beyond spine reads)."""
    from thinkbox.kilo_env_matrix import env_matrix_contract_summary
    from thinkbox.kilo_governance_evidence import governance_evidence_contract_summary
    from thinkbox.kilo_mercury_hermetic import mercury_hermetic_contract_summary
    from thinkbox.kilo_substrate_checklist import substrate_checklist_contract_summary
    from thinkbox.kilo_dashboard_slots import dashboard_slots_contract_summary
    from thinkbox.kilo_live_proof_exec import live_proof_exec_contract_summary
    from thinkbox.kilo_live_smoke_evidence import live_smoke_evidence_contract_summary
    from thinkbox.kilo_live_smoke_operator import live_smoke_operator_contract_summary
    from thinkbox.kilo_control_plane_api import control_plane_api_contract_summary
    from thinkbox.kilo_receipt_chain_etag import receipt_chain_etag_contract_summary
    from thinkbox.kilo_dashboard_receipt_chain_bind import (
        dashboard_receipt_chain_bind_contract_summary,
    )
    from thinkbox.kilo_api_ops_harden import api_ops_harden_contract_summary
    from thinkbox.kilo_end_link_deepen import end_link_deepen_contract_summary
    from thinkbox.kilo_end_link_operator_ux import end_link_operator_ux_contract_summary
    from thinkbox.kilo_receipt_chain_end_link_docs import (
        receipt_chain_end_link_docs_contract_summary,
    )
    from thinkbox.kilo_end_link_api_ops_harden import end_link_api_ops_harden_contract_summary
    from thinkbox.kilo_control_plane_e2e_deepen import control_plane_e2e_deepen_contract_summary
    from thinkbox.kilo_governance_evidence_live_proof_readiness import (
        governance_evidence_live_proof_readiness_contract_summary,
    )
    from thinkbox.kilo_receipt_chain_end_link_era_close import (
        receipt_chain_end_link_era_close_contract_summary,
    )
    from thinkbox.kilo_pr165_combined_harden_era_chronicle import (
        pr165_combined_harden_era_chronicle_contract_summary,
    )
    from thinkbox.kilo_pr166_combined_post165_lane import (
        pr166_combined_post165_lane_contract_summary,
    )
    from thinkbox.kilo_pr167_combined_post166_lane import (
        pr167_combined_post166_lane_contract_summary,
    )
    from thinkbox.kilo_post_season_harden import post_season_harden_contract_summary
    from thinkbox.kilo_proof_schema import proof_schema_contract_summary
    from thinkbox.kilo_swarm_instrumentation import swarm_instrumentation_contract_summary

    runbook_raw = load_text(runbook_path())
    runbook_scan = _runbook_text_for_claim_scan(runbook_raw)
    env_summary = env_matrix_contract_summary()
    substrate_summary = substrate_checklist_contract_summary()
    governance_summary = governance_evidence_contract_summary()
    mercury_summary = mercury_hermetic_contract_summary()
    swarm_summary = swarm_instrumentation_contract_summary()
    proof_schema_summary = proof_schema_contract_summary()
    dashboard_slots_summary = dashboard_slots_contract_summary()
    live_proof_exec_summary = live_proof_exec_contract_summary()
    post_season_summary = post_season_harden_contract_summary()
    live_smoke_summary = live_smoke_evidence_contract_summary()
    live_smoke_operator_summary = live_smoke_operator_contract_summary()
    control_plane_api_summary = control_plane_api_contract_summary()
    receipt_chain_etag_summary = receipt_chain_etag_contract_summary()
    dashboard_receipt_chain_bind_summary = dashboard_receipt_chain_bind_contract_summary()
    api_ops_harden_summary = api_ops_harden_contract_summary()
    end_link_deepen_summary = end_link_deepen_contract_summary()
    end_link_operator_ux_summary = end_link_operator_ux_contract_summary()
    receipt_chain_end_link_docs_summary = receipt_chain_end_link_docs_contract_summary()
    end_link_api_ops_harden_summary = end_link_api_ops_harden_contract_summary()
    receipt_chain_end_link_era_close_summary = receipt_chain_end_link_era_close_contract_summary()
    control_plane_e2e_deepen_summary = control_plane_e2e_deepen_contract_summary()
    governance_evidence_live_proof_readiness_summary = (
        governance_evidence_live_proof_readiness_contract_summary()
    )
    pr165_combined_summary = pr165_combined_harden_era_chronicle_contract_summary()
    pr166_combined_summary = pr166_combined_post165_lane_contract_summary()
    pr167_combined_summary = pr167_combined_post166_lane_contract_summary()
    return {
        "arc_pr_count": len(ARC_GATES),
        "arc_pr_first": ARC_GATES[0].pr_number,
        "arc_pr_last": ARC_GATES[-1].pr_number,
        "missing_spine_docs": missing_spine_docs(),
        "missing_runbook_headings": missing_runbook_headings(runbook_raw),
        "forbidden_literals_in_runbook": find_forbidden_literal_claims(runbook_scan),
        "affirmative_kilo_claims_in_runbook": find_affirmative_kilo_live_claims(runbook_scan),
        "four_state_max": "TEST_VERIFIED",
        "live_proof_in_this_pr": False,
        "pr141_gate_id": (gate_for_pr(141).gate_id if gate_for_pr(141) else None),
        "pr142_gate_id": (gate_for_pr(142).gate_id if gate_for_pr(142) else None),
        "pr143_gate_id": (gate_for_pr(143).gate_id if gate_for_pr(143) else None),
        "pr145_gate_id": (gate_for_pr(145).gate_id if gate_for_pr(145) else None),
        "pr146_gate_id": (gate_for_pr(146).gate_id if gate_for_pr(146) else None),
        "pr147_gate_id": (gate_for_pr(147).gate_id if gate_for_pr(147) else None),
        "pr148_gate_id": (gate_for_pr(148).gate_id if gate_for_pr(148) else None),
        "pr149_gate_id": (gate_for_pr(149).gate_id if gate_for_pr(149) else None),
        "pr150_gate_id": (gate_for_pr(150).gate_id if gate_for_pr(150) else None),
        "arc_season_complete": True,
        "env_matrix": env_summary,
        "substrate_checklist": substrate_summary,
        "governance_evidence": governance_summary,
        "mercury_hermetic": mercury_summary,
        "swarm_instrumentation": swarm_summary,
        "proof_schema": proof_schema_summary,
        "dashboard_slots": dashboard_slots_summary,
        "live_proof_exec": live_proof_exec_summary,
        "post_season_harden": post_season_summary,
        "pr151_gate_id": post_season_summary.get("pr151_gate_id"),
        "live_smoke_evidence": live_smoke_summary,
        "pr152_gate_id": live_smoke_summary.get("pr152_gate_id"),
        "live_smoke_operator": live_smoke_operator_summary,
        "pr153_gate_id": live_smoke_operator_summary.get("pr153_gate_id"),
        "control_plane_api": control_plane_api_summary,
        "pr154_gate_id": control_plane_api_summary.get("pr154_gate_id"),
        "receipt_chain_etag": receipt_chain_etag_summary,
        "pr155_gate_id": receipt_chain_etag_summary.get("pr155_gate_id"),
        "dashboard_receipt_chain_bind": dashboard_receipt_chain_bind_summary,
        "pr156_gate_id": dashboard_receipt_chain_bind_summary.get("pr156_gate_id"),
        "api_ops_harden": api_ops_harden_summary,
        "pr157_gate_id": api_ops_harden_summary.get("pr157_gate_id"),
        "end_link_deepen": end_link_deepen_summary,
        "pr158_gate_id": end_link_deepen_summary.get("pr158_gate_id"),
        "end_link_operator_ux": end_link_operator_ux_summary,
        "pr159_gate_id": end_link_operator_ux_summary.get("pr159_gate_id"),
        "receipt_chain_end_link_docs": receipt_chain_end_link_docs_summary,
        "pr160_gate_id": receipt_chain_end_link_docs_summary.get("pr160_gate_id"),
        "end_link_api_ops_harden": end_link_api_ops_harden_summary,
        "pr161_gate_id": end_link_api_ops_harden_summary.get("pr161_gate_id"),
        "receipt_chain_end_link_era_close": receipt_chain_end_link_era_close_summary,
        "control_plane_e2e_deepen": control_plane_e2e_deepen_summary,
        "pr162_gate_id": control_plane_e2e_deepen_summary.get("pr162_gate_id"),
        "governance_evidence_live_proof_readiness": governance_evidence_live_proof_readiness_summary,
        "pr164_gate_id": governance_evidence_live_proof_readiness_summary.get("pr164_gate_id"),
        "pr165_combined_harden_era_chronicle": pr165_combined_summary,
        "pr165_gate_id": pr165_combined_summary.get("pr165_gate_id"),
        "pr166_combined_post165_lane": pr166_combined_summary,
        "pr166_gate_id": pr166_combined_summary.get("pr166_gate_id"),
        "pr167_combined_post166_lane": pr167_combined_summary,
        "pr167_gate_id": pr167_combined_summary.get("pr167_gate_id"),
    }
