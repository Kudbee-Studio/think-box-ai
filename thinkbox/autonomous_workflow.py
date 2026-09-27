"""Hermetic autonomous Trait Lab workflow (A01–A25).

Plans and signs prep → session → workflow dry-run chains, dry-runs without
writes, and persists autonomous receipts. No live APIs.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from core.memory.store import MemoryStore
from thinkbox.local_env_prep import (
    require_trait_lab_local_env_no_live_ack,
    require_trait_lab_local_env_provenance,
)
from thinkbox.local_env_prep import (
    dry_run_trait_lab_local_env_workflow,
    export_trait_lab_local_env_prep_report,
    persist_trait_lab_local_env_prep_receipt,
    prepare_trait_lab_local_env_workspace,
    verify_trait_lab_local_env_prep_report,
)
from thinkbox.memory_layers import MemoryLayer, MemoryLayerError, query_layer, record_task_step, write_verified
from thinkbox.operator_session import (
    dry_run_trait_lab_operator_session,
    get_trait_lab_operator_session_receipt,
    persist_trait_lab_operator_session_receipt,
    require_trait_lab_operator_session_prep_receipt,
    session_from_prep_trait_lab_operator,
)

_AUTO_KIND = "trait-lab-autonomous-workflow"
_AUTO_RECEIPT_KIND = "trait-lab-autonomous-workflow-receipt"
_AUTO_FACT_PREFIX = "trait-lab-auto-wf-"

TRAIT_LAB_AUTONOMOUS_WORKFLOW_OPS: tuple[str, ...] = (
    "refuse_live",
    "require_prep_receipt",
    "require_session_receipt",
    "require_no_live_ack",
    "require_provenance",
    "plan",
    "validate",
    "sign",
    "verify",
    "list_steps",
    "count_steps",
    "has_step",
    "page_steps",
    "digest",
    "etag",
    "public_row",
    "require_green_session",
    "dry_run",
    "status",
    "persist_receipt",
    "get_receipt",
    "list_receipts",
    "has_receipt",
    "receipts_by_agent",
    "run_autonomous",
)

TRAIT_LAB_AUTONOMOUS_WORKFLOW_STEPS: tuple[str, ...] = (
    "prep",
    "session",
    "workflow_dry_run",
)


def refuse_trait_lab_autonomous_workflow_live(payload: Any) -> None:
    """A01 — autonomous payloads may not claim LIVE VERIFIED."""
    if isinstance(payload, dict) and payload.get("live_verified") is True:
        raise MemoryLayerError("live_claim", "autonomous workflow may not claim LIVE VERIFIED")


def require_trait_lab_autonomous_workflow_prep_receipt(
    store: MemoryStore,
    prep_sha256: str = "",
) -> dict[str, Any]:
    """A02 — fail-closed unless a green prep receipt exists."""
    return require_trait_lab_operator_session_prep_receipt(store, prep_sha256)


def require_trait_lab_autonomous_workflow_session_receipt(
    store: MemoryStore,
    session_sha256: str = "",
) -> dict[str, Any]:
    """A03 — fail-closed unless a session receipt exists."""
    sha = str(session_sha256 or "").strip().lower()
    if sha:
        row = get_trait_lab_operator_session_receipt(store, sha)
        if row.get("status") not in {"dry_run", "ready"}:
            raise MemoryLayerError("blocked_session", "autonomous workflow requires a green session")
        return {**row, "required": True, "live_verified": False}
    for entry in query_layer(
        store,
        MemoryLayer.VERIFIED_KNOWLEDGE,
        prefix="verified:trait-lab-op-session-",
        limit=50,
    ):
        if entry.value.get("live_verified") is True:
            continue
        status = str(entry.value.get("status") or "")
        if status not in {"dry_run", "ready"}:
            continue
        source = str(entry.value.get("source") or "").strip().lower()
        if len(source) != 64:
            continue
        row = get_trait_lab_operator_session_receipt(store, source)
        return {**row, "required": True, "live_verified": False}
    raise MemoryLayerError("missing_session", "autonomous workflow requires a session receipt")


def require_trait_lab_autonomous_workflow_no_live_ack(environ: Any = None) -> dict[str, Any]:
    """A04 — fail-closed when a swarm live ack is present."""
    return require_trait_lab_local_env_no_live_ack(environ)


def require_trait_lab_autonomous_workflow_provenance(*, agent_id: str, task_id: str) -> dict[str, Any]:
    """A05 — fail-closed without agent_id and task_id."""
    return require_trait_lab_local_env_provenance(agent_id=agent_id, task_id=task_id)


def _auto_body(steps: list[str]) -> dict[str, Any]:
    return {
        "kind": _AUTO_KIND,
        "steps": list(steps),
        "count": len(steps),
        "live_verified": False,
    }


def _require_auto_steps(steps: Any) -> list[str]:
    if not isinstance(steps, list) or not steps:
        raise MemoryLayerError("missing_step", "autonomous workflow requires at least one step")
    allowed = set(TRAIT_LAB_AUTONOMOUS_WORKFLOW_STEPS)
    names: list[str] = []
    for item in steps:
        name = str(item or "").strip()
        if name not in allowed:
            raise MemoryLayerError("invalid_step", f"unknown autonomous step {name or '<empty>'}")
        names.append(name)
    return names


def plan_trait_lab_autonomous_workflow(steps: Any) -> dict[str, Any]:
    """A06 — build an unsigned hermetic autonomous plan."""
    names = _require_auto_steps(steps)
    body = _auto_body(names)
    refuse_trait_lab_autonomous_workflow_live(body)
    return body


def validate_trait_lab_autonomous_workflow(plan: Any) -> dict[str, Any]:
    """A07 — fail-closed check of an autonomous plan."""
    if not isinstance(plan, dict):
        raise MemoryLayerError("invalid_autonomous", "autonomous workflow must be an object")
    refuse_trait_lab_autonomous_workflow_live(plan)
    if plan.get("kind") not in {None, _AUTO_KIND}:
        raise MemoryLayerError("invalid_autonomous", "kind must be trait-lab-autonomous-workflow")
    names = _require_auto_steps(plan.get("steps"))
    return {**_auto_body(names), "valid": True}


def sign_trait_lab_autonomous_workflow(plan: Any) -> dict[str, Any]:
    """A08 — sign a validated plan. Not a live ranking."""
    validated = validate_trait_lab_autonomous_workflow(plan)
    body = _auto_body(validated["steps"])
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        **body,
        "autonomous_sha256": hashlib.sha256(encoded).hexdigest(),
        "live_verified": False,
    }


def verify_trait_lab_autonomous_workflow(workflow: Any) -> dict[str, Any]:
    """A09 — rematch autonomous_sha256 over the stable plan body."""
    if not isinstance(workflow, dict):
        raise MemoryLayerError("invalid_autonomous", "autonomous workflow must be an object")
    if workflow.get("kind") != _AUTO_KIND:
        raise MemoryLayerError("invalid_autonomous", "kind must be trait-lab-autonomous-workflow")
    refuse_trait_lab_autonomous_workflow_live(workflow)
    names = _require_auto_steps(workflow.get("steps"))
    sha = str(workflow.get("autonomous_sha256") or "").strip().lower()
    if len(sha) != 64 or any(ch not in "0123456789abcdef" for ch in sha):
        raise MemoryLayerError("missing_autonomous_hash", "verify requires autonomous_sha256")
    body = _auto_body(names)
    got = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    if got != sha:
        raise MemoryLayerError("autonomous_mismatch", f"autonomous hashed {got[:12]} not {sha[:12]}")
    return {**body, "matched": True, "autonomous_sha256": sha, "live_verified": False}


def list_trait_lab_autonomous_workflow_steps(plan: Any) -> list[str]:
    """A10 — step names from a plan or signed workflow."""
    return list(validate_trait_lab_autonomous_workflow(plan)["steps"])


def count_trait_lab_autonomous_workflow_steps(plan: Any) -> int:
    """A11 — number of steps in a plan."""
    return int(validate_trait_lab_autonomous_workflow(plan)["count"])


def trait_lab_autonomous_workflow_has_step(plan: Any, step: str) -> bool:
    """A12 — true when the plan lists the step name."""
    name = str(step or "").strip()
    if name not in TRAIT_LAB_AUTONOMOUS_WORKFLOW_STEPS:
        raise MemoryLayerError("invalid_step", f"unknown autonomous step {name or '<empty>'}")
    return name in list_trait_lab_autonomous_workflow_steps(plan)


def page_trait_lab_autonomous_workflow_steps(
    plan: Any,
    *,
    offset: int = 0,
    limit: int = 50,
) -> dict[str, Any]:
    """A13 — deterministic step page."""
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise MemoryLayerError("invalid_limit", "limit must be >= 1")
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
        raise MemoryLayerError("invalid_offset", "offset must be >= 0")
    names = list_trait_lab_autonomous_workflow_steps(plan)
    return {
        "kind": _AUTO_KIND,
        "steps": names[offset : offset + limit],
        "count": len(names),
        "offset": offset,
        "limit": limit,
        "live_verified": False,
    }


def trait_lab_autonomous_workflow_digest(plan: Any) -> str:
    """A14 — SHA-256 over the stable signed plan body."""
    return str(sign_trait_lab_autonomous_workflow(plan)["autonomous_sha256"])


def trait_lab_autonomous_workflow_etag(plan: Any) -> str:
    """A15 — short digest for autonomous identity."""
    return trait_lab_autonomous_workflow_digest(plan)[:16]


def public_trait_lab_autonomous_workflow_row(row: dict[str, Any]) -> dict[str, Any]:
    """A16 — stable plan row without agent/task fields."""
    validated = validate_trait_lab_autonomous_workflow(row)
    public = _auto_body(validated["steps"])
    sha = str(row.get("autonomous_sha256") or "").strip().lower()
    if sha:
        public = {**sign_trait_lab_autonomous_workflow(public), "live_verified": False}
        if sha != public["autonomous_sha256"]:
            raise MemoryLayerError("autonomous_mismatch", "public row hash disagrees")
    return public


def require_trait_lab_autonomous_workflow_green_session(
    store: MemoryStore,
    session_sha256: str = "",
) -> dict[str, Any]:
    """A17 — fail-closed unless a green (ok) session receipt exists."""
    row = require_trait_lab_autonomous_workflow_session_receipt(store, session_sha256)
    if not row.get("ok", True):
        raise MemoryLayerError("blocked_session", "autonomous workflow requires a green session")
    status = str(row.get("status") or "")
    if status not in {"dry_run", "ready"}:
        raise MemoryLayerError("blocked_session", "autonomous workflow session is not green")
    return {**row, "green": True, "live_verified": False}


def _execute_autonomous_step(
    store: MemoryStore,
    step: str,
    ctx: dict[str, Any],
    *,
    dry_run: bool,
    agent_id: str,
    task_id: str,
    environ: Any,
) -> dict[str, Any]:
    if step == "prep":
        report = export_trait_lab_local_env_prep_report(
            agent_id=agent_id,
            task_id=task_id,
            environ=environ,
            store_path=store.db_path,
        )
        verified = verify_trait_lab_local_env_prep_report(report)
        if not verified.get("ok"):
            raise MemoryLayerError("blocked_prep", "autonomous prep report is not green")
        ctx["report"] = report
        ctx["prep_sha256"] = report["prep_sha256"]
        wrote = False
        if not dry_run:
            persist_trait_lab_local_env_prep_receipt(
                store, report, agent_id=agent_id, task_id=task_id
            )
            wrote = True
        return {
            "step": step,
            "ok": True,
            "wrote": wrote,
            "prep_sha256": report["prep_sha256"],
            "live_verified": False,
        }
    if step == "session":
        inline_prep = ctx.get("report")
        if isinstance(inline_prep, dict) and verify_trait_lab_local_env_prep_report(inline_prep).get("ok"):
            pass
        else:
            require_trait_lab_autonomous_workflow_prep_receipt(
                store, str(ctx.get("prep_sha256") or "")
            )
        session_plan = session_from_prep_trait_lab_operator()
        ran = dry_run_trait_lab_operator_session(
            store,
            session_plan,
            agent_id=agent_id,
            task_id=task_id,
            environ=environ,
            prep_sha256=str(ctx.get("prep_sha256") or ""),
        )
        if ran.get("wrote"):
            raise MemoryLayerError("invalid_autonomous", "autonomous session step must not write")
        ctx["session"] = ran
        ctx["session_sha256"] = ran.get("session_sha256")
        return {
            "step": step,
            "ok": bool(ran.get("ok")),
            "wrote": False,
            "session_sha256": ran.get("session_sha256"),
            "status": ran.get("status"),
            "live_verified": False,
        }
    if step == "workflow_dry_run":
        inline = ctx.get("session")
        if isinstance(inline, dict) and inline.get("status") == "dry_run" and inline.get("ok"):
            pass
        else:
            require_trait_lab_autonomous_workflow_green_session(
                store, str(ctx.get("session_sha256") or "")
            )
        ran = dry_run_trait_lab_local_env_workflow(store, agent_id=agent_id, task_id=task_id)
        if ran.get("wrote"):
            raise MemoryLayerError("invalid_autonomous", "autonomous workflow dry-run must not write")
        ctx["workflow"] = ran
        return {
            "step": step,
            "ok": ran.get("status") == "dry_run",
            "wrote": False,
            "status": ran.get("status"),
            "live_verified": False,
        }
    raise MemoryLayerError("invalid_step", f"unknown autonomous step {step}")


def dry_run_trait_lab_autonomous_workflow(
    store: MemoryStore,
    plan: Any,
    *,
    agent_id: str,
    task_id: str,
    environ: Any = None,
    prep_sha256: str = "",
    session_sha256: str = "",
) -> dict[str, Any]:
    """A18 — execute autonomous steps without writes."""
    require_trait_lab_autonomous_workflow_provenance(agent_id=agent_id, task_id=task_id)
    require_trait_lab_autonomous_workflow_no_live_ack(environ)
    signed = sign_trait_lab_autonomous_workflow(plan)
    refuse_trait_lab_autonomous_workflow_live(signed)
    ctx: dict[str, Any] = {}
    if prep_sha256:
        ctx["prep_sha256"] = prep_sha256
    if session_sha256:
        ctx["session_sha256"] = session_sha256
        require_trait_lab_autonomous_workflow_green_session(store, session_sha256)
    results: list[dict[str, Any]] = []
    for step in signed["steps"]:
        results.append(
            _execute_autonomous_step(
                store,
                step,
                ctx,
                dry_run=True,
                agent_id=agent_id,
                task_id=task_id,
                environ=environ,
            )
        )
    if any(row.get("wrote") for row in results):
        raise MemoryLayerError("invalid_autonomous", "autonomous dry-run must not write")
    return {
        **signed,
        "results": results,
        "prep_sha256": ctx.get("prep_sha256"),
        "session_sha256": ctx.get("session_sha256"),
        "status": "dry_run",
        "ok": all(bool(row.get("ok")) for row in results),
        "wrote": False,
        "live_verified": False,
    }


def trait_lab_autonomous_workflow_status(result: Any) -> str:
    """A19 — dry_run, ready, blocked, or planned."""
    if not isinstance(result, dict):
        raise MemoryLayerError("invalid_autonomous", "autonomous status requires a result")
    refuse_trait_lab_autonomous_workflow_live(result)
    if result.get("status") == "dry_run":
        return "dry_run"
    if result.get("persisted") is True or result.get("ran") is True:
        return "ready"
    if result.get("ok") is False:
        return "blocked"
    if result.get("steps"):
        return "planned"
    raise MemoryLayerError("invalid_autonomous", "autonomous status is missing")


def _auto_fact_id(autonomous_sha256: str) -> str:
    return f"{_AUTO_FACT_PREFIX}{autonomous_sha256[:16]}"


def persist_trait_lab_autonomous_workflow_receipt(
    store: MemoryStore,
    result: Any,
    *,
    agent_id: str,
    task_id: str,
) -> dict[str, Any]:
    """A20 — write an autonomous receipt fact. Does not apply packs or runs."""
    require_trait_lab_autonomous_workflow_provenance(agent_id=agent_id, task_id=task_id)
    if not isinstance(result, dict) or not result.get("autonomous_sha256"):
        raise MemoryLayerError("invalid_autonomous", "receipt requires a signed autonomous result")
    refuse_trait_lab_autonomous_workflow_live(result)
    verified = verify_trait_lab_autonomous_workflow(result)
    status = trait_lab_autonomous_workflow_status(result)
    sha = str(verified["autonomous_sha256"])
    prep_sha = str(result.get("prep_sha256") or "").strip().lower()
    session_sha = str(result.get("session_sha256") or "").strip().lower()
    write_verified(
        store,
        {
            "id": _auto_fact_id(sha),
            "fact": f"autonomous workflow {sha} status={status}",
            "how": f"persist_trait_lab_autonomous_workflow_receipt {sha}",
            "confidence": 1.0,
            "source": sha,
            "agent_id": agent_id,
            "task_id": task_id,
            "kind": _AUTO_RECEIPT_KIND,
            "status": status,
            "steps": verified["steps"],
            "count": verified["count"],
            "prep_sha256": prep_sha,
            "session_sha256": session_sha,
            "ok": bool(result.get("ok", True)),
        },
    )
    record_task_step(
        store,
        task_id,
        "autonomous-workflow",
        {
            "autonomous_sha256": sha,
            "status": status,
            "prep_sha256": prep_sha,
            "session_sha256": session_sha,
        },
        agent_id=agent_id,
    )
    return {
        "persisted": True,
        "autonomous_sha256": sha,
        "fact_id": _auto_fact_id(sha),
        "status": status,
        "prep_sha256": prep_sha,
        "session_sha256": session_sha,
        "live_verified": False,
    }


def _auto_receipt_row(entry: Any) -> dict[str, Any] | None:
    if not str(entry.key).startswith("verified:trait-lab-auto-wf-"):
        return None
    if entry.value.get("live_verified") is True:
        return None
    sha = str(entry.value.get("source") or "").strip().lower()
    if len(sha) != 64 or any(ch not in "0123456789abcdef" for ch in sha):
        return None
    status = str(entry.value.get("status") or "").strip()
    if status not in {"dry_run", "ready", "blocked", "planned"}:
        return None
    raw_steps = entry.value.get("steps")
    if not isinstance(raw_steps, list):
        return None
    prep_sha = str(entry.value.get("prep_sha256") or "").strip().lower()
    session_sha = str(entry.value.get("session_sha256") or "").strip().lower()
    return {
        "kind": _AUTO_RECEIPT_KIND,
        "autonomous_sha256": sha,
        "fact_id": _auto_fact_id(sha),
        "status": status,
        "steps": [str(item) for item in raw_steps],
        "count": int(entry.value.get("count") or len(raw_steps)),
        "prep_sha256": prep_sha,
        "session_sha256": session_sha,
        "ok": bool(entry.value.get("ok", True)),
        "agent_id": entry.agent_id,
        "task_id": entry.task_id,
        "live_verified": False,
    }


def _collect_autonomous_receipts(store: MemoryStore, *, scan: int = 200) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in query_layer(
        store,
        MemoryLayer.VERIFIED_KNOWLEDGE,
        prefix="verified:trait-lab-auto-wf-",
        limit=scan,
    ):
        row = _auto_receipt_row(entry)
        if row is None or row["autonomous_sha256"] in seen:
            continue
        seen.add(row["autonomous_sha256"])
        found.append(row)
    found.sort(key=lambda row: str(row["autonomous_sha256"]))
    return found


def get_trait_lab_autonomous_workflow_receipt(
    store: MemoryStore,
    autonomous_sha256: str,
) -> dict[str, Any]:
    """A21 — select one autonomous receipt by autonomous_sha256."""
    sha = str(autonomous_sha256 or "").strip().lower()
    if len(sha) != 64 or any(ch not in "0123456789abcdef" for ch in sha):
        raise MemoryLayerError("missing_autonomous_hash", "receipt select requires autonomous_sha256")
    entry = store.get(f"verified:{_auto_fact_id(sha)}")
    if entry is None:
        raise MemoryLayerError("missing_autonomous", f"no autonomous workflow receipt {sha[:12]}")
    row = _auto_receipt_row(entry)
    if row is None:
        raise MemoryLayerError("invalid_autonomous", f"autonomous receipt {sha[:12]} is malformed")
    return {**row, "live_verified": False}


def list_trait_lab_autonomous_workflow_receipts(store: MemoryStore, *, limit: int = 50) -> dict[str, Any]:
    """A22 — index persisted autonomous receipts."""
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise MemoryLayerError("invalid_limit", "limit must be >= 1")
    rows = _collect_autonomous_receipts(store)[:limit]
    public = [
        {
            "autonomous_sha256": row["autonomous_sha256"],
            "fact_id": row["fact_id"],
            "kind": _AUTO_RECEIPT_KIND,
            "status": row["status"],
            "prep_sha256": row["prep_sha256"],
            "session_sha256": row["session_sha256"],
            "count": row["count"],
            "live_verified": False,
        }
        for row in rows
    ]
    return {
        "kind": _AUTO_RECEIPT_KIND,
        "receipts": public,
        "count": len(rows),
        "live_verified": False,
    }


def has_trait_lab_autonomous_workflow_receipt(store: MemoryStore, autonomous_sha256: str) -> bool:
    """A23 — true when an autonomous receipt exists."""
    sha = str(autonomous_sha256 or "").strip().lower()
    if len(sha) != 64 or any(ch not in "0123456789abcdef" for ch in sha):
        raise MemoryLayerError("missing_autonomous_hash", "has_receipt requires autonomous_sha256")
    return any(row["autonomous_sha256"] == sha for row in _collect_autonomous_receipts(store))


def list_trait_lab_autonomous_workflow_receipts_by_agent(
    store: MemoryStore,
    agent_id: str,
    *,
    limit: int = 50,
) -> dict[str, Any]:
    """A24 — receipts written by one agent."""
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise MemoryLayerError("invalid_limit", "limit must be >= 1")
    wanted = str(agent_id or "").strip()
    if not wanted:
        raise MemoryLayerError("missing_agent", "autonomous receipt by agent requires agent_id")
    rows = [row for row in _collect_autonomous_receipts(store) if row.get("agent_id") == wanted]
    if not rows:
        raise MemoryLayerError("missing_agent", f"no autonomous workflow receipt for agent {wanted}")
    return {
        "kind": _AUTO_RECEIPT_KIND,
        "receipts": [
            {
                "autonomous_sha256": row["autonomous_sha256"],
                "fact_id": row["fact_id"],
                "kind": _AUTO_RECEIPT_KIND,
                "status": row["status"],
                "prep_sha256": row["prep_sha256"],
                "session_sha256": row["session_sha256"],
                "count": row["count"],
                "live_verified": False,
            }
            for row in rows[:limit]
        ],
        "count": len(rows),
        "agent_id": wanted,
        "live_verified": False,
    }


def workflow_from_session_trait_lab_autonomous(session: Any = None) -> dict[str, Any]:
    """Build canned prep → session → workflow dry-run plan (used by A25 run_autonomous)."""
    signed = sign_trait_lab_autonomous_workflow(
        plan_trait_lab_autonomous_workflow(["prep", "session", "workflow_dry_run"])
    )
    if isinstance(session, dict):
        sha = str(session.get("session_sha256") or "").strip().lower()
        if sha:
            return {**signed, "session_sha256": sha, "live_verified": False}
    return signed


def run_trait_lab_autonomous(
    *,
    agent_id: str,
    task_id: str,
    environ: Any = None,
) -> dict[str, Any]:
    """A25 — prepare workspace, dry-run autonomous chain, persist receipts."""
    require_trait_lab_autonomous_workflow_provenance(agent_id=agent_id, task_id=task_id)
    require_trait_lab_autonomous_workflow_no_live_ack(environ)
    workspace = prepare_trait_lab_local_env_workspace()
    store = MemoryStore(workspace["store_path"])
    try:
        session_plan = session_from_prep_trait_lab_operator()
        session_dry = dry_run_trait_lab_operator_session(
            store, session_plan, agent_id=agent_id, task_id=task_id, environ=environ
        )
        persist_trait_lab_local_env_prep_receipt(
            store,
            export_trait_lab_local_env_prep_report(
                agent_id=agent_id,
                task_id=task_id,
                environ=environ,
                store_path=workspace["store_path"],
            ),
            agent_id=agent_id,
            task_id=task_id,
        )
        session_receipt = persist_trait_lab_operator_session_receipt(
            store, session_dry, agent_id=agent_id, task_id=task_id
        )
        plan = workflow_from_session_trait_lab_autonomous(session_receipt)
        auto_dry = dry_run_trait_lab_autonomous_workflow(
            store,
            plan,
            agent_id=agent_id,
            task_id=task_id,
            environ=environ,
            prep_sha256=str(session_dry.get("prep_sha256") or ""),
            session_sha256=str(session_dry.get("session_sha256") or ""),
        )
        auto_receipt = persist_trait_lab_autonomous_workflow_receipt(
            store, auto_dry, agent_id=agent_id, task_id=task_id
        )
    finally:
        store.close()
    return {
        "kind": _AUTO_KIND,
        "workspace": workspace,
        "session_receipt": session_receipt,
        "autonomous": auto_dry,
        "receipt": auto_receipt,
        "ran": True,
        "ok": bool(auto_dry.get("ok")) and bool(auto_receipt.get("persisted")),
        "status": "ready",
        "live_verified": False,
    }
