"""Import + offline verify a proof bundle (no network)."""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

from thinkbox.agent.control_plane.store import ActionReceiptStore
from thinkbox.agent.control_plane.verify_chain import verify_chain, ChainResult

logger = logging.getLogger(__name__)


def import_bundle(
    store: ActionReceiptStore,
    jsonl_path: str | Path,
) -> dict[str, Any]:
    """Import receipts from a JSONL file into the store (offline, no network)."""
    path = Path(jsonl_path)
    if not path.exists():
        raise FileNotFoundError(f"Bundle not found: {jsonl_path}")

    imported = 0
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        # Validate required fields
        for field_name in ("receipt_id", "action", "status", "reason", "evidence_label", "prev_hash", "entry_hash"):
            if field_name not in record:
                raise ValueError(f"Missing field {field_name} in bundle record")
        # Re-hydrate into store via raw SQL to preserve chain
        with store._lock:
            store._conn.execute(
                "INSERT OR IGNORE INTO receipts (receipt_id, action, status, reason, evidence_label, timestamp, prev_hash, entry_hash, metadata) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    record["receipt_id"],
                    record["action"],
                    record["status"],
                    record["reason"],
                    record["evidence_label"],
                    record.get("timestamp", ""),
                    record["prev_hash"],
                    record["entry_hash"],
                    json.dumps(record.get("metadata", {})),
                ),
            )
            store._conn.commit()
        imported += 1

    logger.info("Imported %d receipts from %s", imported, path)
    return {"imported": imported, "path": str(path)}


def verify_bundle_offline(
    jsonl_path: str | Path,
) -> dict[str, Any]:
    """Verify a JSONL bundle offline — check sha256 manifest and chain integrity."""
    path = Path(jsonl_path)
    if not path.exists():
        raise FileNotFoundError(f"Bundle not found: {jsonl_path}")

    records: list[dict[str, Any]] = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        records.append(json.loads(line))

    # Compute sha256 of the JSONL content
    content = path.read_text()
    sha256 = hashlib.sha256(content.encode()).hexdigest()

    # Verify chain
    prev = "GENESIS"
    chain_valid = True
    for i, record in enumerate(records):
        if record.get("prev_hash") != prev:
            chain_valid = False
            break
        payload = {k: record.get(k, "") for k in (
            "receipt_id", "action", "status", "reason", "evidence_label",
            "timestamp", "prev_hash",
        )}
        payload["metadata"] = record.get("metadata", {})
        expected = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()[:32]
        if expected != record.get("entry_hash", ""):
            chain_valid = False
            break
        prev = record["entry_hash"]

    return {
        "sha256": sha256,
        "receipt_count": len(records),
        "chain_valid": chain_valid,
        "offline": True,
    }
