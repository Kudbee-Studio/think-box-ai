"""Receipt-chain / END_LINK season harden helpers (PR #165 theme C).

Extends era-close validators with post-#164 honesty checks. Hermetic only — no HTTP.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from thinkbox.end_link_deepen import END_LINK_DEEPEN_LABEL
from thinkbox.kilo_receipt_chain_etag import GATE_ID as RECEIPT_CHAIN_GATE_ID
from thinkbox.receipt_chain_end_link_era_close import ERA_CLOSE_LABEL

__all__ = (
    "SEASON_HARDEN_LABEL",
    "SEASON_HARDEN_VERSION",
    "SeasonHardenViolation",
    "end_link_etag_token_valid",
    "receipt_chain_season_contract_snippet",
    "validate_end_link_etag_pairs",
    "validate_receipt_chain_season_document",
)

SEASON_HARDEN_LABEL = "receipt-chain-end-link-season-harden"
SEASON_HARDEN_VERSION = "1.0.0"

_ETAG_RE = re.compile(r'^W/"[a-f0-9]{8,64}"$|^[a-f0-9]{8,64}$', re.IGNORECASE)


@dataclass(frozen=True)
class SeasonHardenViolation:
    code: str
    message: str
    path: str | None = None


def end_link_etag_token_valid(token: str) -> bool:
    trimmed = (token or "").strip()
    if not trimmed:
        return False
    return bool(_ETAG_RE.match(trimmed))


def validate_end_link_etag_pairs(
    receipt_ids: Sequence[str],
    etags: Sequence[str],
) -> list[SeasonHardenViolation]:
    violations: list[SeasonHardenViolation] = []
    if len(receipt_ids) != len(etags):
        violations.append(
            SeasonHardenViolation(
                code="length_mismatch",
                message="receipt_ids and etags length mismatch",
            )
        )
    for idx, (rid, etag) in enumerate(zip(receipt_ids, etags)):
        if not (rid or "").strip():
            violations.append(
                SeasonHardenViolation(
                    code="receipt_empty",
                    message=f"receipt_id empty at {idx}",
                    path=f"receipt_ids[{idx}]",
                )
            )
        if not end_link_etag_token_valid(str(etag)):
            violations.append(
                SeasonHardenViolation(
                    code="etag_invalid",
                    message=f"etag token invalid at {idx}",
                    path=f"etags[{idx}]",
                )
            )
    return violations


def validate_receipt_chain_season_document(doc: Mapping[str, Any]) -> list[SeasonHardenViolation]:
    """Fail-closed season harden document validator."""
    violations: list[SeasonHardenViolation] = []
    if doc.get("live_verified") is True:
        violations.append(SeasonHardenViolation(code="live_verified", message="must be false"))
    if doc.get("live_api_called") is True:
        violations.append(SeasonHardenViolation(code="live_api_called", message="must be false"))
    if doc.get("four_state_max") != "TEST_VERIFIED":
        violations.append(SeasonHardenViolation(code="four_state", message="four_state_max"))
    if doc.get("season_harden_label") != SEASON_HARDEN_LABEL:
        violations.append(SeasonHardenViolation(code="label", message="season_harden_label"))
    if doc.get("receipt_chain_gate_id") != RECEIPT_CHAIN_GATE_ID:
        violations.append(
            SeasonHardenViolation(code="receipt_chain_gate", message="receipt_chain_gate_id")
        )
    if doc.get("era_close_label") != ERA_CLOSE_LABEL:
        violations.append(SeasonHardenViolation(code="era_close_label", message="era_close_label"))
    if doc.get("end_link_deepen_label") != END_LINK_DEEPEN_LABEL:
        violations.append(
            SeasonHardenViolation(code="end_link_deepen", message="end_link_deepen_label")
        )
    pairs = doc.get("receipt_etag_pairs")
    if isinstance(pairs, list):
        rids: list[str] = []
        etags: list[str] = []
        for idx, item in enumerate(pairs):
            if not isinstance(item, Mapping):
                violations.append(
                    SeasonHardenViolation(
                        code="pair_shape",
                        message=f"pair {idx} not object",
                    )
                )
                continue
            rids.append(str(item.get("receipt_id") or ""))
            etags.append(str(item.get("etag") or ""))
        violations.extend(validate_end_link_etag_pairs(rids, etags))
    return violations


def receipt_chain_season_contract_snippet() -> dict[str, Any]:
    return {
        "season_harden_label": SEASON_HARDEN_LABEL,
        "season_harden_version": SEASON_HARDEN_VERSION,
        "receipt_chain_gate_id": RECEIPT_CHAIN_GATE_ID,
        "era_close_label": ERA_CLOSE_LABEL,
        "end_link_deepen_label": END_LINK_DEEPEN_LABEL,
        "live_verified": False,
        "live_api_called": False,
        "four_state_max": "TEST_VERIFIED",
    }
