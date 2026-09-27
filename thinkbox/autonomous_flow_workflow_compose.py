"""Hermetic Trait Lab autonomous flow workflow compose (P01–P25).

Merge, intersect, subtract, and xor two signed flow-receipt indexes. No live APIs.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from core.memory.store import MemoryStore
from thinkbox.autonomous_flow_workflow import (
    export_trait_lab_autonomous_flow_workflow_receipt_index,
    list_trait_lab_autonomous_flow_workflow_receipt_index_flows,
    persist_trait_lab_autonomous_flow_workflow_receipt_index,
    verify_trait_lab_autonomous_flow_workflow_receipt_index,
)
from thinkbox.memory_layers import MemoryLayerError, record_task_step, write_verified

_COMPOSE_KIND = "trait-lab-autonomous-flow-workflow-compose"
_FLOW_INDEX_KIND = "trait-lab-autonomous-flow-workflow-receipt-index"
_COMPOSE_FACT_PREFIX = "trait-lab-auto-flow-compose-"

TRAIT_LAB_AUTONOMOUS_FLOW_WORKFLOW_COMPOSE_OPS: tuple[str, ...] = (
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
    "list_flows",
    "has_flow",
    "page",
    "public_row",
    "same_index_guard",
    "retain_on_conflict",
    "filter_status",
    "export_flow_receipt_index",
    "rematch_left",
    "rematch_right",
    "compose_row",
    "verify_pair",
    "symmetric_diff_sets",
    "persist_snapshot",
)

_STATUS_RANK = {"ready": 3, "dry_run": 2, "planned": 1, "blocked": 0}


def refuse_trait_lab_autonomous_flow_workflow_compose_live(payload: Any) -> None:
    """P01 — compose payloads may not claim LIVE VERIFIED."""
    if isinstance(payload, dict) and payload.get("live_verified") is True:
        raise MemoryLayerError("live_claim", "flow workflow compose may not claim LIVE VERIFIED")


def require_trait_lab_autonomous_flow_workflow_compose_provenance(
    *,
    agent_id: str,
    task_id: str,
) -> dict[str, Any]:
    """P02 — fail-closed without agent_id and task_id."""
    wanted_agent = str(agent_id or "").strip()
    wanted_task = str(task_id or "").strip()
    if not wanted_agent or not wanted_task:
        raise MemoryLayerError("missing_provenance", "flow compose requires agent_id and task_id")
    return {"agent_id": wanted_agent, "task_id": wanted_task, "live_verified": False}


def _flow_map(index: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {row["flow_sha256"]: row for row in list_trait_lab_autonomous_flow_workflow_receipt_index_flows(index)}


def _pick_status(left: str, right: str) -> str:
    if _STATUS_RANK.get(left, -1) >= _STATUS_RANK.get(right, -1):
        return left
    return right


def _resolve_conflict(row_a: dict[str, Any], row_b: dict[str, Any]) -> dict[str, Any]:
    for key in ("bind_sha256", "chain_index_sha256", "autonomous_sha256"):
        if row_a[key] != row_b[key]:
            raise MemoryLayerError("flow_conflict", "flow row disagrees across indexes")
    return {
        **row_a,
        "status": _pick_status(str(row_a.get("status") or ""), str(row_b.get("status") or "")),
        "live_verified": False,
    }


def guard_same_trait_lab_autonomous_flow_workflow_receipt_index(index_a: Any, index_b: Any) -> None:
    """P16 — fail-closed when both indexes are identical."""
    left = verify_trait_lab_autonomous_flow_workflow_receipt_index(index_a)
    right = verify_trait_lab_autonomous_flow_workflow_receipt_index(index_b)
    if left["flow_receipt_index_sha256"] == right["flow_receipt_index_sha256"]:
        raise MemoryLayerError("same_flow_index", "compose requires two different flow-index hashes")


def _compose_trait_lab_autonomous_flow_workflow_receipt_indexes(
    index_a: Any,
    index_b: Any,
    *,
    mode: str,
) -> dict[str, Any]:
    if mode not in {"merge", "intersect", "subtract", "xor"}:
        raise MemoryLayerError("invalid_compose", f"unknown compose mode {mode}")
    guard_same_trait_lab_autonomous_flow_workflow_receipt_index(index_a, index_b)
    left = verify_trait_lab_autonomous_flow_workflow_receipt_index(index_a)
    right = verify_trait_lab_autonomous_flow_workflow_receipt_index(index_b)
    map_a = _flow_map(left)
    map_b = _flow_map(right)
    for sha, row_b in map_b.items():
        row_a = map_a.get(sha)
        if row_a is None:
            continue
        for key in ("bind_sha256", "chain_index_sha256", "autonomous_sha256"):
            if row_a[key] != row_b[key]:
                raise MemoryLayerError("flow_conflict", "flow row disagrees across indexes")
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
    flows = sorted(selected.values(), key=lambda row: str(row["flow_sha256"]))
    body = {
        "kind": _COMPOSE_KIND,
        "mode": mode,
        "flows": flows,
        "count": len(flows),
        "a": left["flow_receipt_index_sha256"],
        "b": right["flow_receipt_index_sha256"],
        "live_verified": False,
    }
    refuse_trait_lab_autonomous_flow_workflow_compose_live(body)
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {**body, "compose_sha256": hashlib.sha256(encoded).hexdigest(), "live_verified": False}


def merge_trait_lab_autonomous_flow_workflow_receipt_indexes(index_a: Any, index_b: Any) -> dict[str, Any]:
    """P03 — union two rematched flow-receipt indexes."""
    return _compose_trait_lab_autonomous_flow_workflow_receipt_indexes(index_a, index_b, mode="merge")


def intersect_trait_lab_autonomous_flow_workflow_receipt_indexes(index_a: Any, index_b: Any) -> dict[str, Any]:
    """P04 — shared flows of two rematched indexes."""
    return _compose_trait_lab_autonomous_flow_workflow_receipt_indexes(index_a, index_b, mode="intersect")


def subtract_trait_lab_autonomous_flow_workflow_receipt_indexes(index_a: Any, index_b: Any) -> dict[str, Any]:
    """P05 — flows in A that are not in B."""
    return _compose_trait_lab_autonomous_flow_workflow_receipt_indexes(index_a, index_b, mode="subtract")


def symmetric_diff_trait_lab_autonomous_flow_workflow_receipt_indexes(
    index_a: Any,
    index_b: Any,
) -> dict[str, Any]:
    """P06 — flows in exactly one rematched index."""
    return _compose_trait_lab_autonomous_flow_workflow_receipt_indexes(index_a, index_b, mode="xor")


def sign_trait_lab_autonomous_flow_workflow_compose(result: Any) -> dict[str, Any]:
    """P07 — sign a compose result (idempotent if already signed)."""
    verified = verify_trait_lab_autonomous_flow_workflow_compose(result)
    body = {
        "kind": _COMPOSE_KIND,
        "mode": verified["mode"],
        "flows": verified["flows"],
        "count": verified["count"],
        "a": verified["a"],
        "b": verified["b"],
        "live_verified": False,
    }
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {**body, "compose_sha256": hashlib.sha256(encoded).hexdigest(), "live_verified": False}


def verify_trait_lab_autonomous_flow_workflow_compose(result: Any) -> dict[str, Any]:
    """P08 — rematch compose_sha256 over the stable compose body."""
    if not isinstance(result, dict):
        raise MemoryLayerError("invalid_compose", "compose result must be an object")
    if result.get("kind") != _COMPOSE_KIND:
        raise MemoryLayerError("invalid_compose", "kind must be trait-lab-autonomous-flow-workflow-compose")
    refuse_trait_lab_autonomous_flow_workflow_compose_live(result)
    mode = str(result.get("mode") or "").strip()
    if mode not in {"merge", "intersect", "subtract", "xor"}:
        raise MemoryLayerError("invalid_compose", f"unknown compose mode {mode or '<empty>'}")
    if not isinstance(result.get("flows"), list):
        raise MemoryLayerError("invalid_compose", "flows must be a list")
    sha = str(result.get("compose_sha256") or "").strip().lower()
    if len(sha) != 64 or any(ch not in "0123456789abcdef" for ch in sha):
        raise MemoryLayerError("missing_compose_hash", "verify requires compose_sha256")
    flows = [row for row in result["flows"] if isinstance(row, dict)]
    if len(flows) != len(result["flows"]):
        raise MemoryLayerError("invalid_compose", "every flow row must be an object")
    body = {
        "kind": _COMPOSE_KIND,
        "mode": mode,
        "flows": flows,
        "count": len(flows),
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


def trait_lab_autonomous_flow_workflow_compose_digest(result: Any) -> str:
    """P09 — SHA-256 digest of signed compose body."""
    return str(sign_trait_lab_autonomous_flow_workflow_compose(result)["compose_sha256"])


def trait_lab_autonomous_flow_workflow_compose_etag(result: Any) -> str:
    """P10 — short compose identity."""
    return trait_lab_autonomous_flow_workflow_compose_digest(result)[:16]


def count_trait_lab_autonomous_flow_workflow_compose(result: Any) -> int:
    """P11 — number of flows in a compose result."""
    return int(verify_trait_lab_autonomous_flow_workflow_compose(result)["count"])


def list_trait_lab_autonomous_flow_workflow_compose_flows(result: Any) -> list[dict[str, Any]]:
    """P12 — flow rows from a verified compose result."""
    return list(verify_trait_lab_autonomous_flow_workflow_compose(result)["flows"])


def trait_lab_autonomous_flow_workflow_compose_has(result: Any, *, flow_sha256: str) -> bool:
    """P13 — true when compose lists the flow hash."""
    flow = str(flow_sha256 or "").strip().lower()
    if len(flow) != 64:
        raise MemoryLayerError("missing_flow_hash", "has_flow requires flow_sha256")
    return any(row.get("flow_sha256") == flow for row in list_trait_lab_autonomous_flow_workflow_compose_flows(result))


def page_trait_lab_autonomous_flow_workflow_compose(
    result: Any,
    *,
    offset: int = 0,
    limit: int = 50,
) -> dict[str, Any]:
    """P14 — deterministic compose flow page."""
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise MemoryLayerError("invalid_limit", "limit must be >= 1")
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
        raise MemoryLayerError("invalid_offset", "offset must be >= 0")
    flows = list_trait_lab_autonomous_flow_workflow_compose_flows(result)
    return {
        "kind": _COMPOSE_KIND,
        "flows": flows[offset : offset + limit],
        "count": len(flows),
        "offset": offset,
        "limit": limit,
        "live_verified": False,
    }


def public_trait_lab_autonomous_flow_workflow_compose_row(result: dict[str, Any]) -> dict[str, Any]:
    """P15 — stable compose summary without agent/task fields."""
    signed = sign_trait_lab_autonomous_flow_workflow_compose(result)
    return {
        "kind": _COMPOSE_KIND,
        "mode": signed["mode"],
        "count": signed["count"],
        "compose_sha256": signed["compose_sha256"],
        "a": signed["a"],
        "b": signed["b"],
        "live_verified": False,
    }


def retain_on_conflict_trait_lab_autonomous_flow_workflow_compose(
    index_a: Any,
    index_b: Any,
) -> dict[str, Any]:
    """P17 — merge while retaining the higher-status row on conflicts."""
    return merge_trait_lab_autonomous_flow_workflow_receipt_indexes(index_a, index_b)


def filter_trait_lab_autonomous_flow_workflow_compose_by_status(
    result: Any,
    status: str,
) -> dict[str, Any]:
    """P18 — filter compose flows by status."""
    wanted = str(status or "").strip()
    if wanted not in {"dry_run", "ready", "blocked", "planned"}:
        raise MemoryLayerError("invalid_status", f"unknown status {wanted or '<empty>'}")
    rows = [
        row
        for row in list_trait_lab_autonomous_flow_workflow_compose_flows(result)
        if str(row.get("status") or "") == wanted
    ]
    filtered = verify_trait_lab_autonomous_flow_workflow_compose(result)
    body = {
        "kind": _COMPOSE_KIND,
        "mode": filtered["mode"],
        "flows": rows,
        "count": len(rows),
        "a": filtered["a"],
        "b": filtered["b"],
        "live_verified": False,
    }
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {**body, "compose_sha256": hashlib.sha256(encoded).hexdigest(), "status": wanted, "live_verified": False}


def export_trait_lab_autonomous_flow_workflow_compose_as_index(result: Any) -> dict[str, Any]:
    """P19 — project a compose result into a signed flow-receipt index."""
    verified = verify_trait_lab_autonomous_flow_workflow_compose(result)
    body = {
        "kind": _FLOW_INDEX_KIND,
        "flows": verified["flows"],
        "count": verified["count"],
        "live_verified": False,
    }
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        **body,
        "flow_receipt_index_sha256": hashlib.sha256(encoded).hexdigest(),
        "source_compose_sha256": verified["compose_sha256"],
        "live_verified": False,
    }


def rematch_trait_lab_autonomous_flow_workflow_compose_left(
    store: MemoryStore,
    result: Any,
) -> dict[str, Any]:
    """P20 — verify compose source A matches store export."""
    verified = verify_trait_lab_autonomous_flow_workflow_compose(result)
    fresh = export_trait_lab_autonomous_flow_workflow_receipt_index(store)
    if fresh["flow_receipt_index_sha256"] != verified["a"]:
        raise MemoryLayerError("flow_index_mismatch", "compose source A disagrees with store")
    return {**fresh, "rematched": True, "live_verified": False}


def rematch_trait_lab_autonomous_flow_workflow_compose_right(
    store: MemoryStore,
    result: Any,
) -> dict[str, Any]:
    """P21 — verify compose source B matches store export."""
    verified = verify_trait_lab_autonomous_flow_workflow_compose(result)
    fresh = export_trait_lab_autonomous_flow_workflow_receipt_index(store)
    if fresh["flow_receipt_index_sha256"] != verified["b"]:
        raise MemoryLayerError("flow_index_mismatch", "compose source B disagrees with store")
    return {**fresh, "rematched": True, "live_verified": False}


def trait_lab_autonomous_flow_workflow_compose_row(result: Any) -> dict[str, Any]:
    """P22 — one-line compose metadata row."""
    return public_trait_lab_autonomous_flow_workflow_compose_row(result)


def verify_trait_lab_autonomous_flow_workflow_compose_pair(index_a: Any, index_b: Any) -> dict[str, Any]:
    """P23 — verify both indexes before compose."""
    left = verify_trait_lab_autonomous_flow_workflow_receipt_index(index_a)
    right = verify_trait_lab_autonomous_flow_workflow_receipt_index(index_b)
    return {
        "a": left["flow_receipt_index_sha256"],
        "b": right["flow_receipt_index_sha256"],
        "live_verified": False,
    }


def symmetric_diff_sets_trait_lab_autonomous_flow_workflow_compose(
    index_a: Any,
    index_b: Any,
) -> dict[str, Any]:
    """P24 — flow_sha256 sets from xor compose."""
    xor = symmetric_diff_trait_lab_autonomous_flow_workflow_receipt_indexes(index_a, index_b)
    flows = sorted(row["flow_sha256"] for row in xor["flows"])
    return {"flows": flows, "count": len(flows), "mode": "xor", "live_verified": False}


def _compose_fact_id(compose_sha256: str) -> str:
    return f"{_COMPOSE_FACT_PREFIX}{compose_sha256[:16]}"


def persist_trait_lab_autonomous_flow_workflow_compose_snapshot(
    store: MemoryStore,
    result: Any,
    *,
    agent_id: str,
    task_id: str,
) -> dict[str, Any]:
    """P25 — persist compose snapshot + optional flow-receipt index export."""
    require_trait_lab_autonomous_flow_workflow_compose_provenance(agent_id=agent_id, task_id=task_id)
    verified = verify_trait_lab_autonomous_flow_workflow_compose(result)
    sha = str(verified["compose_sha256"])
    write_verified(
        store,
        {
            "id": _compose_fact_id(sha),
            "fact": f"autonomous flow workflow compose {sha} mode={verified['mode']}",
            "how": f"persist_trait_lab_autonomous_flow_workflow_compose_snapshot {sha}",
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
    exported = export_trait_lab_autonomous_flow_workflow_compose_as_index(result)
    index_persist = persist_trait_lab_autonomous_flow_workflow_receipt_index(
        store, exported, agent_id=agent_id, task_id=task_id
    )
    record_task_step(
        store,
        task_id,
        "autonomous-flow-workflow-compose",
        {
            "compose_sha256": sha,
            "flow_receipt_index_sha256": index_persist["flow_receipt_index_sha256"],
        },
        agent_id=agent_id,
    )
    return {
        "persisted": True,
        "compose_sha256": sha,
        "fact_id": _compose_fact_id(sha),
        "flow_receipt_index": index_persist,
        "live_verified": False,
    }
