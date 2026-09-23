"""Receipt-chain / END_LINK era audit close helpers (PR #162).

Validates consolidated audit pack for PR #154–#161. Hermetic only.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from thinkbox.kilo_live_proof_readiness import REPO_ROOT

__all__ = (
    "ERA_CLOSE_LABEL",
    "ERA_CLOSE_VERSION",
    "ERA_CONSOLIDATED_154_161_REL",
    "ERA_GATE_SPECS",
    "EraGateSpec",
    "era_close_contract_snippet",
    "load_era_consolidated_pack",
    "validate_era_consolidated_154_161_pack",
)

ERA_CLOSE_LABEL = "receipt-chain-end-link-era-close"
ERA_CLOSE_VERSION = "1.0.0"

ERA_CONSOLIDATED_154_161_REL = Path("docs/audit/passes/2026-09-23-pr154-161-era-consolidated.json")


@dataclass(frozen=True)
class EraGateSpec:
    pr_number: int
    gate_id: str
    pass_file: str


ERA_GATE_SPECS: tuple[EraGateSpec, ...] = (
    EraGateSpec(154, "control-plane-api", "passes/2026-09-23-pr154.json"),
    EraGateSpec(155, "receipt-chain-etag", "passes/2026-09-23-pr155.json"),
    EraGateSpec(156, "dashboard-receipt-chain-bind", "passes/2026-09-23-pr156.json"),
    EraGateSpec(157, "api-ops-harden", "passes/2026-09-23-pr157.json"),
    EraGateSpec(158, "end-link-deepen", "passes/2026-09-23-pr158.json"),
    EraGateSpec(159, "end-link-operator-ux", "passes/2026-09-23-pr159.json"),
    EraGateSpec(160, "receipt-chain-end-link-docs", "passes/2026-09-23-pr160.json"),
    EraGateSpec(161, "end-link-api-ops-harden", "passes/2026-09-23-pr161.json"),
)


@dataclass(frozen=True)
class EraPackViolation:
    code: str
    message: str
    path: str | None = None


def load_era_consolidated_pack(
    rel: Path = ERA_CONSOLIDATED_154_161_REL,
) -> dict[str, Any]:
    """Load consolidated era JSON from repo root."""
    path = REPO_ROOT / rel
    return json.loads(path.read_text(encoding="utf-8"))


def validate_era_consolidated_154_161_pack(
    doc: Mapping[str, Any],
    *,
    specs: Sequence[EraGateSpec] = ERA_GATE_SPECS,
) -> list[EraPackViolation]:
    """Fail-closed validation for PR #154–#161 era honesty pack."""
    violations: list[EraPackViolation] = []
    if doc.get("live_verified") is True:
        violations.append(EraPackViolation(code="era_live_verified", message="live_verified must be false"))
    if doc.get("live_api_called") is True:
        violations.append(EraPackViolation(code="era_live_api", message="live_api_called must be false"))
    if doc.get("four_state_max") != "TEST_VERIFIED":
        violations.append(EraPackViolation(code="four_state", message="four_state_max must be TEST_VERIFIED"))
    if doc.get("pr_range_first") != specs[0].pr_number:
        violations.append(EraPackViolation(code="pr_range_first", message="pr_range_first mismatch"))
    if doc.get("pr_range_last") != specs[-1].pr_number:
        violations.append(EraPackViolation(code="pr_range_last", message="pr_range_last mismatch"))

    gates = doc.get("gates") or []
    if len(gates) != len(specs):
        violations.append(
            EraPackViolation(
                code="era_gate_count",
                message=f"expected {len(specs)} gates, got {len(gates)}",
            ),
        )

    by_pr = {int(g.get("pr_number", -1)): g for g in gates if isinstance(g, dict)}
    for spec in specs:
        entry = by_pr.get(spec.pr_number)
        if entry is None:
            violations.append(
                EraPackViolation(code="era_gate_missing", message=f"missing pr {spec.pr_number}"),
            )
            continue
        if entry.get("gate_id") != spec.gate_id:
            violations.append(
                EraPackViolation(
                    code="era_gate_id",
                    message=f"pr{spec.pr_number} gate_id expected {spec.gate_id}",
                ),
            )
        if entry.get("live_verified") is True:
            violations.append(
                EraPackViolation(code="era_gate_live", message=f"pr{spec.pr_number} live_verified true"),
            )
        pass_rel = str(entry.get("pass_file") or spec.pass_file)
        pass_path = REPO_ROOT / "docs/audit" / pass_rel
        if not pass_path.is_file():
            violations.append(
                EraPackViolation(code="era_pass_missing", message=f"missing {pass_rel}", path=pass_rel),
            )
        else:
            body = json.loads(pass_path.read_text(encoding="utf-8"))
            if body.get("live_verified") is True or body.get("live_api_called") is True:
                violations.append(
                    EraPackViolation(
                        code="pass_honesty",
                        message=f"{pass_rel} live flags must be false",
                        path=pass_rel,
                    ),
                )
    return violations


def era_close_contract_snippet() -> dict[str, Any]:
    return {
        "receipt_chain_end_link_era_close": ERA_CLOSE_LABEL,
        "receipt_chain_end_link_era_close_version": ERA_CLOSE_VERSION,
        "era_gate_count": len(ERA_GATE_SPECS),
        "pr_range_first": ERA_GATE_SPECS[0].pr_number,
        "pr_range_last": ERA_GATE_SPECS[-1].pr_number,
        "live_verified": False,
        "live_api_called": False,
        "four_state_max": "TEST_VERIFIED",
    }
