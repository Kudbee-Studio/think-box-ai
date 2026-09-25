"""Hermetic operator session that gates workflow dry-run behind local env prep.

Chains GitHub #213 prep with GitHub #212 rematch dry-run. Persists a session
receipt. Does not call live APIs and does not run pin/drop writes.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from core.memory.store import MemoryStore
from thinkbox.local_env_prep import (
    dry_run_trait_lab_local_env_workflow,
    export_trait_lab_local_env_prep_report,
    get_trait_lab_local_env_prep_receipt,
    list_trait_lab_local_env_prep_receipts,
    persist_trait_lab_local_env_prep_receipt,
    prepare_trait_lab_local_env_workspace,
    require_trait_lab_local_env_no_live_ack,
    require_trait_lab_local_env_provenance,
    verify_trait_lab_local_env_prep_report,
)
from thinkbox.memory_layers import (
    MemoryLayer,
    MemoryLayerError,
    query_layer,
    record_task_step,
    write_verified,
)

_SESSION_KIND = "trait-lab-operator-session"
_SESSION_RECEIPT_KIND = "trait-lab-operator-session-receipt"
_SESSION_FACT_PREFIX = "trait-lab-op-session-"

TRAIT_LAB_OPERATOR_SESSION_OPS: tuple[str, ...] = (
    "refuse_live",
    "require_prep_ok",
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
    "require_prep_receipt",
    "dry_run",
    "status",
    "persist_receipt",
    "get_receipt",
    "list_receipts",
    "has_receipt",
    "receipts_by_agent",
    "session_from_prep",
    "open_session",
)

TRAIT_LAB_OPERATOR_SESSION_STEPS: tuple[str, ...] = (
    "prep",
    "require_prep",
    "dry_run",
)


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def refuse_trait_lab_operator_session_live(payload: Any) -> None:
    """S01 — session payloads may not claim LIVE VERIFIED."""
    if isinstance(payload, dict) and payload.get("live_verified") is True:
        raise MemoryLayerError("live_claim", "operator session may not claim LIVE VERIFIED")


def require_trait_lab_operator_session_prep_ok(report: Any) -> dict[str, Any]:
    """S02 — fail-closed unless a rematched prep report is ok."""
    verified = verify_trait_lab_local_env_prep_report(report)
    if not verified.get("ok"):
        raise MemoryLayerError("blocked_prep", "operator session requires a green local env prep")
    return {**verified, "required": True, "live_verified": False}


def require_trait_lab_operator_session_no_live_ack(environ: Any = None) -> dict[str, Any]:
    """S03 — fail-closed when a swarm live ack is present."""
    return require_trait_lab_local_env_no_live_ack(environ)


def require_trait_lab_operator_session_provenance(*, agent_id: str, task_id: str) -> dict[str, Any]:
    """S04 — fail-closed without agent_id and task_id."""
    return require_trait_lab_local_env_provenance(agent_id=agent_id, task_id=task_id)


def _session_body(steps: list[str]) -> dict[str, Any]:
    return {
        "kind": _SESSION_KIND,
        "steps": list(steps),
        "count": len(steps),
        "live_verified": False,
    }


def _require_session_steps(steps: Any) -> list[str]:
    if not isinstance(steps, list) or not steps:
        raise MemoryLayerError("missing_step", "operator session requires at least one step")
    allowed = set(TRAIT_LAB_OPERATOR_SESSION_STEPS)
    names: list[str] = []
    for item in steps:
        name = str(item or "").strip()
        if name not in allowed:
            raise MemoryLayerError("invalid_step", f"unknown operator session step {name or '<empty>'}")
        names.append(name)
    return names


def plan_trait_lab_operator_session(steps: Any) -> dict[str, Any]:
    """S05 — build an unsigned hermetic session plan."""
    names = _require_session_steps(steps)
    body = _session_body(names)
    refuse_trait_lab_operator_session_live(body)
    return body


def validate_trait_lab_operator_session(plan: Any) -> dict[str, Any]:
    """S06 — fail-closed check of a session plan."""
    if not isinstance(plan, dict):
        raise MemoryLayerError("invalid_session", "operator session must be an object")
    refuse_trait_lab_operator_session_live(plan)
    if plan.get("kind") not in {None, _SESSION_KIND}:
        raise MemoryLayerError("invalid_session", "kind must be trait-lab-operator-session")
    names = _require_session_steps(plan.get("steps"))
    return {**_session_body(names), "valid": True}


def sign_trait_lab_operator_session(plan: Any) -> dict[str, Any]:
    """S07 — sign a validated plan. Not a live ranking."""
    validated = validate_trait_lab_operator_session(plan)
    body = _session_body(validated["steps"])
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        **body,
        "session_sha256": hashlib.sha256(encoded).hexdigest(),
        "live_verified": False,
    }


def verify_trait_lab_operator_session(session: Any) -> dict[str, Any]:
    """S08 — rematch session_sha256 over the stable plan body."""
    if not isinstance(session, dict):
        raise MemoryLayerError("invalid_session", "operator session must be an object")
    if session.get("kind") != _SESSION_KIND:
        raise MemoryLayerError("invalid_session", "kind must be trait-lab-operator-session")
    refuse_trait_lab_operator_session_live(session)
    names = _require_session_steps(session.get("steps"))
    sha = str(session.get("session_sha256") or "").strip().lower()
    if len(sha) != 64 or any(ch not in "0123456789abcdef" for ch in sha):
        raise MemoryLayerError("missing_session_hash", "verify requires session_sha256")
    body = _session_body(names)
    got = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    if got != sha:
        raise MemoryLayerError("session_mismatch", f"session hashed {got[:12]} not {sha[:12]}")
    return {**body, "matched": True, "session_sha256": sha, "live_verified": False}


def list_trait_lab_operator_session_steps(plan: Any) -> list[str]:
    """S09 — step names from a plan or signed session."""
    return list(validate_trait_lab_operator_session(plan)["steps"])


def count_trait_lab_operator_session_steps(plan: Any) -> int:
    """S10 — number of steps in a plan."""
    return int(validate_trait_lab_operator_session(plan)["count"])


def trait_lab_operator_session_has_step(plan: Any, step: str) -> bool:
    """S11 — true when the plan lists the step name."""
    name = str(step or "").strip()
    if name not in TRAIT_LAB_OPERATOR_SESSION_STEPS:
        raise MemoryLayerError("invalid_step", f"unknown operator session step {name or '<empty>'}")
    return name in list_trait_lab_operator_session_steps(plan)


def page_trait_lab_operator_session_steps(
    plan: Any,
    *,
    offset: int = 0,
    limit: int = 50,
) -> dict[str, Any]:
    """S12 — deterministic step page."""
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise MemoryLayerError("invalid_limit", "limit must be >= 1")
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
        raise MemoryLayerError("invalid_offset", "offset must be >= 0")
    names = list_trait_lab_operator_session_steps(plan)
    return {
        "kind": _SESSION_KIND,
        "steps": names[offset : offset + limit],
        "count": len(names),
        "offset": offset,
        "limit": limit,
        "live_verified": False,
    }


def trait_lab_operator_session_digest(plan: Any) -> str:
    """S13 — SHA-256 over the stable signed plan body."""
    return str(sign_trait_lab_operator_session(plan)["session_sha256"])


def trait_lab_operator_session_etag(plan: Any) -> str:
    """S14 — short digest for session identity."""
    return trait_lab_operator_session_digest(plan)[:16]


def public_trait_lab_operator_session_row(row: dict[str, Any]) -> dict[str, Any]:
    """S15 — stable plan row without agent/task fields."""
    validated = validate_trait_lab_operator_session(row)
    public = _session_body(validated["steps"])
    sha = str(row.get("session_sha256") or "").strip().lower()
    if sha:
        public = {**sign_trait_lab_operator_session(public), "live_verified": False}
        if sha != public["session_sha256"]:
            raise MemoryLayerError("session_mismatch", "public row hash disagrees")
    return public


def require_trait_lab_operator_session_prep_receipt(
    store: MemoryStore,
    prep_sha256: str = "",
) -> dict[str, Any]:
    """S16 — fail-closed unless a green prep receipt exists."""
    sha = str(prep_sha256 or "").strip().lower()
    if sha:
        row = get_trait_lab_local_env_prep_receipt(store, sha)
        if not row.get("ok"):
            raise MemoryLayerError("blocked_prep", "operator session prep receipt is not green")
        return {**row, "required": True, "live_verified": False}
    listed = list_trait_lab_local_env_prep_receipts(store)
    green = [row for row in listed.get("receipts") or [] if row.get("ok")]
    if not green:
        raise MemoryLayerError("missing_prep", "operator session requires a green prep receipt")
    return {**green[0], "required": True, "live_verified": False}


def _execute_session_step(
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
        require_trait_lab_operator_session_prep_ok(report)
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
    if step == "require_prep":
        row = require_trait_lab_operator_session_prep_receipt(
            store, str(ctx.get("prep_sha256") or "")
        )
        ctx["prep_sha256"] = row["prep_sha256"]
        return {
            "step": step,
            "ok": True,
            "wrote": False,
            "prep_sha256": row["prep_sha256"],
            "live_verified": False,
        }
    if step == "dry_run":
        ran = dry_run_trait_lab_local_env_workflow(store, agent_id=agent_id, task_id=task_id)
        if ran.get("wrote"):
            raise MemoryLayerError("invalid_session", "operator session dry-run must not write")
        ctx["dry_run"] = ran
        return {
            "step": step,
            "ok": ran.get("status") == "dry_run",
            "wrote": False,
            "status": ran.get("status"),
            "live_verified": False,
        }
    raise MemoryLayerError("invalid_step", f"unknown operator session step {step}")


def dry_run_trait_lab_operator_session(
    store: MemoryStore,
    plan: Any,
    *,
    agent_id: str,
    task_id: str,
    environ: Any = None,
    prep_sha256: str = "",
) -> dict[str, Any]:
    """S17 — execute session steps without writes."""
    require_trait_lab_operator_session_provenance(agent_id=agent_id, task_id=task_id)
    require_trait_lab_operator_session_no_live_ack(environ)
    signed = sign_trait_lab_operator_session(plan)
    refuse_trait_lab_operator_session_live(signed)
    ctx: dict[str, Any] = {}
    if prep_sha256:
        ctx["prep_sha256"] = prep_sha256
    results: list[dict[str, Any]] = []
    for step in signed["steps"]:
        results.append(
            _execute_session_step(
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
        raise MemoryLayerError("invalid_session", "operator session dry-run must not write")
    return {
        **signed,
        "results": results,
        "prep_sha256": ctx.get("prep_sha256"),
        "status": "dry_run",
        "ok": all(bool(row.get("ok")) for row in results),
        "wrote": False,
        "live_verified": False,
    }


def trait_lab_operator_session_status(result: Any) -> str:
    """S18 — dry_run, ready, blocked, or planned."""
    if not isinstance(result, dict):
        raise MemoryLayerError("invalid_session", "session status requires a result")
    refuse_trait_lab_operator_session_live(result)
    if result.get("status") == "dry_run":
        return "dry_run"
    if result.get("persisted") is True or result.get("opened") is True:
        return "ready"
    if result.get("ok") is False:
        return "blocked"
    if result.get("steps"):
        return "planned"
    raise MemoryLayerError("invalid_session", "session status is missing")


def _session_fact_id(session_sha256: str) -> str:
    return f"{_SESSION_FACT_PREFIX}{session_sha256[:16]}"


def persist_trait_lab_operator_session_receipt(
    store: MemoryStore,
    result: Any,
    *,
    agent_id: str,
    task_id: str,
) -> dict[str, Any]:
    """S19 — write a session receipt fact. Does not apply packs or runs."""
    require_trait_lab_operator_session_provenance(agent_id=agent_id, task_id=task_id)
    if not isinstance(result, dict) or not result.get("session_sha256"):
        raise MemoryLayerError("invalid_session", "receipt requires a signed session result")
    refuse_trait_lab_operator_session_live(result)
    verified = verify_trait_lab_operator_session(result)
    status = trait_lab_operator_session_status(result)
    sha = str(verified["session_sha256"])
    prep_sha = str(result.get("prep_sha256") or "").strip().lower()
    write_verified(
        store,
        {
            "id": _session_fact_id(sha),
            "fact": f"operator session {sha} status={status}",
            "how": f"persist_trait_lab_operator_session_receipt {sha}",
            "confidence": 1.0,
            "source": sha,
            "agent_id": agent_id,
            "task_id": task_id,
            "kind": _SESSION_RECEIPT_KIND,
            "status": status,
            "steps": verified["steps"],
            "count": verified["count"],
            "prep_sha256": prep_sha,
            "ok": bool(result.get("ok", True)),
        },
    )
    record_task_step(
        store,
        task_id,
        "operator-session",
        {"session_sha256": sha, "status": status, "prep_sha256": prep_sha},
        agent_id=agent_id,
    )
    return {
        "persisted": True,
        "session_sha256": sha,
        "fact_id": _session_fact_id(sha),
        "status": status,
        "prep_sha256": prep_sha,
        "live_verified": False,
    }


def _session_receipt_row(entry: Any) -> dict[str, Any] | None:
    if not str(entry.key).startswith("verified:trait-lab-op-session-"):
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
    return {
        "kind": _SESSION_RECEIPT_KIND,
        "session_sha256": sha,
        "fact_id": _session_fact_id(sha),
        "status": status,
        "steps": [str(item) for item in raw_steps],
        "count": int(entry.value.get("count") or len(raw_steps)),
        "prep_sha256": prep_sha,
        "ok": bool(entry.value.get("ok", True)),
        "agent_id": entry.agent_id,
        "task_id": entry.task_id,
        "live_verified": False,
    }


def _collect_session_receipts(store: MemoryStore, *, scan: int = 200) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in query_layer(
        store,
        MemoryLayer.VERIFIED_KNOWLEDGE,
        prefix="verified:trait-lab-op-session-",
        limit=scan,
    ):
        row = _session_receipt_row(entry)
        if row is None or row["session_sha256"] in seen:
            continue
        seen.add(row["session_sha256"])
        found.append(row)
    found.sort(key=lambda row: str(row["session_sha256"]))
    return found


def get_trait_lab_operator_session_receipt(store: MemoryStore, session_sha256: str) -> dict[str, Any]:
    """S20 — select one session receipt by session_sha256."""
    sha = str(session_sha256 or "").strip().lower()
    if len(sha) != 64 or any(ch not in "0123456789abcdef" for ch in sha):
        raise MemoryLayerError("missing_session_hash", "receipt select requires session_sha256")
    entry = store.get(f"verified:{_session_fact_id(sha)}")
    if entry is None:
        raise MemoryLayerError("missing_session", f"no operator session receipt {sha[:12]}")
    row = _session_receipt_row(entry)
    if row is None:
        raise MemoryLayerError("invalid_session", f"operator session receipt {sha[:12]} is malformed")
    return {**row, "live_verified": False}


def list_trait_lab_operator_session_receipts(store: MemoryStore, *, limit: int = 50) -> dict[str, Any]:
    """S21 — index persisted session receipts."""
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise MemoryLayerError("invalid_limit", "limit must be >= 1")
    rows = _collect_session_receipts(store)[:limit]
    public = [
        {
            "session_sha256": row["session_sha256"],
            "fact_id": row["fact_id"],
            "kind": _SESSION_RECEIPT_KIND,
            "status": row["status"],
            "prep_sha256": row["prep_sha256"],
            "count": row["count"],
            "live_verified": False,
        }
        for row in rows
    ]
    return {
        "kind": _SESSION_RECEIPT_KIND,
        "receipts": public,
        "count": len(rows),
        "live_verified": False,
    }


def has_trait_lab_operator_session_receipt(store: MemoryStore, session_sha256: str) -> bool:
    """S22 — true when a session receipt exists."""
    sha = str(session_sha256 or "").strip().lower()
    if len(sha) != 64 or any(ch not in "0123456789abcdef" for ch in sha):
        raise MemoryLayerError("missing_session_hash", "has_receipt requires session_sha256")
    return any(row["session_sha256"] == sha for row in _collect_session_receipts(store))


def list_trait_lab_operator_session_receipts_by_agent(
    store: MemoryStore,
    agent_id: str,
    *,
    limit: int = 50,
) -> dict[str, Any]:
    """S23 — receipts written by one agent."""
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise MemoryLayerError("invalid_limit", "limit must be >= 1")
    wanted = str(agent_id or "").strip()
    if not wanted:
        raise MemoryLayerError("missing_agent", "session receipt by agent requires agent_id")
    rows = [row for row in _collect_session_receipts(store) if row.get("agent_id") == wanted]
    if not rows:
        raise MemoryLayerError("missing_agent", f"no operator session receipt for agent {wanted}")
    return {
        "kind": _SESSION_RECEIPT_KIND,
        "receipts": [
            {
                "session_sha256": row["session_sha256"],
                "fact_id": row["fact_id"],
                "kind": _SESSION_RECEIPT_KIND,
                "status": row["status"],
                "prep_sha256": row["prep_sha256"],
                "count": row["count"],
                "live_verified": False,
            }
            for row in rows[:limit]
        ],
        "count": len(rows),
        "agent_id": wanted,
        "live_verified": False,
    }


def session_from_prep_trait_lab_operator() -> dict[str, Any]:
    """S24 — canned prep then rematch dry-run plan."""
    return sign_trait_lab_operator_session(plan_trait_lab_operator_session(["prep", "dry_run"]))


def open_trait_lab_operator_session(
    *,
    agent_id: str,
    task_id: str,
    environ: Any = None,
) -> dict[str, Any]:
    """S25 — prepare workspace, dry-run session, persist prep + session receipts."""
    require_trait_lab_operator_session_provenance(agent_id=agent_id, task_id=task_id)
    require_trait_lab_operator_session_no_live_ack(environ)
    workspace = prepare_trait_lab_local_env_workspace()
    store = MemoryStore(workspace["store_path"])
    try:
        plan = session_from_prep_trait_lab_operator()
        dry = dry_run_trait_lab_operator_session(
            store, plan, agent_id=agent_id, task_id=task_id, environ=environ
        )
        report = dry.get("results") and next(
            (row for row in dry["results"] if row.get("prep_sha256")),
            None,
        )
        if dry.get("prep_sha256") and report is not None:
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
        receipt = persist_trait_lab_operator_session_receipt(
            store, dry, agent_id=agent_id, task_id=task_id
        )
    finally:
        store.close()
    return {
        "kind": _SESSION_KIND,
        "workspace": workspace,
        "session": dry,
        "receipt": receipt,
        "opened": True,
        "ok": bool(dry.get("ok")) and bool(receipt.get("persisted")),
        "status": "ready",
        "live_verified": False,
    }
