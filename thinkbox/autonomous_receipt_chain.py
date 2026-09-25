"""Hermetic Trait Lab autonomous receipt chain (R01–R25).

Binds prep → session → autonomous receipt SHA256 triples into a signed index.
Verifies against store facts. No live APIs.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from core.memory.store import MemoryStore
from thinkbox.autonomous_workflow import (
    get_trait_lab_autonomous_workflow_receipt,
    list_trait_lab_autonomous_workflow_receipts,
)
from thinkbox.local_env_prep import get_trait_lab_local_env_prep_receipt
from thinkbox.memory_layers import MemoryLayerError, record_task_step, write_verified
from thinkbox.operator_session import get_trait_lab_operator_session_receipt

_CHAIN_KIND = "trait-lab-autonomous-receipt-chain"
_CHAIN_INDEX_KIND = "trait-lab-autonomous-receipt-chain-index"
_CHAIN_FACT_PREFIX = "trait-lab-auto-chain-"

TRAIT_LAB_AUTONOMOUS_RECEIPT_CHAIN_OPS: tuple[str, ...] = (
    "refuse_live",
    "require_provenance",
    "chain_row",
    "validate",
    "sign",
    "verify",
    "export_index",
    "verify_index",
    "list_chains",
    "count_chains",
    "has_chain",
    "page_chains",
    "digest",
    "etag",
    "public_row",
    "require_green_chain",
    "filter_by_prep",
    "filter_by_session",
    "filter_by_autonomous",
    "filter_by_agent",
    "rematch_index",
    "diff_indexes",
    "retain_best",
    "chain_from_receipt",
    "persist_index",
)


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _require_sha256(name: str, value: Any, *, code: str) -> str:
    sha = str(value or "").strip().lower()
    if len(sha) != 64 or any(ch not in "0123456789abcdef" for ch in sha):
        raise MemoryLayerError(code, f"{name} requires a 64-char hex sha256")
    return sha


def refuse_trait_lab_autonomous_receipt_chain_live(payload: Any) -> None:
    """R01 — chain payloads may not claim LIVE VERIFIED."""
    if isinstance(payload, dict) and payload.get("live_verified") is True:
        raise MemoryLayerError("live_claim", "autonomous receipt chain may not claim LIVE VERIFIED")


def require_trait_lab_autonomous_receipt_chain_provenance(*, agent_id: str, task_id: str) -> dict[str, Any]:
    """R02 — fail-closed without agent_id and task_id."""
    wanted_agent = str(agent_id or "").strip()
    wanted_task = str(task_id or "").strip()
    if not wanted_agent or not wanted_task:
        raise MemoryLayerError("missing_provenance", "receipt chain requires agent_id and task_id")
    return {"agent_id": wanted_agent, "task_id": wanted_task, "live_verified": False}


def trait_lab_autonomous_receipt_chain_row(
    *,
    prep_sha256: str,
    session_sha256: str,
    autonomous_sha256: str,
    status: str = "dry_run",
) -> dict[str, Any]:
    """R03 — one public chain row (unsigned)."""
    prep = _require_sha256("prep_sha256", prep_sha256, code="missing_prep_hash")
    session = _require_sha256("session_sha256", session_sha256, code="missing_session_hash")
    auto = _require_sha256("autonomous_sha256", autonomous_sha256, code="missing_autonomous_hash")
    stat = str(status or "dry_run").strip()
    if stat not in {"dry_run", "ready", "blocked", "planned"}:
        raise MemoryLayerError("invalid_status", f"unknown chain status {stat or '<empty>'}")
    return {
        "kind": _CHAIN_KIND,
        "prep_sha256": prep,
        "session_sha256": session,
        "autonomous_sha256": auto,
        "status": stat,
        "live_verified": False,
    }


def validate_trait_lab_autonomous_receipt_chain(row: Any) -> dict[str, Any]:
    """R04 — fail-closed check of one chain row."""
    if not isinstance(row, dict):
        raise MemoryLayerError("invalid_chain", "chain row must be an object")
    refuse_trait_lab_autonomous_receipt_chain_live(row)
    if row.get("kind") not in {None, _CHAIN_KIND}:
        raise MemoryLayerError("invalid_chain", "kind must be trait-lab-autonomous-receipt-chain")
    built = trait_lab_autonomous_receipt_chain_row(
        prep_sha256=str(row.get("prep_sha256") or ""),
        session_sha256=str(row.get("session_sha256") or ""),
        autonomous_sha256=str(row.get("autonomous_sha256") or ""),
        status=str(row.get("status") or "dry_run"),
    )
    return {**built, "valid": True}


def sign_trait_lab_autonomous_receipt_chain(row: Any) -> dict[str, Any]:
    """R05 — sign a validated chain row."""
    validated = validate_trait_lab_autonomous_receipt_chain(row)
    body = {
        "kind": _CHAIN_KIND,
        "prep_sha256": validated["prep_sha256"],
        "session_sha256": validated["session_sha256"],
        "autonomous_sha256": validated["autonomous_sha256"],
        "status": validated["status"],
        "live_verified": False,
    }
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {**body, "chain_sha256": hashlib.sha256(encoded).hexdigest(), "live_verified": False}


def verify_trait_lab_autonomous_receipt_chain(row: Any) -> dict[str, Any]:
    """R06 — rematch chain_sha256 over the stable row body."""
    if not isinstance(row, dict):
        raise MemoryLayerError("invalid_chain", "chain row must be an object")
    if row.get("kind") != _CHAIN_KIND:
        raise MemoryLayerError("invalid_chain", "kind must be trait-lab-autonomous-receipt-chain")
    refuse_trait_lab_autonomous_receipt_chain_live(row)
    sha = _require_sha256("chain_sha256", row.get("chain_sha256"), code="missing_chain_hash")
    body = validate_trait_lab_autonomous_receipt_chain(row)
    got = hashlib.sha256(
        json.dumps(
            {
                "kind": _CHAIN_KIND,
                "prep_sha256": body["prep_sha256"],
                "session_sha256": body["session_sha256"],
                "autonomous_sha256": body["autonomous_sha256"],
                "status": body["status"],
                "live_verified": False,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    if got != sha:
        raise MemoryLayerError("chain_mismatch", f"chain hashed {got[:12]} not {sha[:12]}")
    return {**body, "matched": True, "chain_sha256": sha, "live_verified": False}


def _chain_public_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "prep_sha256": row["prep_sha256"],
        "session_sha256": row["session_sha256"],
        "autonomous_sha256": row["autonomous_sha256"],
        "status": row["status"],
        "live_verified": False,
    }


def _index_body(chains: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "kind": _CHAIN_INDEX_KIND,
        "chains": chains,
        "count": len(chains),
        "live_verified": False,
    }


def export_trait_lab_autonomous_receipt_chain_index(
    store: MemoryStore,
    *,
    limit: int = 50,
) -> dict[str, Any]:
    """R07 — portable chain index from persisted autonomous receipts."""
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise MemoryLayerError("invalid_limit", "limit must be >= 1")
    listed = list_trait_lab_autonomous_workflow_receipts(store, limit=limit)
    chains: list[dict[str, Any]] = []
    for receipt in listed.get("receipts") or []:
        prep = str(receipt.get("prep_sha256") or "").strip().lower()
        session = str(receipt.get("session_sha256") or "").strip().lower()
        auto = str(receipt.get("autonomous_sha256") or "").strip().lower()
        if len(prep) != 64 or len(session) != 64 or len(auto) != 64:
            continue
        chains.append(
            _chain_public_row(
                {
                    "prep_sha256": prep,
                    "session_sha256": session,
                    "autonomous_sha256": auto,
                    "status": str(receipt.get("status") or "dry_run"),
                }
            )
        )
    body = _index_body(chains)
    refuse_trait_lab_autonomous_receipt_chain_live(body)
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        **body,
        "chain_index_sha256": hashlib.sha256(encoded).hexdigest(),
        "exported_at": _utc(),
        "live_verified": False,
    }


def verify_trait_lab_autonomous_receipt_chain_index(index: Any) -> dict[str, Any]:
    """R08 — rematch chain_index_sha256 over the stable index body."""
    if not isinstance(index, dict):
        raise MemoryLayerError("invalid_chain", "chain index must be an object")
    if index.get("kind") != _CHAIN_INDEX_KIND:
        raise MemoryLayerError("invalid_chain", "kind must be trait-lab-autonomous-receipt-chain-index")
    refuse_trait_lab_autonomous_receipt_chain_live(index)
    if not isinstance(index.get("chains"), list):
        raise MemoryLayerError("invalid_chain", "chains must be a list")
    sha = _require_sha256("chain_index_sha256", index.get("chain_index_sha256"), code="missing_index_hash")
    public = [_chain_public_row(row) for row in index["chains"] if isinstance(row, dict)]
    if len(public) != len(index["chains"]):
        raise MemoryLayerError("invalid_chain", "every chain row must be an object")
    for row in public:
        trait_lab_autonomous_receipt_chain_row(
            prep_sha256=row["prep_sha256"],
            session_sha256=row["session_sha256"],
            autonomous_sha256=row["autonomous_sha256"],
            status=row["status"],
        )
    body = _index_body(public)
    got = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    if got != sha:
        raise MemoryLayerError("chain_index_mismatch", f"index hashed {got[:12]} not {sha[:12]}")
    return {**body, "matched": True, "chain_index_sha256": sha, "live_verified": False}


def list_trait_lab_autonomous_receipt_chains(index: Any) -> list[dict[str, Any]]:
    """R09 — chain rows from a verified index."""
    verified = verify_trait_lab_autonomous_receipt_chain_index(index)
    return list(verified["chains"])


def count_trait_lab_autonomous_receipt_chains(index: Any) -> int:
    """R10 — number of chains in an index."""
    return int(verify_trait_lab_autonomous_receipt_chain_index(index)["count"])


def trait_lab_autonomous_receipt_chain_has(
    index: Any,
    *,
    autonomous_sha256: str,
) -> bool:
    """R11 — true when the index lists the autonomous receipt hash."""
    auto = _require_sha256("autonomous_sha256", autonomous_sha256, code="missing_autonomous_hash")
    return any(row.get("autonomous_sha256") == auto for row in list_trait_lab_autonomous_receipt_chains(index))


def page_trait_lab_autonomous_receipt_chains(
    index: Any,
    *,
    offset: int = 0,
    limit: int = 50,
) -> dict[str, Any]:
    """R12 — deterministic chain page."""
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise MemoryLayerError("invalid_limit", "limit must be >= 1")
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
        raise MemoryLayerError("invalid_offset", "offset must be >= 0")
    chains = list_trait_lab_autonomous_receipt_chains(index)
    return {
        "kind": _CHAIN_INDEX_KIND,
        "chains": chains[offset : offset + limit],
        "count": len(chains),
        "offset": offset,
        "limit": limit,
        "live_verified": False,
    }


def trait_lab_autonomous_receipt_chain_digest(index: Any) -> str:
    """R13 — SHA-256 over the stable signed index body."""
    verified = verify_trait_lab_autonomous_receipt_chain_index(index)
    body = _index_body(list(verified["chains"]))
    return hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def trait_lab_autonomous_receipt_chain_etag(index: Any) -> str:
    """R14 — short digest for chain index identity."""
    return trait_lab_autonomous_receipt_chain_digest(index)[:16]


def public_trait_lab_autonomous_receipt_chain_row(row: dict[str, Any]) -> dict[str, Any]:
    """R15 — stable chain row without agent/task fields."""
    signed = sign_trait_lab_autonomous_receipt_chain(row)
    return {
        "prep_sha256": signed["prep_sha256"],
        "session_sha256": signed["session_sha256"],
        "autonomous_sha256": signed["autonomous_sha256"],
        "status": signed["status"],
        "chain_sha256": signed["chain_sha256"],
        "live_verified": False,
    }


def require_trait_lab_autonomous_receipt_green_chain(
    store: MemoryStore,
    row: Any,
) -> dict[str, Any]:
    """R16 — fail-closed unless prep, session, and autonomous receipts align."""
    signed = sign_trait_lab_autonomous_receipt_chain(row)
    prep = get_trait_lab_local_env_prep_receipt(store, signed["prep_sha256"])
    if not prep.get("ok"):
        raise MemoryLayerError("blocked_prep", "chain prep receipt is not green")
    session = get_trait_lab_operator_session_receipt(store, signed["session_sha256"])
    if session.get("status") not in {"dry_run", "ready"} or not session.get("ok", True):
        raise MemoryLayerError("blocked_session", "chain session receipt is not green")
    auto = get_trait_lab_autonomous_workflow_receipt(store, signed["autonomous_sha256"])
    if auto.get("status") not in {"dry_run", "ready"} or not auto.get("ok", True):
        raise MemoryLayerError("blocked_autonomous", "chain autonomous receipt is not green")
    if str(session.get("prep_sha256") or "").lower() != signed["prep_sha256"]:
        raise MemoryLayerError("chain_mismatch", "session prep_sha256 disagrees with chain")
    if (
        str(auto.get("prep_sha256") or "").lower() != signed["prep_sha256"]
        or str(auto.get("session_sha256") or "").lower() != signed["session_sha256"]
    ):
        raise MemoryLayerError("chain_mismatch", "autonomous receipt disagrees with chain")
    return {**signed, "green": True, "live_verified": False}


def filter_trait_lab_autonomous_receipt_chains_by_prep(
    index: Any,
    prep_sha256: str,
) -> dict[str, Any]:
    """R17 — chains matching prep_sha256."""
    prep = _require_sha256("prep_sha256", prep_sha256, code="missing_prep_hash")
    rows = [row for row in list_trait_lab_autonomous_receipt_chains(index) if row["prep_sha256"] == prep]
    return {**_index_body(rows), "prep_sha256": prep, "live_verified": False}


def filter_trait_lab_autonomous_receipt_chains_by_session(
    index: Any,
    session_sha256: str,
) -> dict[str, Any]:
    """R18 — chains matching session_sha256."""
    session = _require_sha256("session_sha256", session_sha256, code="missing_session_hash")
    rows = [
        row for row in list_trait_lab_autonomous_receipt_chains(index) if row["session_sha256"] == session
    ]
    return {**_index_body(rows), "session_sha256": session, "live_verified": False}


def filter_trait_lab_autonomous_receipt_chains_by_autonomous(
    index: Any,
    autonomous_sha256: str,
) -> dict[str, Any]:
    """R19 — chains matching autonomous_sha256."""
    auto = _require_sha256("autonomous_sha256", autonomous_sha256, code="missing_autonomous_hash")
    rows = [
        row for row in list_trait_lab_autonomous_receipt_chains(index) if row["autonomous_sha256"] == auto
    ]
    return {**_index_body(rows), "autonomous_sha256": auto, "live_verified": False}


def filter_trait_lab_autonomous_receipt_chains_by_agent(
    store: MemoryStore,
    index: Any,
    agent_id: str,
) -> dict[str, Any]:
    """R20 — chains whose autonomous receipt was written by agent_id."""
    wanted = str(agent_id or "").strip()
    if not wanted:
        raise MemoryLayerError("missing_agent", "filter by agent requires agent_id")
    kept: list[dict[str, Any]] = []
    for row in list_trait_lab_autonomous_receipt_chains(index):
        auto = get_trait_lab_autonomous_workflow_receipt(store, row["autonomous_sha256"])
        if auto.get("agent_id") == wanted:
            kept.append(row)
    if not kept:
        raise MemoryLayerError("missing_agent", f"no chain row for agent {wanted}")
    return {**_index_body(kept), "agent_id": wanted, "live_verified": False}


def rematch_trait_lab_autonomous_receipt_chain_index(store: MemoryStore, index: Any) -> dict[str, Any]:
    """R21 — rebuild index from store and compare to signed snapshot."""
    verified = verify_trait_lab_autonomous_receipt_chain_index(index)
    fresh = export_trait_lab_autonomous_receipt_chain_index(store, limit=max(50, verified["count"]))
    if fresh["chain_index_sha256"] != verified["chain_index_sha256"]:
        raise MemoryLayerError("chain_index_mismatch", "store rematch disagrees with signed index")
    return {**fresh, "rematched": True, "live_verified": False}


def diff_trait_lab_autonomous_receipt_chain_indexes(index_a: Any, index_b: Any) -> dict[str, Any]:
    """R22 — symmetric diff of autonomous_sha256 sets."""
    a = {row["autonomous_sha256"] for row in list_trait_lab_autonomous_receipt_chains(index_a)}
    b = {row["autonomous_sha256"] for row in list_trait_lab_autonomous_receipt_chains(index_b)}
    only_a = sorted(a - b)
    only_b = sorted(b - a)
    return {
        "kind": _CHAIN_INDEX_KIND,
        "only_a": only_a,
        "only_b": only_b,
        "count_a": len(a),
        "count_b": len(b),
        "live_verified": False,
    }


_STATUS_RANK = {"ready": 3, "dry_run": 2, "planned": 1, "blocked": 0}


def retain_best_trait_lab_autonomous_receipt_chain(index: Any) -> dict[str, Any]:
    """R23 — keep the highest-status chain row (ready beats dry_run)."""
    chains = list_trait_lab_autonomous_receipt_chains(index)
    if not chains:
        raise MemoryLayerError("missing_chain", "retain_best requires at least one chain")
    best = max(chains, key=lambda row: _STATUS_RANK.get(str(row.get("status") or ""), -1))
    return sign_trait_lab_autonomous_receipt_chain(best)


def chain_from_trait_lab_autonomous_receipt(store: MemoryStore, autonomous_sha256: str) -> dict[str, Any]:
    """R24 — build a signed chain row from one autonomous receipt."""
    auto = get_trait_lab_autonomous_workflow_receipt(store, autonomous_sha256)
    return sign_trait_lab_autonomous_receipt_chain(
        {
            "prep_sha256": auto["prep_sha256"],
            "session_sha256": auto["session_sha256"],
            "autonomous_sha256": auto["autonomous_sha256"],
            "status": auto["status"],
        }
    )


def _chain_index_fact_id(chain_index_sha256: str) -> str:
    return f"{_CHAIN_FACT_PREFIX}{chain_index_sha256[:16]}"


def persist_trait_lab_autonomous_receipt_chain_index(
    store: MemoryStore,
    index: Any,
    *,
    agent_id: str,
    task_id: str,
) -> dict[str, Any]:
    """R25 — persist a verified chain index fact. Does not apply packs or runs."""
    require_trait_lab_autonomous_receipt_chain_provenance(agent_id=agent_id, task_id=task_id)
    verified = verify_trait_lab_autonomous_receipt_chain_index(index)
    sha = str(verified["chain_index_sha256"])
    write_verified(
        store,
        {
            "id": _chain_index_fact_id(sha),
            "fact": f"autonomous receipt chain index {sha}",
            "how": f"persist_trait_lab_autonomous_receipt_chain_index {sha}",
            "confidence": 1.0,
            "source": sha,
            "agent_id": agent_id,
            "task_id": task_id,
            "kind": _CHAIN_INDEX_KIND,
            "count": verified["count"],
            "chain_index_sha256": sha,
        },
    )
    record_task_step(
        store,
        task_id,
        "autonomous-receipt-chain",
        {"chain_index_sha256": sha, "count": verified["count"]},
        agent_id=agent_id,
    )
    return {
        "persisted": True,
        "chain_index_sha256": sha,
        "fact_id": _chain_index_fact_id(sha),
        "count": verified["count"],
        "live_verified": False,
    }
