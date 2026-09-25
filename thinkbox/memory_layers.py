"""Four memory layers — Session, Task, Organizational, Verified Knowledge.

Markdown ingest is a catalog plus fail-closed writes. Organizational rows
need evidence. Nothing in these layers may claim LIVE VERIFIED.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.memory.schema import MemoryEntry, MemoryEntryType, MemoryLayer
from core.memory.store import MemoryStore

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".pytest_cache", ".mypy_cache", "think_box_ai.egg-info"}


class MemoryLayerError(ValueError):
    """Fail-closed memory-layer write."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def catalog_markdown(root: Path) -> list[dict[str, Any]]:
    """List markdown files under ``root``. Skips VCS and cache trees."""
    rows: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*.md")):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        title = ""
        for line in text.splitlines():
            if line.startswith("# "):
                title = line[2:].strip()
                break
        rows.append(
            {
                "path": str(path.relative_to(root)),
                "bytes": len(text),
                "title": title,
            }
        )
    return rows


def _force_not_live(payload: dict[str, Any]) -> dict[str, Any]:
    body = dict(payload)
    body["live_verified"] = False
    body.setdefault("written_at", _utc())
    return body


def write_session(store: MemoryStore, session: dict[str, Any]) -> MemoryEntry:
    """Session layer: one conversation. Transient UI does not belong here."""
    if session.get("live_verified") is True:
        session = dict(session)
    body = _force_not_live(session)
    session_id = str(body.get("session_id") or "session")
    entry = MemoryEntry(
        key=f"session:{session_id}",
        layer=MemoryLayer.SESSION,
        entry_type=MemoryEntryType.GOAL_STATE,
        value=body,
        agent_id=str(body.get("agent_id") or ""),
        task_id=str(body.get("task_id") or ""),
    )
    store.put(entry)
    return entry


def write_task(store: MemoryStore, task: dict[str, Any]) -> MemoryEntry:
    """Task layer: one root goal and its steps."""
    body = _force_not_live(task)
    task_id = str(body.get("task_id") or "task")
    entry = MemoryEntry(
        key=f"task:{task_id}",
        layer=MemoryLayer.TASK,
        entry_type=MemoryEntryType.GOAL_STATE,
        value=body,
        agent_id=str(body.get("agent_id") or ""),
        task_id=task_id,
    )
    store.put(entry)
    return entry


def write_organizational(store: MemoryStore, pattern: dict[str, Any]) -> MemoryEntry:
    """Organizational layer: evidenced patterns only. No speculation."""
    evidence = pattern.get("evidence") or []
    if not isinstance(evidence, list) or not evidence:
        raise MemoryLayerError("missing_evidence", "organizational writes require evidence")
    if pattern.get("live_verified") is True:
        raise MemoryLayerError("live_claim", "organizational memory may not claim live verification")
    body = _force_not_live(pattern)
    pattern_id = str(body.get("pattern_id") or "pattern")
    entry = MemoryEntry(
        key=f"org:pattern:{pattern_id}",
        layer=MemoryLayer.ORGANIZATIONAL,
        entry_type=MemoryEntryType.PATTERN,
        value=body,
        metadata={"evidence": evidence},
    )
    store.put(entry)
    return entry


def write_verified(store: MemoryStore, fact: dict[str, Any]) -> MemoryEntry:
    """Verified knowledge: confirmed facts with a how. Confidence may decay later."""
    if fact.get("live_verified") is True:
        raise MemoryLayerError("live_claim", "verified knowledge may not claim LIVE VERIFIED")
    if not str(fact.get("how") or "").strip():
        raise MemoryLayerError("missing_how", "verified facts require a how")
    if not str(fact.get("fact") or "").strip():
        raise MemoryLayerError("missing_fact", "verified writes require a fact")
    body = _force_not_live(fact)
    fact_id = str(body.get("id") or "fact")
    confidence = float(body.get("confidence") or 1.0)
    entry = MemoryEntry(
        key=f"verified:{fact_id}",
        layer=MemoryLayer.VERIFIED_KNOWLEDGE,
        entry_type=MemoryEntryType.FACT,
        value=body,
        confidence=confidence,
    )
    store.put(entry)
    return entry


def ingest_markdown(
    root: Path,
    store: MemoryStore,
    *,
    session_id: str,
    task_id: str,
    agent_id: str,
) -> dict[str, Any]:
    """Catalog markdown and write one row to each layer. Not a live proof."""
    catalog = catalog_markdown(root)
    write_session(
        store,
        {
            "session_id": session_id,
            "task_id": task_id,
            "agent_id": agent_id,
            "goal": "ingest markdown into four memory layers",
            "markdown_files": len(catalog),
        },
    )
    write_task(
        store,
        {
            "task_id": task_id,
            "agent_id": agent_id,
            "status": "running",
            "steps": {"catalog": True, "write_layers": True},
            "markdown_files": len(catalog),
        },
    )
    write_organizational(
        store,
        {
            "pattern_id": "memory-four-layers",
            "description": "Memory is Session, Task, Organizational, Verified Knowledge.",
            "evidence": ["docs/architecture-v1.md", "AGENTS.md"],
        },
    )
    write_verified(
        store,
        {
            "id": "md-catalog",
            "fact": f"{len(catalog)} markdown files under {root}.",
            "how": "catalog_markdown walk",
            "confidence": 1.0,
            "paths": [row["path"] for row in catalog],
        },
    )
    return {
        "session_id": session_id,
        "task_id": task_id,
        "markdown_files": len(catalog),
        "markdown_bytes": sum(int(row["bytes"]) for row in catalog),
        "catalog": catalog,
        "live_verified": False,
    }
