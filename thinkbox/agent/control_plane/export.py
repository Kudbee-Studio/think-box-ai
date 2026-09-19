"""Export proof bundle: JSONL receipts + manifest sha256 under data/proofs/."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from thinkbox.agent.control_plane.store import ActionReceiptStore

logger = logging.getLogger(__name__)

PROOFS_DIR = Path("data/proofs")


def export_proof_bundle(
    store: ActionReceiptStore,
    output_dir: str | Path = PROOFS_DIR,
    prefix: str = "proof",
) -> dict[str, Any]:
    """Export all receipts as JSONL plus a manifest with sha256."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    jsonl_path = output_path / f"{prefix}_{timestamp}.jsonl"
    manifest_path = output_path / f"{prefix}_{timestamp}.manifest.json"

    records: list[dict[str, Any]] = []
    with store._lock:
        rows = store._conn.execute(
            "SELECT receipt_id, action, status, reason, evidence_label, timestamp, prev_hash, entry_hash, metadata FROM receipts ORDER BY rowid"
        ).fetchall()

    for row in rows:
        receipt_id, action, status, reason, evidence_label, timestamp_str, prev_hash, entry_hash, metadata_str = row
        records.append({
            "receipt_id": receipt_id,
            "action": action,
            "status": status,
            "reason": reason,
            "evidence_label": evidence_label,
            "timestamp": timestamp_str,
            "prev_hash": prev_hash,
            "entry_hash": entry_hash,
            "metadata": json.loads(metadata_str),
        })

    jsonl_content = ""
    for record in records:
        jsonl_content += json.dumps(record, sort_keys=True) + "\n"
    jsonl_path.write_text(jsonl_content)

    sha256 = hashlib.sha256(jsonl_content.encode()).hexdigest()
    manifest = {
        "schema_version": "1.0",
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "receipt_count": len(records),
        "sha256": sha256,
        "chain_valid": store.verify(),
        "source": "ActionReceiptStore",
    }
    manifest_path.write_text(json.dumps(manifest, indent=2))

    logger.info(
        "Exported %d receipts to %s (sha256=%s)",
        len(records),
        jsonl_path,
        sha256[:16],
    )
    return {
        "jsonl": str(jsonl_path),
        "manifest": str(manifest_path),
        "receipt_count": len(records),
        "sha256": sha256,
        "chain_valid": manifest["chain_valid"],
    }
