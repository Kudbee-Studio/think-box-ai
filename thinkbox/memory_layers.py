"""Four memory layers — Session, Task, Organizational, Verified Knowledge.

Markdown ingest is a catalog plus fail-closed writes. Reads, query, and
retention sit on the same store. Organizational rows are append-only.
Verified confidence decays. Nothing here may claim LIVE VERIFIED.
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
    """Organizational layer: evidenced, versioned, append-only history."""
    evidence = pattern.get("evidence") or []
    if not isinstance(evidence, list) or not evidence:
        raise MemoryLayerError("missing_evidence", "organizational writes require evidence")
    if pattern.get("live_verified") is True:
        raise MemoryLayerError("live_claim", "organizational memory may not claim live verification")
    body = _force_not_live(pattern)
    pattern_id = str(body.get("pattern_id") or "pattern")
    key = f"org:pattern:{pattern_id}"
    existing = store.get(key)
    if existing is not None:
        same_desc = existing.value.get("description") == body.get("description")
        same_ev = list(existing.value.get("evidence") or []) == list(evidence)
        if same_desc and same_ev:
            return existing
        version = int(existing.value.get("version") or 1)
        archive_key = f"{key}:v{version}"
        store.put(
            MemoryEntry(
                key=archive_key,
                layer=MemoryLayer.ORGANIZATIONAL,
                entry_type=MemoryEntryType.PATTERN,
                value={**dict(existing.value), "version": version, "superseded_at": _utc()},
                metadata=existing.metadata,
            )
        )
        body["version"] = version + 1
        body["supersedes"] = archive_key
    else:
        body["version"] = 1
    entry = MemoryEntry(
        key=key,
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


def _parse_utc(stamp: str) -> datetime:
    moment = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    if moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)
    return moment


def _require(store: MemoryStore, key: str, code: str) -> MemoryEntry:
    entry = store.get(key)
    if entry is None:
        raise MemoryLayerError(code, f"missing memory key {key}")
    return entry


def read_session(store: MemoryStore, session_id: str) -> MemoryEntry:
    """Read one session row. Fail-closed if it is gone."""
    return _require(store, f"session:{session_id}", "missing_session")


def read_task(store: MemoryStore, task_id: str) -> MemoryEntry:
    """Read one task goal-state row."""
    return _require(store, f"task:{task_id}", "missing_task")


def read_organizational(store: MemoryStore, pattern_id: str) -> MemoryEntry:
    """Read one evidenced organizational pattern."""
    return _require(store, f"org:pattern:{pattern_id}", "missing_org")


def effective_confidence(
    entry: MemoryEntry,
    *,
    now: datetime | None = None,
    half_life_hours: float = 168.0,
) -> float:
    """Decay stored confidence by age. Half-life default is one week."""
    if half_life_hours <= 0:
        raise MemoryLayerError("invalid_half_life", "half_life_hours must be > 0")
    moment = now or datetime.now(timezone.utc)
    age_hours = max(0.0, (moment - _parse_utc(entry.created_at)).total_seconds() / 3600.0)
    decayed = float(entry.confidence) * (0.5 ** (age_hours / half_life_hours))
    return max(0.0, min(1.0, decayed))


def read_verified(
    store: MemoryStore,
    fact_id: str,
    *,
    now: datetime | None = None,
    half_life_hours: float = 168.0,
) -> dict[str, Any]:
    """Read a verified fact with stored and decayed confidence. Never live."""
    entry = _require(store, f"verified:{fact_id}", "missing_verified")
    return {
        "entry": entry,
        "fact": entry.value.get("fact"),
        "how": entry.value.get("how"),
        "stored_confidence": float(entry.confidence),
        "effective_confidence": effective_confidence(
            entry, now=now, half_life_hours=half_life_hours
        ),
        "live_verified": False,
    }


def query_layer(
    store: MemoryStore,
    layer: MemoryLayer,
    *,
    prefix: str | None = None,
    limit: int = 100,
) -> list[MemoryEntry]:
    """List rows in one layer. Optional key prefix."""
    rows = store.query(layer=layer, limit=limit)
    if prefix:
        rows = [row for row in rows if row.key.startswith(prefix)]
    return rows


def end_session(store: MemoryStore, session_id: str) -> dict[str, Any]:
    """Session lifetime ends. Org and verified rows stay."""
    key = f"session:{session_id}"
    deleted = store.delete(key)
    if not deleted:
        raise MemoryLayerError("missing_session", f"session {session_id} not found")
    return {"deleted": [key], "live_verified": False}


def end_task(store: MemoryStore, task_id: str) -> dict[str, Any]:
    """Task lifetime ends. Delete the goal row and its steps/errors."""
    prefix = f"task:{task_id}"
    deleted: list[str] = []
    for key in list(store.keys(MemoryLayer.TASK)):
        if key == prefix or key.startswith(prefix + ":"):
            if store.delete(key):
                deleted.append(key)
    if not deleted:
        raise MemoryLayerError("missing_task", f"task {task_id} not found")
    return {"deleted": deleted, "live_verified": False}


def delete_organizational(store: MemoryStore, pattern_id: str) -> None:
    """Organizational memory is append-only."""
    raise MemoryLayerError(
        "append_only", f"organizational pattern {pattern_id} cannot be deleted"
    )


def delete_verified(store: MemoryStore, fact_id: str) -> None:
    """Verified knowledge decays; it is not deleted."""
    raise MemoryLayerError("no_delete", f"verified fact {fact_id} cannot be deleted")


def apply_retention(
    store: MemoryStore,
    *,
    now: datetime | None = None,
    session_max_age_hours: float = 24.0,
) -> dict[str, Any]:
    """Expire stale sessions and ended tasks. Never drop org or verified."""
    if session_max_age_hours < 0:
        raise MemoryLayerError("invalid_retention", "session_max_age_hours must be >= 0")
    moment = now or datetime.now(timezone.utc)
    expired_sessions: list[str] = []
    for key in list(store.keys(MemoryLayer.SESSION)):
        entry = store.get(key)
        if entry is None:
            continue
        age_hours = (moment - _parse_utc(entry.created_at)).total_seconds() / 3600.0
        if age_hours > session_max_age_hours:
            store.delete(key)
            expired_sessions.append(key)
    expired_tasks: list[str] = []
    for entry in list(store.query(layer=MemoryLayer.TASK, limit=500)):
        if entry.key.count(":") != 1:
            continue
        status = str(entry.value.get("status") or "")
        if status in {"ended", "completed", "failed"}:
            task_id = str(entry.value.get("task_id") or entry.key.split(":", 1)[1])
            result = end_task(store, task_id)
            expired_tasks.extend(result["deleted"])
    return {
        "expired_sessions": expired_sessions,
        "expired_tasks": expired_tasks,
        "organizational": store.count(MemoryLayer.ORGANIZATIONAL),
        "verified_knowledge": store.count(MemoryLayer.VERIFIED_KNOWLEDGE),
        "live_verified": False,
    }


def org_history(store: MemoryStore, pattern_id: str) -> list[MemoryEntry]:
    """Version chain for one organizational pattern. Oldest first, current last."""
    key = f"org:pattern:{pattern_id}"
    rows = query_layer(store, MemoryLayer.ORGANIZATIONAL, prefix=key)
    versions = [row for row in rows if row.key.startswith(f"{key}:v")]
    versions.sort(key=lambda row: int(row.value.get("version") or 0))
    current = store.get(key)
    if current is not None:
        versions.append(current)
    if not versions:
        raise MemoryLayerError("missing_org", f"organizational pattern {pattern_id} not found")
    return versions


def _entry_payload(entry: MemoryEntry) -> dict[str, Any]:
    return {
        "key": entry.key,
        "layer": entry.layer.value,
        "entry_type": entry.entry_type.value,
        "value": dict(entry.value),
        "agent_id": entry.agent_id,
        "task_id": entry.task_id,
        "created_at": entry.created_at,
        "confidence": entry.confidence,
        "metadata": dict(entry.metadata),
    }


def export_snapshot(store: MemoryStore) -> dict[str, Any]:
    """Portable four-layer snapshot. Never a live proof."""
    layers: dict[str, list[dict[str, Any]]] = {}
    for layer in MemoryLayer:
        layers[layer.value] = [_entry_payload(row) for row in store.query(layer=layer, limit=1000)]
    return {
        "layers": layers,
        "exported_at": _utc(),
        "live_verified": False,
    }


def import_snapshot(store: MemoryStore, snapshot: dict[str, Any]) -> dict[str, Any]:
    """Replay a snapshot through write policy. Rejects live claims."""
    if snapshot.get("live_verified") is True:
        raise MemoryLayerError("live_claim", "snapshot may not claim LIVE VERIFIED")
    layers = snapshot.get("layers")
    if not isinstance(layers, dict):
        raise MemoryLayerError("invalid_snapshot", "snapshot requires a layers object")
    imported = 0
    for layer_name, rows in layers.items():
        if not isinstance(rows, list):
            raise MemoryLayerError("invalid_snapshot", f"layer {layer_name} must be a list")
        for row in rows:
            value = dict((row or {}).get("value") or {})
            key = str((row or {}).get("key") or "")
            if layer_name == MemoryLayer.SESSION.value:
                write_session(store, value)
            elif layer_name == MemoryLayer.TASK.value:
                if key.count(":") == 1:
                    write_task(store, value)
                elif ":step:" in key:
                    record_task_step(
                        store,
                        str(value.get("task_id") or key.split(":")[1]),
                        str(value.get("step_id") or "step"),
                        dict(value.get("result") or {}),
                        agent_id=str(value.get("agent_id") or ""),
                    )
                elif ":error:" in key:
                    record_task_error(
                        store,
                        str(value.get("task_id") or key.split(":")[1]),
                        str(value.get("error") or "error"),
                        dict(value.get("context") or {}),
                    )
            elif layer_name == MemoryLayer.ORGANIZATIONAL.value:
                if key.startswith("org:pattern:") and ":v" in key[len("org:pattern:"):]:
                    evidence = value.get("evidence") or []
                    if not isinstance(evidence, list) or not evidence:
                        raise MemoryLayerError("missing_evidence", "organizational writes require evidence")
                    if value.get("live_verified") is True:
                        raise MemoryLayerError("live_claim", "organizational memory may not claim live verification")
                    store.put(
                        MemoryEntry(
                            key=key,
                            layer=MemoryLayer.ORGANIZATIONAL,
                            entry_type=MemoryEntryType.PATTERN,
                            value=_force_not_live(value),
                            metadata={"evidence": evidence},
                        )
                    )
                else:
                    write_organizational(store, value)
            elif layer_name == MemoryLayer.VERIFIED_KNOWLEDGE.value:
                write_verified(store, value)
            imported += 1
    snap = snapshot_layers(store)
    snap["imported"] = imported
    return snap
