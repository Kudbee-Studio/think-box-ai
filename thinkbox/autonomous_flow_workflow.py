"""Hermetic Trait Lab autonomous flow workflow major (O01–O25).

Orchestrates dry-run and chained-run paths over prep → session → autonomous →
chain → bind. Persists a flow receipt. No live APIs.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from core.memory.store import MemoryStore
from thinkbox.autonomous_workflow import (
    require_trait_lab_autonomous_workflow_no_live_ack,
    require_trait_lab_autonomous_workflow_provenance,
)
from thinkbox.autonomous_workflow_chain import (
    dry_run_trait_lab_autonomous_chained,
    export_trait_lab_autonomous_workflow_chain_from_run,
    run_trait_lab_autonomous_chained,
    trait_lab_autonomous_workflow_chain_status,
    verify_trait_lab_autonomous_workflow_chain_bind,
)
from thinkbox.memory_layers import MemoryLayer, MemoryLayerError, query_layer, record_task_step, write_verified

_FLOW_KIND = "trait-lab-autonomous-flow-workflow"
_FLOW_RECEIPT_KIND = "trait-lab-autonomous-flow-workflow-receipt"
_FLOW_FACT_PREFIX = "trait-lab-auto-flow-"

TRAIT_LAB_AUTONOMOUS_FLOW_WORKFLOW_OPS: tuple[str, ...] = (
    "refuse_live",
    "require_provenance",
    "require_no_live_ack",
    "plan",
    "validate",
    "sign",
    "verify",
    "list_steps",
    "count_steps",
    "dry_run_flow",
    "run_flow",
    "flow_status",
    "export_artifacts",
    "digest",
    "etag",
    "public_row",
    "require_bind",
    "require_chain_index",
    "rematch_artifacts",
    "persist_receipt",
    "get_receipt",
    "list_receipts",
    "has_receipt",
    "receipts_by_agent",
    "open_flow",
)

TRAIT_LAB_AUTONOMOUS_FLOW_WORKFLOW_STEPS: tuple[str, ...] = (
    "dry_run",
    "run_chained",
)


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def refuse_trait_lab_autonomous_flow_workflow_live(payload: Any) -> None:
    """O01 — flow payloads may not claim LIVE VERIFIED."""
    if isinstance(payload, dict) and payload.get("live_verified") is True:
        raise MemoryLayerError("live_claim", "autonomous flow workflow may not claim LIVE VERIFIED")


def require_trait_lab_autonomous_flow_workflow_provenance(*, agent_id: str, task_id: str) -> dict[str, Any]:
    """O02 — fail-closed without agent_id and task_id."""
    return require_trait_lab_autonomous_workflow_provenance(agent_id=agent_id, task_id=task_id)


def require_trait_lab_autonomous_flow_workflow_no_live_ack(environ: Any = None) -> dict[str, Any]:
    """O03 — fail-closed when swarm live ack is present."""
    return require_trait_lab_autonomous_workflow_no_live_ack(environ)


def _flow_body(steps: list[str]) -> dict[str, Any]:
    return {
        "kind": _FLOW_KIND,
        "steps": list(steps),
        "count": len(steps),
        "live_verified": False,
    }


def _require_flow_steps(steps: Any) -> list[str]:
    if not isinstance(steps, list) or not steps:
        raise MemoryLayerError("missing_step", "flow workflow requires at least one step")
    allowed = set(TRAIT_LAB_AUTONOMOUS_FLOW_WORKFLOW_STEPS)
    names: list[str] = []
    for item in steps:
        name = str(item or "").strip()
        if name not in allowed:
            raise MemoryLayerError("invalid_step", f"unknown flow step {name or '<empty>'}")
        names.append(name)
    return names


def plan_trait_lab_autonomous_flow_workflow(steps: Any) -> dict[str, Any]:
    """O04 — build an unsigned flow plan."""
    names = _require_flow_steps(steps)
    body = _flow_body(names)
    refuse_trait_lab_autonomous_flow_workflow_live(body)
    return body


def validate_trait_lab_autonomous_flow_workflow(plan: Any) -> dict[str, Any]:
    """O05 — fail-closed check of a flow plan."""
    if not isinstance(plan, dict):
        raise MemoryLayerError("invalid_flow", "flow workflow must be an object")
    refuse_trait_lab_autonomous_flow_workflow_live(plan)
    if plan.get("kind") not in {None, _FLOW_KIND}:
        raise MemoryLayerError("invalid_flow", "kind must be trait-lab-autonomous-flow-workflow")
    names = _require_flow_steps(plan.get("steps"))
    return {**_flow_body(names), "valid": True}


def sign_trait_lab_autonomous_flow_workflow(plan: Any) -> dict[str, Any]:
    """O06 — sign a validated flow plan."""
    validated = validate_trait_lab_autonomous_flow_workflow(plan)
    body = _flow_body(validated["steps"])
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {**body, "flow_sha256": hashlib.sha256(encoded).hexdigest(), "live_verified": False}


def verify_trait_lab_autonomous_flow_workflow(flow: Any) -> dict[str, Any]:
    """O07 — rematch flow_sha256."""
    if not isinstance(flow, dict):
        raise MemoryLayerError("invalid_flow", "flow workflow must be an object")
    if flow.get("kind") != _FLOW_KIND:
        raise MemoryLayerError("invalid_flow", "kind must be trait-lab-autonomous-flow-workflow")
    refuse_trait_lab_autonomous_flow_workflow_live(flow)
    names = _require_flow_steps(flow.get("steps"))
    sha = str(flow.get("flow_sha256") or "").strip().lower()
    if len(sha) != 64 or any(ch not in "0123456789abcdef" for ch in sha):
        raise MemoryLayerError("missing_flow_hash", "verify requires flow_sha256")
    body = _flow_body(names)
    got = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    if got != sha:
        raise MemoryLayerError("flow_mismatch", f"flow hashed {got[:12]} not {sha[:12]}")
    return {**body, "matched": True, "flow_sha256": sha, "live_verified": False}


def list_trait_lab_autonomous_flow_workflow_steps(plan: Any) -> list[str]:
    """O08 — step names from a flow plan."""
    return list(validate_trait_lab_autonomous_flow_workflow(plan)["steps"])


def count_trait_lab_autonomous_flow_workflow_steps(plan: Any) -> int:
    """O09 — number of steps in a flow plan."""
    return int(validate_trait_lab_autonomous_flow_workflow(plan)["count"])


def dry_run_trait_lab_autonomous_flow_workflow(
    store: MemoryStore,
    plan: Any,
    *,
    agent_id: str,
    task_id: str,
    environ: Any = None,
) -> dict[str, Any]:
    """O10 — dry-run flow steps without bind/flow receipt writes."""
    require_trait_lab_autonomous_flow_workflow_provenance(agent_id=agent_id, task_id=task_id)
    require_trait_lab_autonomous_flow_workflow_no_live_ack(environ)
    signed = sign_trait_lab_autonomous_flow_workflow(plan)
    results: list[dict[str, Any]] = []
    for step in signed["steps"]:
        if step == "dry_run":
            results.append(
                {
                    **dry_run_trait_lab_autonomous_chained(
                        store, agent_id=agent_id, task_id=task_id, environ=environ
                    ),
                    "step": step,
                }
            )
        elif step == "run_chained":
            raise MemoryLayerError("invalid_flow", "dry_run_flow must not include run_chained")
        else:
            raise MemoryLayerError("invalid_step", f"unknown flow step {step}")
    if any(r.get("wrote") for r in results if isinstance(r, dict)):
        raise MemoryLayerError("invalid_flow", "dry_run_flow must not write")
    return {
        **signed,
        "results": results,
        "status": "dry_run",
        "ok": True,
        "wrote": False,
        "live_verified": False,
    }


def run_trait_lab_autonomous_flow_workflow(
    plan: Any,
    *,
    agent_id: str,
    task_id: str,
    environ: Any = None,
) -> dict[str, Any]:
    """O11 — execute flow steps (run_chained path persists bind)."""
    require_trait_lab_autonomous_flow_workflow_provenance(agent_id=agent_id, task_id=task_id)
    require_trait_lab_autonomous_flow_workflow_no_live_ack(environ)
    signed = sign_trait_lab_autonomous_flow_workflow(plan)
    results: list[dict[str, Any]] = []
    for step in signed["steps"]:
        if step == "run_chained":
            chained = run_trait_lab_autonomous_chained(
                agent_id=agent_id, task_id=task_id, environ=environ
            )
            results.append({**chained, "step": step})
        elif step == "dry_run":
            raise MemoryLayerError("invalid_flow", "run_flow must not include dry_run")
        else:
            raise MemoryLayerError("invalid_step", f"unknown flow step {step}")
    ok = all(bool(r.get("ok")) for r in results)
    status = trait_lab_autonomous_workflow_chain_status(results[-1]) if results else "blocked"
    return {
        **signed,
        "results": results,
        "status": status,
        "ok": ok,
        "live_verified": False,
    }


def trait_lab_autonomous_flow_workflow_status(result: Any) -> str:
    """O12 — dry_run, ready, blocked, or planned."""
    if not isinstance(result, dict):
        raise MemoryLayerError("invalid_flow", "flow status requires a result")
    refuse_trait_lab_autonomous_flow_workflow_live(result)
    if result.get("status") == "dry_run":
        return "dry_run"
    if result.get("flow_persisted") is True or result.get("opened") is True:
        return "ready"
    if result.get("ok") is False:
        return "blocked"
    if result.get("steps"):
        return "planned"
    raise MemoryLayerError("invalid_flow", "flow status is missing")


def export_trait_lab_autonomous_flow_workflow_artifacts(result: Any) -> dict[str, Any]:
    """O13 — chain index + bind from a chained flow result."""
    if not isinstance(result, dict) or not result.get("results"):
        raise MemoryLayerError("invalid_flow", "artifacts require flow results")
    last = result["results"][-1]
    if not last.get("chained"):
        raise MemoryLayerError("invalid_flow", "artifacts require a chained result")
    bind = last.get("bind")
    chain_index = last.get("chain_index")
    if not bind or not chain_index:
        raise MemoryLayerError("invalid_flow", "artifacts require bind and chain_index")
    verified_bind = verify_trait_lab_autonomous_workflow_chain_bind(bind)
    return {
        "kind": _FLOW_KIND,
        "chain_index_sha256": chain_index.get("chain_index_sha256"),
        "bind_sha256": verified_bind["bind_sha256"],
        "autonomous_sha256": verified_bind["autonomous_sha256"],
        "live_verified": False,
    }


def trait_lab_autonomous_flow_workflow_digest(plan: Any) -> str:
    """O14 — SHA-256 over signed flow plan."""
    return str(sign_trait_lab_autonomous_flow_workflow(plan)["flow_sha256"])


def trait_lab_autonomous_flow_workflow_etag(plan: Any) -> str:
    """O15 — short flow identity."""
    return trait_lab_autonomous_flow_workflow_digest(plan)[:16]


def public_trait_lab_autonomous_flow_workflow_row(row: dict[str, Any]) -> dict[str, Any]:
    """O16 — stable flow row without agent/task fields."""
    signed = sign_trait_lab_autonomous_flow_workflow(row)
    return {
        "kind": _FLOW_KIND,
        "steps": signed["steps"],
        "count": signed["count"],
        "flow_sha256": signed["flow_sha256"],
        "live_verified": False,
    }


def require_trait_lab_autonomous_flow_workflow_bind(result: Any) -> dict[str, Any]:
    """O17 — fail-closed unless chained result includes a bind."""
    artifacts = export_trait_lab_autonomous_flow_workflow_artifacts(result)
    last = result["results"][-1]
    bind = last.get("bind")
    if not bind:
        raise MemoryLayerError("missing_bind", "flow requires a workflow chain bind")
    return {**verify_trait_lab_autonomous_workflow_chain_bind(bind), "required": True, "live_verified": False}


def require_trait_lab_autonomous_flow_workflow_chain_index(result: Any) -> dict[str, Any]:
    """O18 — fail-closed unless chained result includes a chain index."""
    artifacts = export_trait_lab_autonomous_flow_workflow_artifacts(result)
    sha = str(artifacts.get("chain_index_sha256") or "")
    if len(sha) != 64:
        raise MemoryLayerError("missing_chain_index", "flow requires chain_index_sha256")
    return {**artifacts, "required": True, "live_verified": False}


def rematch_trait_lab_autonomous_flow_workflow_artifacts(result: Any) -> dict[str, Any]:
    """O19 — re-export chain index from run workspace and compare."""
    if not isinstance(result, dict) or not result.get("results"):
        raise MemoryLayerError("invalid_flow", "rematch requires flow results")
    last = result["results"][-1]
    if not last.get("run"):
        raise MemoryLayerError("invalid_flow", "rematch requires chained run payload")
    fresh_index = export_trait_lab_autonomous_workflow_chain_from_run(last["run"])
    prior = last.get("chain_index") or {}
    if fresh_index.get("chain_index_sha256") != prior.get("chain_index_sha256"):
        raise MemoryLayerError("chain_index_mismatch", "flow rematch disagrees with prior index")
    return {**fresh_index, "rematched": True, "live_verified": False}


def _flow_fact_id(flow_sha256: str) -> str:
    return f"{_FLOW_FACT_PREFIX}{flow_sha256[:16]}"


def persist_trait_lab_autonomous_flow_workflow_receipt(
    store: MemoryStore,
    result: Any,
    *,
    agent_id: str,
    task_id: str,
) -> dict[str, Any]:
    """O20 — persist flow receipt with artifact hashes."""
    require_trait_lab_autonomous_flow_workflow_provenance(agent_id=agent_id, task_id=task_id)
    if not isinstance(result, dict) or not result.get("flow_sha256"):
        raise MemoryLayerError("invalid_flow", "receipt requires a signed flow result")
    refuse_trait_lab_autonomous_flow_workflow_live(result)
    verified = verify_trait_lab_autonomous_flow_workflow(result)
    status = trait_lab_autonomous_flow_workflow_status(result)
    artifacts = export_trait_lab_autonomous_flow_workflow_artifacts(result)
    sha = str(verified["flow_sha256"])
    write_verified(
        store,
        {
            "id": _flow_fact_id(sha),
            "fact": f"autonomous flow workflow {sha} status={status}",
            "how": f"persist_trait_lab_autonomous_flow_workflow_receipt {sha}",
            "confidence": 1.0,
            "source": sha,
            "agent_id": agent_id,
            "task_id": task_id,
            "kind": _FLOW_RECEIPT_KIND,
            "status": status,
            "steps": verified["steps"],
            "count": verified["count"],
            "bind_sha256": artifacts["bind_sha256"],
            "chain_index_sha256": artifacts["chain_index_sha256"],
            "autonomous_sha256": artifacts["autonomous_sha256"],
            "ok": bool(result.get("ok", True)),
        },
    )
    record_task_step(
        store,
        task_id,
        "autonomous-flow-workflow",
        {"flow_sha256": sha, "status": status, "bind_sha256": artifacts["bind_sha256"]},
        agent_id=agent_id,
    )
    return {
        "persisted": True,
        "flow_sha256": sha,
        "fact_id": _flow_fact_id(sha),
        "status": status,
        "live_verified": False,
    }


def _flow_receipt_row(entry: Any) -> dict[str, Any] | None:
    if not str(entry.key).startswith("verified:trait-lab-auto-flow-"):
        return None
    if entry.value.get("live_verified") is True:
        return None
    sha = str(entry.value.get("source") or "").strip().lower()
    if len(sha) != 64:
        return None
    status = str(entry.value.get("status") or "")
    if status not in {"dry_run", "ready", "blocked", "planned"}:
        return None
    steps = entry.value.get("steps")
    if not isinstance(steps, list):
        return None
    return {
        "kind": _FLOW_RECEIPT_KIND,
        "flow_sha256": sha,
        "fact_id": _flow_fact_id(sha),
        "status": status,
        "steps": [str(s) for s in steps],
        "count": int(entry.value.get("count") or len(steps)),
        "bind_sha256": str(entry.value.get("bind_sha256") or ""),
        "chain_index_sha256": str(entry.value.get("chain_index_sha256") or ""),
        "autonomous_sha256": str(entry.value.get("autonomous_sha256") or ""),
        "ok": bool(entry.value.get("ok", True)),
        "agent_id": entry.agent_id,
        "task_id": entry.task_id,
        "live_verified": False,
    }


def _collect_flow_receipts(store: MemoryStore, *, scan: int = 200) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in query_layer(
        store,
        MemoryLayer.VERIFIED_KNOWLEDGE,
        prefix="verified:trait-lab-auto-flow-",
        limit=scan,
    ):
        row = _flow_receipt_row(entry)
        if row is None or row["flow_sha256"] in seen:
            continue
        seen.add(row["flow_sha256"])
        found.append(row)
    found.sort(key=lambda row: str(row["flow_sha256"]))
    return found


def get_trait_lab_autonomous_flow_workflow_receipt(store: MemoryStore, flow_sha256: str) -> dict[str, Any]:
    """O21 — select flow receipt by flow_sha256."""
    sha = str(flow_sha256 or "").strip().lower()
    if len(sha) != 64:
        raise MemoryLayerError("missing_flow_hash", "get_receipt requires flow_sha256")
    entry = store.get(f"verified:{_flow_fact_id(sha)}")
    if entry is None:
        raise MemoryLayerError("missing_flow", f"no flow workflow receipt {sha[:12]}")
    row = _flow_receipt_row(entry)
    if row is None:
        raise MemoryLayerError("invalid_flow", f"flow receipt {sha[:12]} is malformed")
    return {**row, "live_verified": False}


def list_trait_lab_autonomous_flow_workflow_receipts(store: MemoryStore, *, limit: int = 50) -> dict[str, Any]:
    """O22 — index flow receipts."""
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise MemoryLayerError("invalid_limit", "limit must be >= 1")
    rows = _collect_flow_receipts(store)[:limit]
    return {
        "kind": _FLOW_RECEIPT_KIND,
        "receipts": [
            {
                "flow_sha256": row["flow_sha256"],
                "fact_id": row["fact_id"],
                "status": row["status"],
                "bind_sha256": row["bind_sha256"],
                "autonomous_sha256": row["autonomous_sha256"],
                "live_verified": False,
            }
            for row in rows
        ],
        "count": len(rows),
        "live_verified": False,
    }


def has_trait_lab_autonomous_flow_workflow_receipt(store: MemoryStore, flow_sha256: str) -> bool:
    """O23 — true when a flow receipt exists."""
    sha = str(flow_sha256 or "").strip().lower()
    if len(sha) != 64:
        raise MemoryLayerError("missing_flow_hash", "has_receipt requires flow_sha256")
    return any(row["flow_sha256"] == sha for row in _collect_flow_receipts(store))


_FLOW_RECEIPT_INDEX_KIND = "trait-lab-autonomous-flow-workflow-receipt-index"


def _flow_index_public_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "flow_sha256": row["flow_sha256"],
        "bind_sha256": row["bind_sha256"],
        "chain_index_sha256": row["chain_index_sha256"],
        "autonomous_sha256": row["autonomous_sha256"],
        "status": row["status"],
        "live_verified": False,
    }


def _flow_index_body(flows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "kind": _FLOW_RECEIPT_INDEX_KIND,
        "flows": flows,
        "count": len(flows),
        "live_verified": False,
    }


def export_trait_lab_autonomous_flow_workflow_receipt_index(
    store: MemoryStore,
    *,
    limit: int = 50,
) -> dict[str, Any]:
    """Portable flow-receipt index from persisted flow receipts."""
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise MemoryLayerError("invalid_limit", "limit must be >= 1")
    rows = _collect_flow_receipts(store)[:limit]
    flows: list[dict[str, Any]] = []
    for receipt in rows:
        flow = str(receipt.get("flow_sha256") or "").strip().lower()
        bind = str(receipt.get("bind_sha256") or "").strip().lower()
        auto = str(receipt.get("autonomous_sha256") or "").strip().lower()
        chain = str(receipt.get("chain_index_sha256") or "").strip().lower()
        if len(flow) != 64 or len(bind) != 64 or len(auto) != 64 or len(chain) != 64:
            continue
        flows.append(
            _flow_index_public_row(
                {
                    "flow_sha256": flow,
                    "bind_sha256": bind,
                    "chain_index_sha256": chain,
                    "autonomous_sha256": auto,
                    "status": str(receipt.get("status") or "dry_run"),
                }
            )
        )
    flows.sort(key=lambda row: str(row["flow_sha256"]))
    body = _flow_index_body(flows)
    refuse_trait_lab_autonomous_flow_workflow_live(body)
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        **body,
        "flow_receipt_index_sha256": hashlib.sha256(encoded).hexdigest(),
        "exported_at": _utc(),
        "live_verified": False,
    }


def verify_trait_lab_autonomous_flow_workflow_receipt_index(index: Any) -> dict[str, Any]:
    """Rematch flow_receipt_index_sha256 over the stable index body."""
    if not isinstance(index, dict):
        raise MemoryLayerError("invalid_flow", "flow receipt index must be an object")
    if index.get("kind") != _FLOW_RECEIPT_INDEX_KIND:
        raise MemoryLayerError("invalid_flow", "kind must be trait-lab-autonomous-flow-workflow-receipt-index")
    refuse_trait_lab_autonomous_flow_workflow_live(index)
    if not isinstance(index.get("flows"), list):
        raise MemoryLayerError("invalid_flow", "flows must be a list")
    sha = str(index.get("flow_receipt_index_sha256") or "").strip().lower()
    if len(sha) != 64 or any(ch not in "0123456789abcdef" for ch in sha):
        raise MemoryLayerError("missing_index_hash", "verify requires flow_receipt_index_sha256")
    public: list[dict[str, Any]] = []
    for row in index["flows"]:
        if not isinstance(row, dict):
            raise MemoryLayerError("invalid_flow", "every flow row must be an object")
        flow = str(row.get("flow_sha256") or "").strip().lower()
        bind = str(row.get("bind_sha256") or "").strip().lower()
        chain = str(row.get("chain_index_sha256") or "").strip().lower()
        auto = str(row.get("autonomous_sha256") or "").strip().lower()
        status = str(row.get("status") or "")
        if len(flow) != 64 or len(bind) != 64 or len(chain) != 64 or len(auto) != 64:
            raise MemoryLayerError("invalid_flow", "flow row requires 64-char hashes")
        if status not in {"dry_run", "ready", "blocked", "planned"}:
            raise MemoryLayerError("invalid_status", f"unknown status {status or '<empty>'}")
        public.append(
            _flow_index_public_row(
                {
                    "flow_sha256": flow,
                    "bind_sha256": bind,
                    "chain_index_sha256": chain,
                    "autonomous_sha256": auto,
                    "status": status,
                }
            )
        )
    public.sort(key=lambda row: str(row["flow_sha256"]))
    body = _flow_index_body(public)
    got = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    if got != sha:
        raise MemoryLayerError("flow_index_mismatch", f"index hashed {got[:12]} not {sha[:12]}")
    return {**body, "matched": True, "flow_receipt_index_sha256": sha, "live_verified": False}


def list_trait_lab_autonomous_flow_workflow_receipt_index_flows(index: Any) -> list[dict[str, Any]]:
    """Flow rows from a verified flow-receipt index."""
    verified = verify_trait_lab_autonomous_flow_workflow_receipt_index(index)
    return list(verified["flows"])


def _flow_receipt_index_fact_id(flow_receipt_index_sha256: str) -> str:
    return f"trait-lab-auto-flow-index-{flow_receipt_index_sha256[:16]}"


def persist_trait_lab_autonomous_flow_workflow_receipt_index(
    store: MemoryStore,
    index: Any,
    *,
    agent_id: str,
    task_id: str,
) -> dict[str, Any]:
    """Persist a signed flow-receipt index snapshot."""
    require_trait_lab_autonomous_flow_workflow_provenance(agent_id=agent_id, task_id=task_id)
    verified = verify_trait_lab_autonomous_flow_workflow_receipt_index(index)
    sha = str(verified["flow_receipt_index_sha256"])
    write_verified(
        store,
        {
            "id": _flow_receipt_index_fact_id(sha),
            "fact": f"autonomous flow receipt index {sha}",
            "how": f"persist_trait_lab_autonomous_flow_workflow_receipt_index {sha}",
            "confidence": 1.0,
            "source": sha,
            "agent_id": agent_id,
            "task_id": task_id,
            "kind": _FLOW_RECEIPT_INDEX_KIND,
            "count": verified["count"],
            "flow_receipt_index_sha256": sha,
        },
    )
    record_task_step(
        store,
        task_id,
        "autonomous-flow-workflow-receipt-index",
        {"flow_receipt_index_sha256": sha},
        agent_id=agent_id,
    )
    return {
        "persisted": True,
        "flow_receipt_index_sha256": sha,
        "fact_id": _flow_receipt_index_fact_id(sha),
        "live_verified": False,
    }


def list_trait_lab_autonomous_flow_workflow_receipts_by_agent(
    store: MemoryStore,
    agent_id: str,
    *,
    limit: int = 50,
) -> dict[str, Any]:
    """O24 — flow receipts for one agent."""
    wanted = str(agent_id or "").strip()
    if not wanted:
        raise MemoryLayerError("missing_agent", "receipts by agent requires agent_id")
    rows = [row for row in _collect_flow_receipts(store) if row.get("agent_id") == wanted]
    if not rows:
        raise MemoryLayerError("missing_agent", f"no flow receipt for agent {wanted}")
    return {
        "kind": _FLOW_RECEIPT_KIND,
        "receipts": rows[:limit],
        "count": len(rows),
        "agent_id": wanted,
        "live_verified": False,
    }


def open_trait_lab_autonomous_flow_workflow(
    *,
    agent_id: str,
    task_id: str,
    environ: Any = None,
) -> dict[str, Any]:
    """O25 — run chained flow and persist flow receipt on the run workspace."""
    plan = sign_trait_lab_autonomous_flow_workflow(plan_trait_lab_autonomous_flow_workflow(["run_chained"]))
    ran = run_trait_lab_autonomous_flow_workflow(
        plan, agent_id=agent_id, task_id=task_id, environ=environ
    )
    last = ran["results"][-1]
    store = MemoryStore(str(last["run"]["workspace"]["store_path"]))
    try:
        receipt = persist_trait_lab_autonomous_flow_workflow_receipt(
            store, ran, agent_id=agent_id, task_id=task_id
        )
    finally:
        store.close()
    return {
        **ran,
        "receipt": receipt,
        "opened": True,
        "flow_persisted": bool(receipt.get("persisted")),
        "ok": bool(ran.get("ok")) and bool(receipt.get("persisted")),
        "status": "ready",
        "live_verified": False,
    }
