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
TRANSIENT_KEYS = frozenset({"ui", "scroll", "localStorage", "cursor", "selection", "viewport"})

CHRONICLE_PATTERNS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "memory-four-layers",
        "Memory is Session, Task, Organizational, Verified Knowledge. Not chat history.",
        ("docs/architecture-v1.md", "AGENTS.md"),
    ),
    (
        "governance-default",
        "A tool without an explicit permission level is RESTRICTED. Side effects need admission.",
        ("AGENTS.md",),
    ),
    (
        "four-state-honesty",
        "Hermetic work caps at CODE COMPLETE / TEST VERIFIED. Do not claim LIVE VERIFIED without founder-run artifacts.",
        ("AGENTS.md", "docs/CONTINUITY.md"),
    ),
    (
        "pr-before-work",
        "Meaningful changes go through a GitHub PR. No direct product pushes to main.",
        ("AGENTS.md",),
    ),
    (
        "trait-lab-engine-is-truth",
        "Trait Lab Python engine is source of truth. Browser ports LCG 1664525. live_verified stays false.",
        ("thinkbox/trait_game/engine.py", "public/nfts/trait_game.js"),
    ),
)


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


def chronicle_patterns(root: Path) -> list[dict[str, Any]]:
    """Organizational patterns whose evidence files exist on disk."""
    rows: list[dict[str, Any]] = []
    for pattern_id, description, evidence in CHRONICLE_PATTERNS:
        present = [path for path in evidence if (root / path).is_file()]
        if len(present) != len(evidence):
            continue
        rows.append(
            {
                "pattern_id": pattern_id,
                "description": description,
                "evidence": list(present),
            }
        )
    return rows


def snapshot_layers(store: MemoryStore) -> dict[str, Any]:
    """Counts and keys per layer. Never a live proof."""
    return {
        "session": store.count(MemoryLayer.SESSION),
        "task": store.count(MemoryLayer.TASK),
        "organizational": store.count(MemoryLayer.ORGANIZATIONAL),
        "verified_knowledge": store.count(MemoryLayer.VERIFIED_KNOWLEDGE),
        "keys": {
            "session": store.keys(MemoryLayer.SESSION),
            "task": store.keys(MemoryLayer.TASK),
            "organizational": store.keys(MemoryLayer.ORGANIZATIONAL),
            "verified_knowledge": store.keys(MemoryLayer.VERIFIED_KNOWLEDGE),
        },
        "live_verified": False,
    }


def write_session(store: MemoryStore, session: dict[str, Any]) -> MemoryEntry:
    """Session layer: one conversation. Transient UI does not belong here."""
    hit = sorted(TRANSIENT_KEYS.intersection(session))
    if hit:
        raise MemoryLayerError("transient_ui", f"session memory rejects transient keys: {', '.join(hit)}")
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
    try:
        confidence = float(fact.get("confidence") if fact.get("confidence") is not None else 1.0)
    except (TypeError, ValueError) as exc:
        raise MemoryLayerError("invalid_confidence", "confidence must be a number") from exc
    if not 0.0 <= confidence <= 1.0:
        raise MemoryLayerError("invalid_confidence", "confidence must be between 0 and 1")
    body = _force_not_live(fact)
    fact_id = str(body.get("id") or "fact")
    key = f"verified:{fact_id}"
    existing = store.get(key)
    if existing is not None and existing.value.get("fact") != body.get("fact") and not body.get("corrects"):
        raise MemoryLayerError("contradiction", f"verified fact {fact_id} already exists with a different value")
    entry = MemoryEntry(
        key=key,
        layer=MemoryLayer.VERIFIED_KNOWLEDGE,
        entry_type=MemoryEntryType.FACT,
        value=body,
        confidence=confidence,
    )
    store.put(entry)
    return entry


def record_task_step(
    store: MemoryStore,
    task_id: str,
    step_id: str,
    result: dict[str, Any],
    *,
    agent_id: str = "",
) -> MemoryEntry:
    """Persist one task step. Fail-closed if the run is already marked live."""
    body = _force_not_live({"step_id": step_id, "result": result})
    entry = MemoryEntry(
        key=f"task:{task_id}:step:{step_id}",
        layer=MemoryLayer.TASK,
        entry_type=MemoryEntryType.REASONING_STEP,
        value=body,
        agent_id=agent_id,
        task_id=task_id,
    )
    store.put(entry)
    return entry


def record_task_error(
    store: MemoryStore,
    task_id: str,
    error: str,
    context: dict[str, Any] | None = None,
    *,
    agent_id: str = "",
) -> MemoryEntry:
    """Persist a task error with context. Not swallowed."""
    body = _force_not_live({"error": error, "context": context or {}})
    entry = MemoryEntry(
        key=f"task:{task_id}:error:{step_stamp(error)}",
        layer=MemoryLayer.TASK,
        entry_type=MemoryEntryType.ERROR,
        value=body,
        agent_id=agent_id,
        task_id=task_id,
    )
    store.put(entry)
    return entry


def step_stamp(error: str) -> str:
    """Stable short id for an error row."""
    cleaned = "".join(ch if ch.isalnum() else "-" for ch in error.lower())[:24].strip("-")
    return cleaned or "error"


def ingest_markdown(
    root: Path,
    store: MemoryStore,
    *,
    session_id: str,
    task_id: str,
    agent_id: str,
) -> dict[str, Any]:
    """Catalog markdown and write each layer. Chronicle patterns only when evidence files exist."""
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
    patterns = chronicle_patterns(root)
    for pattern in patterns:
        write_organizational(store, pattern)
    if not patterns:
        write_organizational(
            store,
            {
                "pattern_id": "md-ingest-catalog",
                "description": "Markdown catalog is an evidenced inventory, not a live claim.",
                "evidence": [row["path"] for row in catalog] or ["catalog_markdown:empty"],
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
    record_task_step(
        store,
        task_id,
        "ingest",
        {"markdown_files": len(catalog), "patterns": len(patterns)},
        agent_id=agent_id,
    )
    snap = snapshot_layers(store)
    return {
        "session_id": session_id,
        "task_id": task_id,
        "markdown_files": len(catalog),
        "markdown_bytes": sum(int(row["bytes"]) for row in catalog),
        "catalog": catalog,
        "patterns": [item["pattern_id"] for item in patterns],
        "snapshot": snap,
        "live_verified": False,
    }
