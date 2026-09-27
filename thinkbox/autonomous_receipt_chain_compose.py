"""Hermetic Trait Lab autonomous receipt chain compose (M01–M25).

Merge, intersect, subtract, and xor two signed chain indexes. No live APIs.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from core.memory.store import MemoryStore
from thinkbox.autonomous_receipt_chain import (
    export_trait_lab_autonomous_receipt_chain_index,
    list_trait_lab_autonomous_receipt_chains,
    persist_trait_lab_autonomous_receipt_chain_index,
    verify_trait_lab_autonomous_receipt_chain_index,
)
from thinkbox.memory_layers import MemoryLayerError, record_task_step, write_verified

_COMPOSE_KIND = "trait-lab-autonomous-receipt-chain-compose"
_CHAIN_INDEX_KIND = "trait-lab-autonomous-receipt-chain-index"
_COMPOSE_FACT_PREFIX = "trait-lab-auto-chain-compose-"

TRAIT_LAB_AUTONOMOUS_RECEIPT_CHAIN_COMPOSE_OPS: tuple[str, ...] = (
    "refuse_live",
    "require_provenance",
    "merge",
    "intersect",
    "subtract",
    "xor",
    "sign",
    "verify",
    "digest",
    "etag",
    "count",
    "list_chains",
    "has_chain",
    "page",
    "public_row",
    "same_index_guard",
    "retain_on_conflict",
    "filter_status",
    "export_chain_index",
    "rematch_left",
    "rematch_right",
    "compose_row",
    "verify_pair",
    "symmetric_diff_sets",
    "persist_snapshot",
)

_STATUS_RANK = {"ready": 3, "dry_run": 2, "planned": 1, "blocked": 0}


def refuse_trait_lab_autonomous_receipt_chain_compose_live(payload: Any) -> None:
    """M01 — compose payloads may not claim LIVE VERIFIED."""
    if isinstance(payload, dict) and payload.get("live_verified") is True:
        raise MemoryLayerError("live_claim", "receipt chain compose may not claim LIVE VERIFIED")


def require_trait_lab_autonomous_receipt_chain_compose_provenance(
    *,
    agent_id: str,
    task_id: str,
) -> dict[str, Any]:
    """M02 — fail-closed without agent_id and task_id."""
    wanted_agent = str(agent_id or "").strip()
    wanted_task = str(task_id or "").strip()
    if not wanted_agent or not wanted_task:
        raise MemoryLayerError("missing_provenance", "chain compose requires agent_id and task_id")
    return {"agent_id": wanted_agent, "task_id": wanted_task, "live_verified": False}


def _chain_map(index: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {row["autonomous_sha256"]: row for row in list_trait_lab_autonomous_receipt_chains(index)}


def _pick_status(left: str, right: str) -> str:
    if _STATUS_RANK.get(left, -1) >= _STATUS_RANK.get(right, -1):
        return left
    return right


def _resolve_conflict(row_a: dict[str, Any], row_b: dict[str, Any]) -> dict[str, Any]:
    if row_a["prep_sha256"] != row_b["prep_sha256"] or row_a["session_sha256"] != row_b["session_sha256"]:
        raise MemoryLayerError("chain_conflict", "chain row disagrees across indexes")
    return {
        **row_a,
        "status": _pick_status(str(row_a.get("status") or ""), str(row_b.get("status") or "")),
        "live_verified": False,
    }


def guard_same_trait_lab_autonomous_receipt_chain_index(index_a: Any, index_b: Any) -> None:
    """M16 — fail-closed when both indexes are identical."""
    left = verify_trait_lab_autonomous_receipt_chain_index(index_a)
    right = verify_trait_lab_autonomous_receipt_chain_index(index_b)
    if left["chain_index_sha256"] == right["chain_index_sha256"]:
        raise MemoryLayerError("same_chain_index", "compose requires two different chain-index hashes")


def _compose_trait_lab_autonomous_receipt_chain_indexes(
    index_a: Any,
    index_b: Any,
    *,
    mode: str,
) -> dict[str, Any]:
    if mode not in {"merge", "intersect", "subtract", "xor"}:
        raise MemoryLayerError("invalid_compose", f"unknown compose mode {mode}")
    guard_same_trait_lab_autonomous_receipt_chain_index(index_a, index_b)
    left = verify_trait_lab_autonomous_receipt_chain_index(index_a)
    right = verify_trait_lab_autonomous_receipt_chain_index(index_b)
    map_a = _chain_map(left)
    map_b = _chain_map(right)
    for sha, row_b in map_b.items():
        row_a = map_a.get(sha)
        if row_a is None:
            continue
        if row_a["prep_sha256"] != row_b["prep_sha256"] or row_a["session_sha256"] != row_b["session_sha256"]:
            raise MemoryLayerError("chain_conflict", "chain row disagrees across indexes")
        if mode == "merge":
            map_a[sha] = _resolve_conflict(row_a, row_b)
    if mode == "merge":
        selected = {**map_a, **map_b}
    elif mode == "intersect":
        selected = {sha: map_a[sha] for sha in map_a if sha in map_b}
    elif mode == "subtract":
        selected = {sha: map_a[sha] for sha in map_a if sha not in map_b}
    else:
        selected = {
            **{sha: map_a[sha] for sha in map_a if sha not in map_b},
            **{sha: map_b[sha] for sha in map_b if sha not in map_a},
        }
    chains = sorted(selected.values(), key=lambda row: str(row["autonomous_sha256"]))
    body = {
        "kind": _COMPOSE_KIND,
        "mode": mode,
        "chains": chains,
        "count": len(chains),
        "a": left["chain_index_sha256"],
        "b": right["chain_index_sha256"],
        "live_verified": False,
    }
    refuse_trait_lab_autonomous_receipt_chain_compose_live(body)
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {**body, "compose_sha256": hashlib.sha256(encoded).hexdigest(), "live_verified": False}


def merge_trait_lab_autonomous_receipt_chain_indexes(index_a: Any, index_b: Any) -> dict[str, Any]:
    """M03 — union two rematched chain indexes."""
    return _compose_trait_lab_autonomous_receipt_chain_indexes(index_a, index_b, mode="merge")


def intersect_trait_lab_autonomous_receipt_chain_indexes(index_a: Any, index_b: Any) -> dict[str, Any]:
    """M04 — shared chains of two rematched indexes."""
    return _compose_trait_lab_autonomous_receipt_chain_indexes(index_a, index_b, mode="intersect")


def subtract_trait_lab_autonomous_receipt_chain_indexes(index_a: Any, index_b: Any) -> dict[str, Any]:
    """M05 — chains in A that are not in B."""
    return _compose_trait_lab_autonomous_receipt_chain_indexes(index_a, index_b, mode="subtract")


def symmetric_diff_trait_lab_autonomous_receipt_chain_indexes(index_a: Any, index_b: Any) -> dict[str, Any]:
    """M06 — chains in exactly one rematched index."""
    return _compose_trait_lab_autonomous_receipt_chain_indexes(index_a, index_b, mode="xor")


def sign_trait_lab_autonomous_receipt_chain_compose(result: Any) -> dict[str, Any]:
    """M07 — sign a compose result (idempotent if already signed)."""
    verified = verify_trait_lab_autonomous_receipt_chain_compose(result)
    body = {
        "kind": _COMPOSE_KIND,
        "mode": verified["mode"],
        "chains": verified["chains"],
        "count": verified["count"],
        "a": verified["a"],
        "b": verified["b"],
        "live_verified": False,
    }
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {**body, "compose_sha256": hashlib.sha256(encoded).hexdigest(), "live_verified": False}


def verify_trait_lab_autonomous_receipt_chain_compose(result: Any) -> dict[str, Any]:
    """M08 — rematch compose_sha256 over the stable compose body."""
    if not isinstance(result, dict):
        raise MemoryLayerError("invalid_compose", "compose result must be an object")
    if result.get("kind") != _COMPOSE_KIND:
        raise MemoryLayerError("invalid_compose", "kind must be trait-lab-autonomous-receipt-chain-compose")
    refuse_trait_lab_autonomous_receipt_chain_compose_live(result)
    mode = str(result.get("mode") or "").strip()
    if mode not in {"merge", "intersect", "subtract", "xor"}:
        raise MemoryLayerError("invalid_compose", f"unknown compose mode {mode or '<empty>'}")
    if not isinstance(result.get("chains"), list):
        raise MemoryLayerError("invalid_compose", "chains must be a list")
    sha = str(result.get("compose_sha256") or "").strip().lower()
    if len(sha) != 64 or any(ch not in "0123456789abcdef" for ch in sha):
        raise MemoryLayerError("missing_compose_hash", "verify requires compose_sha256")
    chains = [row for row in result["chains"] if isinstance(row, dict)]
    if len(chains) != len(result["chains"]):
        raise MemoryLayerError("invalid_compose", "every chain row must be an object")
    body = {
        "kind": _COMPOSE_KIND,
        "mode": mode,
        "chains": chains,
        "count": len(chains),
        "a": str(result.get("a") or "").strip().lower(),
        "b": str(result.get("b") or "").strip().lower(),
        "live_verified": False,
    }
    got = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    if got != sha:
        raise MemoryLayerError("compose_mismatch", f"compose hashed {got[:12]} not {sha[:12]}")
    return {**body, "matched": True, "compose_sha256": sha, "live_verified": False}


def trait_lab_autonomous_receipt_chain_compose_digest(result: Any) -> str:
    """M09 — SHA-256 digest of signed compose body."""
    return str(sign_trait_lab_autonomous_receipt_chain_compose(result)["compose_sha256"])


def trait_lab_autonomous_receipt_chain_compose_etag(result: Any) -> str:
    """M10 — short compose identity."""
    return trait_lab_autonomous_receipt_chain_compose_digest(result)[:16]


def count_trait_lab_autonomous_receipt_chain_compose(result: Any) -> int:
    """M11 — number of chains in a compose result."""
    return int(verify_trait_lab_autonomous_receipt_chain_compose(result)["count"])


def list_trait_lab_autonomous_receipt_chain_compose_chains(result: Any) -> list[dict[str, Any]]:
    """M12 — chain rows from a verified compose result."""
    return list(verify_trait_lab_autonomous_receipt_chain_compose(result)["chains"])


def trait_lab_autonomous_receipt_chain_compose_has(result: Any, *, autonomous_sha256: str) -> bool:
    """M13 — true when compose lists the autonomous hash."""
    auto = str(autonomous_sha256 or "").strip().lower()
    if len(auto) != 64:
        raise MemoryLayerError("missing_autonomous_hash", "has_chain requires autonomous_sha256")
    return any(row.get("autonomous_sha256") == auto for row in list_trait_lab_autonomous_receipt_chain_compose_chains(result))


def page_trait_lab_autonomous_receipt_chain_compose(
    result: Any,
    *,
    offset: int = 0,
    limit: int = 50,
) -> dict[str, Any]:
    """M14 — deterministic compose chain page."""
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise MemoryLayerError("invalid_limit", "limit must be >= 1")
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
        raise MemoryLayerError("invalid_offset", "offset must be >= 0")
    chains = list_trait_lab_autonomous_receipt_chain_compose_chains(result)
    return {
        "kind": _COMPOSE_KIND,
        "chains": chains[offset : offset + limit],
        "count": len(chains),
        "offset": offset,
        "limit": limit,
        "live_verified": False,
    }


def public_trait_lab_autonomous_receipt_chain_compose_row(result: dict[str, Any]) -> dict[str, Any]:
    """M15 — stable compose summary without agent/task fields."""
    signed = sign_trait_lab_autonomous_receipt_chain_compose(result)
    return {
        "kind": _COMPOSE_KIND,
        "mode": signed["mode"],
        "count": signed["count"],
        "compose_sha256": signed["compose_sha256"],
        "a": signed["a"],
        "b": signed["b"],
        "live_verified": False,
    }


def retain_on_conflict_trait_lab_autonomous_receipt_chain_compose(
    index_a: Any,
    index_b: Any,
) -> dict[str, Any]:
    """M17 — merge while retaining the higher-status row on conflicts."""
    return merge_trait_lab_autonomous_receipt_chain_indexes(index_a, index_b)


def filter_trait_lab_autonomous_receipt_chain_compose_by_status(
    result: Any,
    status: str,
) -> dict[str, Any]:
    """M18 — filter compose chains by status."""
    wanted = str(status or "").strip()
    if wanted not in {"dry_run", "ready", "blocked", "planned"}:
        raise MemoryLayerError("invalid_status", f"unknown status {wanted or '<empty>'}")
    rows = [
        row
        for row in list_trait_lab_autonomous_receipt_chain_compose_chains(result)
        if str(row.get("status") or "") == wanted
    ]
    filtered = verify_trait_lab_autonomous_receipt_chain_compose(result)
    body = {
        "kind": _COMPOSE_KIND,
        "mode": filtered["mode"],
        "chains": rows,
        "count": len(rows),
        "a": filtered["a"],
        "b": filtered["b"],
        "live_verified": False,
    }
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {**body, "compose_sha256": hashlib.sha256(encoded).hexdigest(), "status": wanted, "live_verified": False}


def export_trait_lab_autonomous_receipt_chain_compose_as_index(result: Any) -> dict[str, Any]:
    """M19 — project a compose result into a signed chain index."""
    verified = verify_trait_lab_autonomous_receipt_chain_compose(result)
    body = {
        "kind": _CHAIN_INDEX_KIND,
        "chains": verified["chains"],
        "count": verified["count"],
        "live_verified": False,
    }
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        **body,
        "chain_index_sha256": hashlib.sha256(encoded).hexdigest(),
        "source_compose_sha256": verified["compose_sha256"],
        "live_verified": False,
    }


def rematch_trait_lab_autonomous_receipt_chain_compose_left(
    store: MemoryStore,
    result: Any,
) -> dict[str, Any]:
    """M20 — verify compose source A matches store export."""
    verified = verify_trait_lab_autonomous_receipt_chain_compose(result)
    fresh = export_trait_lab_autonomous_receipt_chain_index(store)
    if fresh["chain_index_sha256"] != verified["a"]:
        raise MemoryLayerError("chain_index_mismatch", "compose source A disagrees with store")
    return {**fresh, "rematched": True, "live_verified": False}


def rematch_trait_lab_autonomous_receipt_chain_compose_right(
    store: MemoryStore,
    result: Any,
) -> dict[str, Any]:
    """M21 — verify compose source B matches store export."""
    verified = verify_trait_lab_autonomous_receipt_chain_compose(result)
    fresh = export_trait_lab_autonomous_receipt_chain_index(store)
    if fresh["chain_index_sha256"] != verified["b"]:
        raise MemoryLayerError("chain_index_mismatch", "compose source B disagrees with store")
    return {**fresh, "rematched": True, "live_verified": False}


def trait_lab_autonomous_receipt_chain_compose_row(result: Any) -> dict[str, Any]:
    """M22 — one-line compose metadata row."""
    return public_trait_lab_autonomous_receipt_chain_compose_row(result)


def verify_trait_lab_autonomous_receipt_chain_compose_pair(index_a: Any, index_b: Any) -> dict[str, Any]:
    """M23 — verify both indexes before compose."""
    left = verify_trait_lab_autonomous_receipt_chain_index(index_a)
    right = verify_trait_lab_autonomous_receipt_chain_index(index_b)
    return {"a": left["chain_index_sha256"], "b": right["chain_index_sha256"], "live_verified": False}


def symmetric_diff_sets_trait_lab_autonomous_receipt_chain_compose(
    index_a: Any,
    index_b: Any,
) -> dict[str, Any]:
    """M24 — autonomous_sha256 sets from xor compose."""
    xor = symmetric_diff_trait_lab_autonomous_receipt_chain_indexes(index_a, index_b)
    autos = sorted(row["autonomous_sha256"] for row in xor["chains"])
    return {"autos": autos, "count": len(autos), "mode": "xor", "live_verified": False}


def _compose_fact_id(compose_sha256: str) -> str:
    return f"{_COMPOSE_FACT_PREFIX}{compose_sha256[:16]}"


def persist_trait_lab_autonomous_receipt_chain_compose_snapshot(
    store: MemoryStore,
    result: Any,
    *,
    agent_id: str,
    task_id: str,
) -> dict[str, Any]:
    """M25 — persist compose snapshot + optional chain index export."""
    require_trait_lab_autonomous_receipt_chain_compose_provenance(agent_id=agent_id, task_id=task_id)
    verified = verify_trait_lab_autonomous_receipt_chain_compose(result)
    sha = str(verified["compose_sha256"])
    write_verified(
        store,
        {
            "id": _compose_fact_id(sha),
            "fact": f"autonomous receipt chain compose {sha} mode={verified['mode']}",
            "how": f"persist_trait_lab_autonomous_receipt_chain_compose_snapshot {sha}",
            "confidence": 1.0,
            "source": sha,
            "agent_id": agent_id,
            "task_id": task_id,
            "kind": _COMPOSE_KIND,
            "mode": verified["mode"],
            "count": verified["count"],
            "compose_sha256": sha,
        },
    )
    exported = export_trait_lab_autonomous_receipt_chain_compose_as_index(result)
    index_persist = persist_trait_lab_autonomous_receipt_chain_index(
        store, exported, agent_id=agent_id, task_id=task_id
    )
    record_task_step(
        store,
        task_id,
        "autonomous-receipt-chain-compose",
        {"compose_sha256": sha, "chain_index_sha256": index_persist["chain_index_sha256"]},
        agent_id=agent_id,
    )
    return {
        "persisted": True,
        "compose_sha256": sha,
        "fact_id": _compose_fact_id(sha),
        "chain_index": index_persist,
        "live_verified": False,
    }
