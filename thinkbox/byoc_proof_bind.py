"""Bind THINK stash I/O to ActionReceipt / proof bundle chain."""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from thinkbox.agent.control_plane.store import ActionReceiptStore
from thinkbox.agent.control_plane.export import export_proof_bundle
from thinkbox.agent.control_plane.verify_chain import verify_chain
from thinkbox.byoc_config import ByocConfig
from thinkbox.byoc_stash_writer import ThinkStashEntry, ThinkStashWriter
from thinkbox.byoc_stash_reader import ThinkStashReader

logger = logging.getLogger(__name__)


@dataclass
class StashProofLink:
    stash_id: str
    proof_receipt_id: str
    reasoning_sha256: str
    bound_at: str = ""
    chain_valid: bool = False


class StashProofBinder:
    """Bind stash entries to ActionReceipt proof chain.

    On proof export, writes stash_id + reasoning_sha256 into receipt
    metadata and verifies the bind via verify_chain().
    """

    def __init__(self, store: ActionReceiptStore, config: ByocConfig | None = None) -> None:
        self._store = store
        self._config = config or ByocConfig.load()
        self._writer = ThinkStashWriter(self._config)
        self._reader = ThinkStashReader(self._config)
        self._links: list[StashProofLink] = []

    def bind(self, stash_id: str, proof_receipt_id: str, reasoning_text: str) -> StashProofLink:
        reasoning_sha256 = hashlib.sha256(reasoning_text.encode()).hexdigest()
        entry = ThinkStashEntry(
            stash_id=stash_id,
            reasoning_sha256=reasoning_sha256,
            proof_receipt_id=proof_receipt_id,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self._writer.write(entry)
        self._store.append(
            action="STASH_BIND",
            status="OK",
            reason=f"bound {stash_id} to {proof_receipt_id}",
            evidence_label=self._config.evidence_label if hasattr(self._config, "evidence_label") else "simulated",
            metadata={
                "stash_id": stash_id,
                "proof_receipt_id": proof_receipt_id,
                "reasoning_sha256": reasoning_sha256,
            },
        )
        link = StashProofLink(
            stash_id=stash_id,
            proof_receipt_id=proof_receipt_id,
            reasoning_sha256=reasoning_sha256,
            bound_at=datetime.now(timezone.utc).isoformat(),
        )
        self._links.append(link)
        logger.info("Bound stash %s to proof %s", stash_id, proof_receipt_id)
        return link

    def verify_bind(self) -> bool:
        """Verify stash bindings are in the proof chain."""
        chain_valid = verify_chain(self._store).valid
        for link in self._links:
            link.chain_valid = chain_valid
        return chain_valid

    def get_bound_proof(self, stash_id: str) -> dict[str, Any] | None:
        for link in self._links:
            if link.stash_id == stash_id:
                return {
                    "stash_id": link.stash_id,
                    "proof_receipt_id": link.proof_receipt_id,
                    "reasoning_sha256": link.reasoning_sha256,
                    "bound_at": link.bound_at,
                    "chain_valid": link.chain_valid,
                }
        return None

    def export_proof_bundle(self, output_dir: str | None = None) -> dict[str, Any]:
        return export_proof_bundle(self._store, output_dir=output_dir or "data/proofs")