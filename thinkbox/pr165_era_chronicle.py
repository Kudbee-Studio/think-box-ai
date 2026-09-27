"""PR #154–#164 era chronicle pack helpers (PR #165 theme D).

Append-only honesty pack for control-plane / receipt-chain / governance-evidence era.
Hermetic only — ``live_verified: false``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from thinkbox.kilo_live_proof_readiness import REPO_ROOT
from thinkbox.receipt_chain_end_link_era_close import ERA_GATE_SPECS, EraGateSpec

__all__ = (
    "CHRONICLE_LABEL",
    "CHRONICLE_VERSION",
    "ERA_154_164_PACK_REL",
    "ChronicleGateSpec",
    "CHRONICLE_GATE_SPECS",
    "chronicle_contract_snippet",
    "load_era_154_164_chronicle_pack",
    "validate_era_154_164_chronicle_pack",
)

CHRONICLE_LABEL = "pr165-era-chronicle-154-164"
CHRONICLE_VERSION = "1.0.0"

ERA_154_164_PACK_REL = Path("docs/audit/passes/2026-09-23-pr154-164-era-chronicle.json")


@dataclass(frozen=True)
class ChronicleGateSpec:
    pr_number: int
    gate_id: str
    pass_file: str
    live_proved: bool = False


CHRONICLE_GATE_SPECS: tuple[ChronicleGateSpec, ...] = tuple(
    ChronicleGateSpec(s.pr_number, s.gate_id, s.pass_file, live_proved=False)
    for s in ERA_GATE_SPECS
) + (
    ChronicleGateSpec(162, "receipt-chain-end-link-era-close", "passes/2026-09-23-pr162.json"),
    ChronicleGateSpec(162, "control-plane-e2e-deepen", "passes/2026-09-23-pr162.json"),
    ChronicleGateSpec(164, "governance-evidence-live-proof-readiness", "passes/2026-09-23-pr164.json"),
)


@dataclass(frozen=True)
class ChronicleViolation:
    code: str
    message: str
    path: str | None = None


def load_era_154_164_chronicle_pack(
    rel: Path = ERA_154_164_PACK_REL,
) -> dict[str, Any]:
    path = REPO_ROOT / rel
    return json.loads(path.read_text(encoding="utf-8"))


def validate_era_154_164_chronicle_pack(
    doc: Mapping[str, Any],
    *,
    specs: Sequence[ChronicleGateSpec] = CHRONICLE_GATE_SPECS,
) -> list[ChronicleViolation]:
    violations: list[ChronicleViolation] = []
    if doc.get("live_verified") is True:
        violations.append(ChronicleViolation(code="live_verified", message="must be false"))
    if doc.get("live_api_called") is True:
        violations.append(ChronicleViolation(code="live_api_called", message="must be false"))
    if doc.get("four_state_max") != "TEST_VERIFIED":
        violations.append(ChronicleViolation(code="four_state", message="four_state_max"))
    if doc.get("chronicle_label") != CHRONICLE_LABEL:
        violations.append(ChronicleViolation(code="chronicle_label", message="label mismatch"))
    if doc.get("pr_range_first") != 154:
        violations.append(ChronicleViolation(code="pr_range_first", message="expected 154"))
    if doc.get("pr_range_last") != 164:
        violations.append(ChronicleViolation(code="pr_range_last", message="expected 164"))
    gates = doc.get("gates") or []
    if not isinstance(gates, list):
        violations.append(ChronicleViolation(code="gates_type", message="gates must be array"))
        return violations
    indexed: set[tuple[int, str]] = set()
    for g in gates:
        if not isinstance(g, Mapping):
            continue
        try:
            pr_n = int(g.get("pr_number", -1))
        except (TypeError, ValueError):
            continue
        gid = str(g.get("gate_id") or "")
        indexed.add((pr_n, gid))
        if g.get("live_proved") is True:
            violations.append(
                ChronicleViolation(
                    code="gate_live_proved",
                    message=f"pr {pr_n} gate {gid} must not claim live_proved",
                )
            )
    for spec in specs:
        if (spec.pr_number, spec.gate_id) not in indexed:
            violations.append(
                ChronicleViolation(
                    code="gate_missing",
                    message=f"missing gate pr {spec.pr_number} {spec.gate_id}",
                )
            )
    not_live = doc.get("explicitly_not_live_proved") or []
    if not isinstance(not_live, list) or len(not_live) < 3:
        violations.append(
            ChronicleViolation(code="not_live_list", message="explicitly_not_live_proved required")
        )
    return violations


def chronicle_contract_snippet() -> dict[str, Any]:
    return {
        "chronicle_label": CHRONICLE_LABEL,
        "chronicle_version": CHRONICLE_VERSION,
        "pr_range": [154, 164],
        "gate_spec_count": len(CHRONICLE_GATE_SPECS),
        "live_verified": False,
        "live_api_called": False,
        "four_state_max": "TEST_VERIFIED",
    }
