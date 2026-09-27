"""Hermetic Trait Lab autonomous workflow ↔ receipt chain bind (F01–F25).

After ``run_autonomous``, export and green-verify the receipt chain, then persist
a bind fact. No live APIs.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from core.memory.store import MemoryStore
from thinkbox.autonomous_receipt_chain import (
    chain_from_trait_lab_autonomous_receipt,
    export_trait_lab_autonomous_receipt_chain_index,
    list_trait_lab_autonomous_receipt_chains,
    rematch_trait_lab_autonomous_receipt_chain_index,
    require_trait_lab_autonomous_receipt_green_chain,
    verify_trait_lab_autonomous_receipt_chain_index,
)
from thinkbox.autonomous_workflow import (
    dry_run_trait_lab_autonomous_workflow,
    get_trait_lab_autonomous_workflow_receipt,
    require_trait_lab_autonomous_workflow_no_live_ack,
    require_trait_lab_autonomous_workflow_provenance,
    run_trait_lab_autonomous,
    workflow_from_session_trait_lab_autonomous,
)
from thinkbox.local_env_prep import require_trait_lab_local_env_no_live_ack
from thinkbox.memory_layers import MemoryLayer, MemoryLayerError, query_layer, record_task_step, write_verified

_BIND_KIND = "trait-lab-autonomous-workflow-chain-bind"
_BIND_FACT_PREFIX = "trait-lab-auto-wf-chain-"

TRAIT_LAB_AUTONOMOUS_WORKFLOW_CHAIN_OPS: tuple[str, ...] = (
    "refuse_live",
    "require_provenance",
    "require_no_live_ack",
    "export_chain_from_run",
    "require_green_chain",
    "align_run_to_chain",
    "sign_bind",
    "verify_bind",
    "validate_bind",
    "public_row",
    "digest",
    "etag",
    "compare_run_chain",
    "rematch_chain_index",
    "persist_bind",
    "get_bind",
    "has_bind",
    "list_binds",
    "filter_by_agent",
    "run_chained",
    "dry_run_chained",
    "status_chained",
    "bind_from_receipt",
    "open_chained_autonomous",
    "chain_index_digest",
)


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def refuse_trait_lab_autonomous_workflow_chain_live(payload: Any) -> None:
    """F01 — bind payloads may not claim LIVE VERIFIED."""
    if isinstance(payload, dict) and payload.get("live_verified") is True:
        raise MemoryLayerError("live_claim", "workflow chain bind may not claim LIVE VERIFIED")


def require_trait_lab_autonomous_workflow_chain_provenance(*, agent_id: str, task_id: str) -> dict[str, Any]:
    """F02 — fail-closed without agent_id and task_id."""
    return require_trait_lab_autonomous_workflow_provenance(agent_id=agent_id, task_id=task_id)


def require_trait_lab_autonomous_workflow_chain_no_live_ack(environ: Any = None) -> dict[str, Any]:
    """F03 — fail-closed when swarm live ack is present."""
    require_trait_lab_local_env_no_live_ack(environ)
    return require_trait_lab_autonomous_workflow_no_live_ack(environ)


def _run_store_path(run_result: Any) -> str:
    if not isinstance(run_result, dict):
        raise MemoryLayerError("invalid_run", "run result must be an object")
    workspace = run_result.get("workspace")
    if not isinstance(workspace, dict) or not workspace.get("store_path"):
        raise MemoryLayerError("invalid_run", "run result requires workspace.store_path")
    return str(workspace["store_path"])


def export_trait_lab_autonomous_workflow_chain_from_run(run_result: Any) -> dict[str, Any]:
    """F04 — export chain index from a ``run_autonomous`` result workspace."""
    refuse_trait_lab_autonomous_workflow_chain_live(run_result)
    store = MemoryStore(_run_store_path(run_result))
    try:
        return export_trait_lab_autonomous_receipt_chain_index(store)
    finally:
        store.close()


def require_trait_lab_autonomous_workflow_green_chain_for_run(
    store: MemoryStore,
    run_result: Any,
) -> dict[str, Any]:
    """F05 — green-chain gate for the autonomous receipt in a run result."""
    if not isinstance(run_result, dict) or not run_result.get("autonomous"):
        raise MemoryLayerError("invalid_run", "run result requires autonomous block")
    auto_sha = str(run_result["autonomous"].get("autonomous_sha256") or "")
    chain = chain_from_trait_lab_autonomous_receipt(store, auto_sha)
    return require_trait_lab_autonomous_receipt_green_chain(store, chain)


def align_trait_lab_autonomous_run_to_chain(run_result: Any, chain_index: Any) -> dict[str, Any]:
    """F06 — fail-closed unless run autonomous hash appears in the chain index."""
    if not isinstance(run_result, dict) or not run_result.get("autonomous"):
        raise MemoryLayerError("invalid_run", "align requires autonomous block")
    auto_sha = str(run_result["autonomous"].get("autonomous_sha256") or "").lower()
    verified = verify_trait_lab_autonomous_receipt_chain_index(chain_index)
    rows = list_trait_lab_autonomous_receipt_chains(verified)
    match = next((row for row in rows if row.get("autonomous_sha256") == auto_sha), None)
    if match is None:
        raise MemoryLayerError("chain_mismatch", "run autonomous hash missing from chain index")
    return {
        "aligned": True,
        "autonomous_sha256": auto_sha,
        "prep_sha256": match["prep_sha256"],
        "session_sha256": match["session_sha256"],
        "chain_index_sha256": verified["chain_index_sha256"],
        "live_verified": False,
    }


def _bind_body(
    *,
    autonomous_sha256: str,
    prep_sha256: str,
    session_sha256: str,
    chain_index_sha256: str,
    status: str,
) -> dict[str, Any]:
    return {
        "kind": _BIND_KIND,
        "autonomous_sha256": autonomous_sha256,
        "prep_sha256": prep_sha256,
        "session_sha256": session_sha256,
        "chain_index_sha256": chain_index_sha256,
        "status": status,
        "live_verified": False,
    }


def sign_trait_lab_autonomous_workflow_chain_bind(bind: Any) -> dict[str, Any]:
    """F07 — sign a validated workflow↔chain bind."""
    validated = validate_trait_lab_autonomous_workflow_chain_bind(bind)
    body = _bind_body(
        autonomous_sha256=validated["autonomous_sha256"],
        prep_sha256=validated["prep_sha256"],
        session_sha256=validated["session_sha256"],
        chain_index_sha256=validated["chain_index_sha256"],
        status=validated["status"],
    )
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {**body, "bind_sha256": hashlib.sha256(encoded).hexdigest(), "live_verified": False}


def validate_trait_lab_autonomous_workflow_chain_bind(bind: Any) -> dict[str, Any]:
    """F08 — fail-closed check of a bind object."""
    if not isinstance(bind, dict):
        raise MemoryLayerError("invalid_bind", "workflow chain bind must be an object")
    refuse_trait_lab_autonomous_workflow_chain_live(bind)
    if bind.get("kind") not in {None, _BIND_KIND}:
        raise MemoryLayerError("invalid_bind", "kind must be trait-lab-autonomous-workflow-chain-bind")
    auto = str(bind.get("autonomous_sha256") or "").strip().lower()
    prep = str(bind.get("prep_sha256") or "").strip().lower()
    session = str(bind.get("session_sha256") or "").strip().lower()
    index_sha = str(bind.get("chain_index_sha256") or "").strip().lower()
    for name, val in (
        ("autonomous_sha256", auto),
        ("prep_sha256", prep),
        ("session_sha256", session),
        ("chain_index_sha256", index_sha),
    ):
        if len(val) != 64 or any(ch not in "0123456789abcdef" for ch in val):
            raise MemoryLayerError("invalid_bind", f"{name} requires 64-char hex")
    status = str(bind.get("status") or "ready").strip()
    if status not in {"dry_run", "ready", "blocked", "planned"}:
        raise MemoryLayerError("invalid_status", f"unknown bind status {status}")
    return {
        **_bind_body(
            autonomous_sha256=auto,
            prep_sha256=prep,
            session_sha256=session,
            chain_index_sha256=index_sha,
            status=status,
        ),
        "valid": True,
    }


def verify_trait_lab_autonomous_workflow_chain_bind(bind: Any) -> dict[str, Any]:
    """F09 — rematch bind_sha256."""
    if not isinstance(bind, dict):
        raise MemoryLayerError("invalid_bind", "workflow chain bind must be an object")
    if bind.get("kind") != _BIND_KIND:
        raise MemoryLayerError("invalid_bind", "kind must be trait-lab-autonomous-workflow-chain-bind")
    refuse_trait_lab_autonomous_workflow_chain_live(bind)
    validated = validate_trait_lab_autonomous_workflow_chain_bind(bind)
    sha = str(bind.get("bind_sha256") or "").strip().lower()
    if len(sha) != 64:
        raise MemoryLayerError("missing_bind_hash", "verify requires bind_sha256")
    body = _bind_body(
        autonomous_sha256=validated["autonomous_sha256"],
        prep_sha256=validated["prep_sha256"],
        session_sha256=validated["session_sha256"],
        chain_index_sha256=validated["chain_index_sha256"],
        status=validated["status"],
    )
    got = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    if got != sha:
        raise MemoryLayerError("bind_mismatch", f"bind hashed {got[:12]} not {sha[:12]}")
    return {**body, "matched": True, "bind_sha256": sha, "live_verified": False}


def public_trait_lab_autonomous_workflow_chain_bind_row(bind: dict[str, Any]) -> dict[str, Any]:
    """F10 — stable bind row without agent/task fields."""
    signed = sign_trait_lab_autonomous_workflow_chain_bind(bind)
    return {
        "kind": _BIND_KIND,
        "autonomous_sha256": signed["autonomous_sha256"],
        "chain_index_sha256": signed["chain_index_sha256"],
        "bind_sha256": signed["bind_sha256"],
        "status": signed["status"],
        "live_verified": False,
    }


def trait_lab_autonomous_workflow_chain_bind_digest(bind: Any) -> str:
    """F11 — SHA-256 over signed bind body."""
    return str(sign_trait_lab_autonomous_workflow_chain_bind(bind)["bind_sha256"])


def trait_lab_autonomous_workflow_chain_bind_etag(bind: Any) -> str:
    """F12 — short bind identity."""
    return trait_lab_autonomous_workflow_chain_bind_digest(bind)[:16]


def compare_trait_lab_autonomous_run_to_chain(run_result: Any, chain_index: Any) -> dict[str, Any]:
    """F13 — structured compare of run vs chain index."""
    aligned = align_trait_lab_autonomous_run_to_chain(run_result, chain_index)
    auto = run_result["autonomous"]
    return {
        **aligned,
        "run_prep_sha256": str(auto.get("prep_sha256") or "").lower(),
        "run_session_sha256": str(auto.get("session_sha256") or "").lower(),
        "prep_match": aligned["prep_sha256"] == str(auto.get("prep_sha256") or "").lower(),
        "session_match": aligned["session_sha256"] == str(auto.get("session_sha256") or "").lower(),
        "live_verified": False,
    }


def rematch_trait_lab_autonomous_workflow_chain_index(
    store: MemoryStore,
    chain_index: Any,
) -> dict[str, Any]:
    """F14 — rematch chain index against store export."""
    return rematch_trait_lab_autonomous_receipt_chain_index(store, chain_index)


def _bind_fact_id(bind_sha256: str) -> str:
    return f"{_BIND_FACT_PREFIX}{bind_sha256[:16]}"


def persist_trait_lab_autonomous_workflow_chain_bind(
    store: MemoryStore,
    bind: Any,
    *,
    agent_id: str,
    task_id: str,
) -> dict[str, Any]:
    """F15 — persist bind fact."""
    require_trait_lab_autonomous_workflow_chain_provenance(agent_id=agent_id, task_id=task_id)
    verified = verify_trait_lab_autonomous_workflow_chain_bind(bind)
    sha = str(verified["bind_sha256"])
    write_verified(
        store,
        {
            "id": _bind_fact_id(sha),
            "fact": f"autonomous workflow chain bind {sha}",
            "how": f"persist_trait_lab_autonomous_workflow_chain_bind {sha}",
            "confidence": 1.0,
            "source": sha,
            "agent_id": agent_id,
            "task_id": task_id,
            "kind": _BIND_KIND,
            "autonomous_sha256": verified["autonomous_sha256"],
            "chain_index_sha256": verified["chain_index_sha256"],
            "status": verified["status"],
        },
    )
    record_task_step(
        store,
        task_id,
        "autonomous-workflow-chain-bind",
        {"bind_sha256": sha, "autonomous_sha256": verified["autonomous_sha256"]},
        agent_id=agent_id,
    )
    return {
        "persisted": True,
        "bind_sha256": sha,
        "fact_id": _bind_fact_id(sha),
        "live_verified": False,
    }


def _bind_row(entry: Any) -> dict[str, Any] | None:
    if not str(entry.key).startswith("verified:trait-lab-auto-wf-chain-"):
        return None
    if entry.value.get("live_verified") is True:
        return None
    bind_sha = str(entry.value.get("source") or "").strip().lower()
    auto = str(entry.value.get("autonomous_sha256") or "").strip().lower()
    index_sha = str(entry.value.get("chain_index_sha256") or "").strip().lower()
    if len(bind_sha) != 64 or len(auto) != 64:
        return None
    return {
        "kind": _BIND_KIND,
        "bind_sha256": bind_sha,
        "fact_id": _bind_fact_id(bind_sha),
        "autonomous_sha256": auto,
        "chain_index_sha256": index_sha,
        "status": str(entry.value.get("status") or ""),
        "agent_id": entry.agent_id,
        "task_id": entry.task_id,
        "live_verified": False,
    }


def _collect_binds(store: MemoryStore, *, scan: int = 200) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in query_layer(
        store,
        MemoryLayer.VERIFIED_KNOWLEDGE,
        prefix="verified:trait-lab-auto-wf-chain-",
        limit=scan,
    ):
        row = _bind_row(entry)
        if row is None or row["bind_sha256"] in seen:
            continue
        seen.add(row["bind_sha256"])
        found.append(row)
    found.sort(key=lambda row: str(row["bind_sha256"]))
    return found


def get_trait_lab_autonomous_workflow_chain_bind(store: MemoryStore, bind_sha256: str) -> dict[str, Any]:
    """F16 — select bind by bind_sha256."""
    sha = str(bind_sha256 or "").strip().lower()
    if len(sha) != 64:
        raise MemoryLayerError("missing_bind_hash", "get_bind requires bind_sha256")
    entry = store.get(f"verified:{_bind_fact_id(sha)}")
    if entry is None:
        raise MemoryLayerError("missing_bind", f"no workflow chain bind {sha[:12]}")
    row = _bind_row(entry)
    if row is None:
        raise MemoryLayerError("invalid_bind", f"workflow chain bind {sha[:12]} is malformed")
    return {**row, "live_verified": False}


def has_trait_lab_autonomous_workflow_chain_bind(store: MemoryStore, bind_sha256: str) -> bool:
    """F17 — true when bind fact exists."""
    sha = str(bind_sha256 or "").strip().lower()
    if len(sha) != 64:
        raise MemoryLayerError("missing_bind_hash", "has_bind requires bind_sha256")
    return any(row["bind_sha256"] == sha for row in _collect_binds(store))


def list_trait_lab_autonomous_workflow_chain_binds(store: MemoryStore, *, limit: int = 50) -> dict[str, Any]:
    """F18 — index persisted binds."""
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise MemoryLayerError("invalid_limit", "limit must be >= 1")
    rows = _collect_binds(store)[:limit]
    return {
        "kind": _BIND_KIND,
        "binds": [
            {
                "bind_sha256": row["bind_sha256"],
                "autonomous_sha256": row["autonomous_sha256"],
                "chain_index_sha256": row["chain_index_sha256"],
                "status": row["status"],
                "live_verified": False,
            }
            for row in rows
        ],
        "count": len(rows),
        "live_verified": False,
    }


def list_trait_lab_autonomous_workflow_chain_binds_by_agent(
    store: MemoryStore,
    agent_id: str,
    *,
    limit: int = 50,
) -> dict[str, Any]:
    """F19 — binds for one agent."""
    wanted = str(agent_id or "").strip()
    if not wanted:
        raise MemoryLayerError("missing_agent", "filter by agent requires agent_id")
    rows = [row for row in _collect_binds(store) if row.get("agent_id") == wanted]
    if not rows:
        raise MemoryLayerError("missing_agent", f"no workflow chain bind for agent {wanted}")
    return {
        "kind": _BIND_KIND,
        "binds": rows[:limit],
        "count": len(rows),
        "agent_id": wanted,
        "live_verified": False,
    }


def run_trait_lab_autonomous_chained(
    *,
    agent_id: str,
    task_id: str,
    environ: Any = None,
) -> dict[str, Any]:
    """F20 — ``run_autonomous`` then export, green-chain, sign, and persist bind."""
    require_trait_lab_autonomous_workflow_chain_provenance(agent_id=agent_id, task_id=task_id)
    require_trait_lab_autonomous_workflow_chain_no_live_ack(environ)
    run_result = run_trait_lab_autonomous(agent_id=agent_id, task_id=task_id, environ=environ)
    refuse_trait_lab_autonomous_workflow_chain_live(run_result)
    chain_index = export_trait_lab_autonomous_workflow_chain_from_run(run_result)
    store = MemoryStore(_run_store_path(run_result))
    try:
        require_trait_lab_autonomous_workflow_green_chain_for_run(store, run_result)
        aligned = align_trait_lab_autonomous_run_to_chain(run_result, chain_index)
        rematch_trait_lab_autonomous_workflow_chain_index(store, chain_index)
        bind = sign_trait_lab_autonomous_workflow_chain_bind(
            {
                "autonomous_sha256": aligned["autonomous_sha256"],
                "prep_sha256": aligned["prep_sha256"],
                "session_sha256": aligned["session_sha256"],
                "chain_index_sha256": aligned["chain_index_sha256"],
                "status": str(run_result.get("status") or "ready"),
            }
        )
        persisted = persist_trait_lab_autonomous_workflow_chain_bind(
            store, bind, agent_id=agent_id, task_id=task_id
        )
    finally:
        store.close()
    return {
        "kind": _BIND_KIND,
        "run": run_result,
        "chain_index": chain_index,
        "bind": bind,
        "persist": persisted,
        "chained": True,
        "ok": bool(run_result.get("ok")) and bool(persisted.get("persisted")),
        "status": str(run_result.get("status") or "ready"),
        "live_verified": False,
    }


def dry_run_trait_lab_autonomous_chained(
    store: MemoryStore,
    *,
    agent_id: str,
    task_id: str,
    environ: Any = None,
) -> dict[str, Any]:
    """F21 — dry-run autonomous plan without bind persist."""
    require_trait_lab_autonomous_workflow_chain_provenance(agent_id=agent_id, task_id=task_id)
    require_trait_lab_autonomous_workflow_chain_no_live_ack(environ)
    plan = workflow_from_session_trait_lab_autonomous()
    ran = dry_run_trait_lab_autonomous_workflow(
        store, plan, agent_id=agent_id, task_id=task_id, environ=environ
    )
    index = export_trait_lab_autonomous_receipt_chain_index(store)
    return {
        "dry_run": ran,
        "chain_index": index,
        "status": "dry_run",
        "wrote": False,
        "live_verified": False,
    }


def trait_lab_autonomous_workflow_chain_status(result: Any) -> str:
    """F22 — dry_run, ready, blocked, or planned."""
    if not isinstance(result, dict):
        raise MemoryLayerError("invalid_bind", "chain status requires a result")
    refuse_trait_lab_autonomous_workflow_chain_live(result)
    if result.get("status") == "dry_run":
        return "dry_run"
    if result.get("chained") is True and result.get("ok"):
        return "ready"
    if result.get("ok") is False:
        return "blocked"
    if result.get("bind"):
        return "planned"
    raise MemoryLayerError("invalid_bind", "chain status is missing")


def bind_trait_lab_autonomous_workflow_from_receipt(
    store: MemoryStore,
    autonomous_sha256: str,
    chain_index: Any,
) -> dict[str, Any]:
    """F23 — sign bind from receipt + chain index row."""
    auto = get_trait_lab_autonomous_workflow_receipt(store, autonomous_sha256)
    aligned = align_trait_lab_autonomous_run_to_chain({"autonomous": auto}, chain_index)
    return sign_trait_lab_autonomous_workflow_chain_bind(
        {
            "autonomous_sha256": aligned["autonomous_sha256"],
            "prep_sha256": aligned["prep_sha256"],
            "session_sha256": aligned["session_sha256"],
            "chain_index_sha256": aligned["chain_index_sha256"],
            "status": auto.get("status") or "dry_run",
        }
    )


def open_trait_lab_autonomous_chained(
    *,
    agent_id: str,
    task_id: str,
    environ: Any = None,
) -> dict[str, Any]:
    """F24 — alias for ``run_trait_lab_autonomous_chained``."""
    return run_trait_lab_autonomous_chained(agent_id=agent_id, task_id=task_id, environ=environ)


def trait_lab_autonomous_workflow_chain_index_digest(chain_index: Any) -> str:
    """F25 — chain index SHA-256 from verified index."""
    return str(verify_trait_lab_autonomous_receipt_chain_index(chain_index)["chain_index_sha256"])
