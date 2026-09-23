"""Live-proof operator prep deepen helpers (PR #166 theme A).

Extends PR #152/#153 operator paths with fail-closed readiness reporting when
founder credentials are absent. Hermetic only — no HTTP.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Mapping

from thinkbox.kilo_live_proof_exec import FOUNDER_ACK_ENV
from thinkbox.kilo_live_smoke_operator import GATE_ID as OPERATOR_GATE_ID
from thinkbox.kilo_substrate_checklist import BOX_URL_ENV, redact_box_url

__all__ = (
    "OPERATOR_PREP_DEEPEN_LABEL",
    "OPERATOR_PREP_DEEPEN_VERSION",
    "FounderCredentialReadiness",
    "founder_credential_readiness",
    "operator_prep_checklist_items",
    "operator_prep_contract_snippet",
    "prep_deepen_markers_present",
)

OPERATOR_PREP_DEEPEN_LABEL = "live-proof-operator-prep-deepen"
OPERATOR_PREP_DEEPEN_VERSION = "1.0.0"

_REQUIRED_ENVS: tuple[str, ...] = (
    BOX_URL_ENV,
    "UPSTASH_PUBLIC_BOX_TOKEN",
    FOUNDER_ACK_ENV,
)

_CHECKLIST_ITEMS: tuple[str, ...] = (
    "governance_token_present_for_side_effects",
    "box_url_configured",
    "box_token_configured",
    "founder_swarm_live_ack",
    "smoke_evidence_gate_closed_hermetic",
    "smoke_operator_gate_closed_hermetic",
    "audit_flip_refused_without_predicates",
    "no_live_http_in_ci",
)


@dataclass(frozen=True)
class FounderCredentialReadiness:
    """Redacted founder-runtime readiness (values never exported)."""

    box_url_present: bool
    box_token_present: bool
    founder_ack_present: bool
    ready_for_bounded_live_smoke: bool
    missing: tuple[str, ...]
    redacted_box_url_hint: str | None


def founder_credential_readiness(
    environ: Mapping[str, str] | None = None,
) -> FounderCredentialReadiness:
    """Evaluate env presence for founder-run live proof (no secret values)."""
    env = environ if environ is not None else os.environ
    box_url = (env.get(BOX_URL_ENV) or "").strip()
    box_token = (env.get("UPSTASH_PUBLIC_BOX_TOKEN") or "").strip()
    ack = (env.get(FOUNDER_ACK_ENV) or "").strip()
    missing: list[str] = []
    if not box_url:
        missing.append(BOX_URL_ENV)
    if not box_token:
        missing.append("UPSTASH_PUBLIC_BOX_TOKEN")
    if not ack:
        missing.append(FOUNDER_ACK_ENV)
    ready = not missing
    hint = redact_box_url(box_url) if box_url else None
    return FounderCredentialReadiness(
        box_url_present=bool(box_url),
        box_token_present=bool(box_token),
        founder_ack_present=bool(ack),
        ready_for_bounded_live_smoke=ready,
        missing=tuple(missing),
        redacted_box_url_hint=hint,
    )


def operator_prep_checklist_items() -> tuple[str, ...]:
    """Stable checklist keys for operator prep deepen gate."""
    return _CHECKLIST_ITEMS


def prep_deepen_markers_present(text: str) -> bool:
    """Return True when PR #166 theme A markers appear in module text."""
    needles = (
        OPERATOR_PREP_DEEPEN_LABEL,
        OPERATOR_GATE_ID,
        "founder_credential_readiness",
        "audit_flip_refused",
    )
    return all(n in text for n in needles)


def operator_prep_contract_snippet() -> dict[str, Any]:
    """Hermetic contract snippet for dashboards and audit passes."""
    readiness = founder_credential_readiness({})
    return {
        "label": OPERATOR_PREP_DEEPEN_LABEL,
        "version": OPERATOR_PREP_DEEPEN_VERSION,
        "operator_gate_id": OPERATOR_GATE_ID,
        "checklist_item_count": len(_CHECKLIST_ITEMS),
        "founder_ready": readiness.ready_for_bounded_live_smoke,
        "missing_env_keys": list(readiness.missing),
        "live_verified": False,
        "live_api_called": False,
        "four_state_max": "TEST_VERIFIED",
    }
