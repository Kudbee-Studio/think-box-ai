"""In-memory hermetic chain append (PR #182 F06)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from thinkbox.receipt_chain_deepen.errors import ReceiptChainDeepenError
from thinkbox.receipt_chain_deepen.hash_link import GENESIS_HASH, compute_entry_hash


@dataclass
class HermeticReceiptChain:
    """Append-only receipt chain for hermetic tests and dry-run."""

    max_entries: int = 256
    _entries: list[dict[str, Any]] = field(default_factory=list)
    _tail_hash: str = GENESIS_HASH

    def append(self, receipt_id: str, action: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        if len(self._entries) >= self.max_entries:
            raise ReceiptChainDeepenError("chain_full", "max entries exceeded")
        meta = dict(metadata or {})
        payload = {
            "receipt_id": receipt_id,
            "action": action,
            "status": "ok",
            "reason": "",
            "evidence_label": "simulated",
            "timestamp": meta.get("timestamp", "1970-01-01T00:00:00Z"),
            "prev_hash": self._tail_hash,
            "metadata": meta,
        }
        entry_hash = compute_entry_hash(payload)
        record = {**payload, "entry_hash": entry_hash}
        self._entries.append(record)
        self._tail_hash = entry_hash
        return dict(record)

    def entries(self) -> tuple[dict[str, Any], ...]:
        return tuple(self._entries)

    def tail_hash(self) -> str:
        return self._tail_hash


def append_receipt(
    chain: HermeticReceiptChain,
    receipt_id: str,
    action: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    out = chain.append(receipt_id, action, metadata)
    out["live_api_called"] = False
    return out
