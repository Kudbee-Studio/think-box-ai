"""Hermetic receipt / proof bind helpers (PR #179 F24)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class ReceiptBindProof:
    receipt_id: str
    payload_sha256: str
    bound: bool


def bind_receipt_hermetic(receipt_id: str, payload: Mapping[str, Any]) -> ReceiptBindProof:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    digest = hashlib.sha256(canonical).hexdigest()
    return ReceiptBindProof(receipt_id=receipt_id, payload_sha256=digest, bound=True)
