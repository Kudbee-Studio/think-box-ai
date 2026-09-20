"""Emit proof bundle under data/proofs/demo-<id>/ (reuses #99 export)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from thinkbox.agent.control_plane.store import ActionReceiptStore
from thinkbox.agent.control_plane.export import export_proof_bundle
from thinkbox.agent.control_plane.demo_record import DemoRunRecord, save_run
from thinkbox.agent.control_plane.verify_chain import verify_chain

logger = logging.getLogger(__name__)

PROOFS_DIR = Path("data/proofs")


def emit_proof_bundle(
    store: ActionReceiptStore,
    run_id: str,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    """Export proof bundle for a demo run."""
    target = output_dir or PROOFS_DIR / f"demo-{run_id}"
    target = Path(target)
    target.mkdir(parents=True, exist_ok=True)
    bundle = export_proof_bundle(store, output_dir=target, prefix="demo")
    result = verify_chain(store)
    logger.info("Emitted proof bundle for %s: valid=%s", run_id, result.valid)
    return {
        "run_id": run_id,
        **bundle,
        "chain_valid": result.valid,
    }


def write_run_record_with_proof(
    store: ActionReceiptStore,
    conn: Any,  # sqlite3.Connection
    record: DemoRunRecord,
) -> dict[str, Any]:
    """Save run record then emit proof bundle.

    Note: not atomic — if save_run succeeds but emit_proof_bundle fails,
    the run record persists without a proof bundle. Callers should verify
    chain_valid after both operations complete.
    """
    save_run(conn, record)
    bundle = emit_proof_bundle(store, record.run_id)
    return bundle
