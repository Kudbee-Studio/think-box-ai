"""Kernel/control-plane hooks: persist admit/capacity/secret/shutdown receipts."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from thinkbox.agent.control_plane.store import ActionReceiptStore

logger = logging.getLogger(__name__)


@dataclass
class HookContext:
    agent_id: str
    action: str
    status: str = "allowed"
    reason: str = ""
    evidence_label: str = "simulated"
    metadata: dict[str, Any] = field(default_factory=dict)


def on_admit(store: ActionReceiptStore, ctx: HookContext) -> None:
    """Called when agent is admitted via admission gate."""
    _persist(store, ctx, action="admit", reason=ctx.reason or "admission granted")


def on_capacity(store: ActionReceiptStore, ctx: HookContext) -> None:
    """Called when orchestration grants capacity."""
    _persist(store, ctx, action="capacity", reason=ctx.reason or "capacity granted")


def on_secret(store: ActionReceiptStore, ctx: HookContext) -> None:
    """Called when orchestration injects secrets."""
    _persist(store, ctx, action="secret", reason=ctx.reason or "secret injected")


def on_shutdown(store: ActionReceiptStore, ctx: HookContext) -> None:
    """Called when agent shuts down."""
    _persist(store, ctx, action="shutdown", reason=ctx.reason or "shutdown")


def _persist(store: ActionReceiptStore, ctx: HookContext, action: str, reason: str) -> None:
    store.append(
        action=action,
        status=ctx.status,
        reason=reason,
        evidence_label=ctx.evidence_label,
        metadata={
            "agent_id": ctx.agent_id,
            **ctx.metadata,
        },
    )
    logger.info("Receipt persisted for %s on %s", action, ctx.agent_id)
