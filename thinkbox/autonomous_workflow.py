"""Hermetic autonomous Trait Lab workflow (A01–A15).

Plans and signs prep → session → workflow dry-run chains. Receipt persistence
and full dry-run execution land in A16–A25 (follow-up). No live APIs.
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
from thinkbox.memory_layers import MemoryLayer, MemoryLayerError, query_layer
from thinkbox.operator_session import (
    get_trait_lab_operator_session_receipt,
    require_trait_lab_operator_session_prep_receipt,
)

_AUTO_KIND = "trait-lab-autonomous-workflow"

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
