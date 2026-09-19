"""ActionReceipt: signed record of every control-plane side effect with hash chain."""

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ActionReceipt:
    action_type: str
    agent_id: str
    status: str  # "OK" | "FAILED"
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    previous_hash: str = ""
    signature: str = ""

    def compute_hash(self) -> str:
        payload = json.dumps({
            "action_type": self.action_type,
            "agent_id": self.agent_id,
            "status": self.status,
            "metadata": self.metadata,
            "previous_hash": self.previous_hash,
        }, sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()


class ReceiptChain:
    """Hash-chained ledger of ActionReceipts."""

    def __init__(self):
        self._receipts: List[ActionReceipt] = []
        self._chain_hashes: List[str] = ["0" * 64]  # genesis

    def append(self, receipt: ActionReceipt) -> str:
        """Append receipt; returns its hash."""
        prev_hash = self._chain_hashes[-1] if self._chain_hashes else "0" * 64
        receipt.previous_hash = prev_hash
        receipt.signature = receipt.compute_hash()
        self._receipts.append(receipt)
        self._chain_hashes.append(receipt.signature)
        return receipt.signature

    def verify(self) -> bool:
        """Verify hash chain integrity."""
        for i, receipt in enumerate(self._receipts):
            expected_prev = self._chain_hashes[i]
            if receipt.previous_hash != expected_prev:
                logger.warning(f"Chain broken at index {i}")
                return False
            if receipt.signature != receipt.compute_hash():
                logger.warning(f"Invalid signature at index {i}")
                return False
        return True

    @property
    def receipts(self) -> List[ActionReceipt]:
        return list(self._receipts)

    @property
    def last_hash(self) -> str:
        return self._chain_hashes[-1] if self._chain_hashes else "0" * 64

    def size(self) -> int:
        return len(self._receipts)
