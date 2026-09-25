"""Four memory layers — Session, Task, Organizational, Verified Knowledge.

Markdown ingest is a catalog plus fail-closed writes. Reads, query, and
retention sit on the same store. Organizational rows are append-only.
Verified confidence decays. Nothing here may claim LIVE VERIFIED.
"""

from __future__ import annotations

import hashlib
import json
import re
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
        agent_id=str(body.get("agent_id") or ""),
        task_id=str(body.get("task_id") or ""),
        metadata={"evidence": evidence, "source": str(body.get("source") or "")},
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
        agent_id=str(body.get("agent_id") or ""),
        task_id=str(body.get("task_id") or ""),
        confidence=confidence,
        metadata={"source": str(body.get("source") or "")},
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


def query_by_provenance(
    store: MemoryStore,
    *,
    agent_id: str | None = None,
    task_id: str | None = None,
    source: str | None = None,
    limit: int = 100,
) -> list[MemoryEntry]:
    """Find rows by agent, task, or observation source."""
    rows: list[MemoryEntry] = []
    for layer in MemoryLayer:
        for entry in store.query(layer=layer, agent_id=agent_id, task_id=task_id, limit=limit):
            if source and str(entry.value.get("source") or entry.metadata.get("source") or "") != source:
                continue
            rows.append(entry)
    return rows


def record_trait_lab_run(
    store: MemoryStore,
    proof: dict[str, Any],
    *,
    agent_id: str,
    task_id: str,
    session_id: str | None = None,
) -> dict[str, Any]:
    """Bind a Trait Lab proof into all four layers. Never a live claim."""
    if proof.get("live_verified") is True:
        raise MemoryLayerError("live_claim", "trait lab ledger may not claim LIVE VERIFIED")
    if not str(agent_id or "").strip() or not str(task_id or "").strip():
        raise MemoryLayerError("missing_provenance", "trait lab ledger requires agent_id and task_id")
    sha = str(proof.get("proof_sha256") or "").strip().lower()
    if len(sha) != 64 or any(ch not in "0123456789abcdef" for ch in sha):
        raise MemoryLayerError("missing_proof", "trait lab run requires proof_sha256")
    if str(proof.get("game_id") or "") != "trait-lab":
        raise MemoryLayerError("wrong_game", "ledger only accepts game_id trait-lab")
    sid = session_id or f"trait-lab-{proof.get('seed')}-{sha[:8]}"
    write_session(
        store,
        {
            "session_id": sid,
            "task_id": task_id,
            "agent_id": agent_id,
            "source": sha,
            "goal": "record trait lab run",
            "seed": proof.get("seed"),
        },
    )
    write_task(
        store,
        {
            "task_id": task_id,
            "agent_id": agent_id,
            "source": sha,
            "status": "completed",
            "game_id": "trait-lab",
            "seed": proof.get("seed"),
            "xp": proof.get("xp"),
            "grade": proof.get("grade") or "",
        },
    )
    write_organizational(
        store,
        {
            "pattern_id": f"trait-lab-seed-{proof.get('seed')}",
            "description": f"Trait Lab seed {proof.get('seed')} hashed {sha[:12]}",
            "evidence": [sha, "thinkbox/trait_game/engine.py"],
            "source": sha,
            "agent_id": agent_id,
            "task_id": task_id,
        },
    )
    write_verified(
        store,
        {
            "id": f"trait-lab-{sha[:16]}",
            "fact": (
                f"seed {proof.get('seed')} xp={proof.get('xp')} "
                f"grade={proof.get('grade') or '-'} "
                f"difficulty={proof.get('difficulty') or '-'} "
                f"operator={proof.get('operator') or '-'} "
                f"daily={'1' if proof.get('daily') else '0'}"
            ),
            "how": f"proof_scorecard {sha}",
            "confidence": 1.0,
            "source": sha,
            "agent_id": agent_id,
            "task_id": task_id,
            "seed": proof.get("seed"),
            "difficulty": proof.get("difficulty") or "",
            "operator": proof.get("operator") or "",
            "daily": bool(proof.get("daily")),
        },
    )
    record_task_step(
        store,
        task_id,
        "proof",
        {"proof_sha256": sha, "xp": proof.get("xp")},
        agent_id=agent_id,
    )
    return {
        "session_id": sid,
        "task_id": task_id,
        "proof_sha256": sha,
        "snapshot": snapshot_layers(store),
        "live_verified": False,
    }


def record_trait_lab_replay(
    store: MemoryStore,
    state: dict[str, Any],
    *,
    agent_id: str,
    task_id: str,
    session_id: str | None = None,
) -> dict[str, Any]:
    """Store a Trait Lab replay beside its proof. Never a live claim."""
    from thinkbox.trait_game.engine import encode_replay, proof_scorecard

    if state.get("live_verified") is True:
        raise MemoryLayerError("live_claim", "trait lab replay may not claim LIVE VERIFIED")
    proof = proof_scorecard(state)
    result = record_trait_lab_run(
        store,
        proof,
        agent_id=agent_id,
        task_id=task_id,
        session_id=session_id,
    )
    sha = str(result["proof_sha256"])
    replay = encode_replay(state)
    write_verified(
        store,
        {
            "id": f"trait-lab-replay-{sha[:16]}",
            "fact": replay,
            "how": f"encode_replay {sha}",
            "confidence": 1.0,
            "source": sha,
            "agent_id": agent_id,
            "task_id": task_id,
            "kind": "replay",
        },
    )
    record_task_step(
        store,
        task_id,
        "replay",
        {"replay": replay, "proof_sha256": sha},
        agent_id=agent_id,
    )
    result["replay"] = replay
    result["snapshot"] = snapshot_layers(store)
    return result


def verify_trait_lab_replay(
    store: MemoryStore,
    proof_sha256: str,
    rules: dict[str, Any],
) -> dict[str, Any]:
    """Replay a stored code and require the proof hash to match."""
    from thinkbox.trait_game.engine import TraitGameError, play_replay, proof_scorecard

    sha = str(proof_sha256 or "").strip().lower()
    if len(sha) != 64:
        raise MemoryLayerError("missing_proof", "verify requires proof_sha256")
    viewed = read_verified(store, f"trait-lab-replay-{sha[:16]}")
    replay = str(viewed.get("fact") or "").strip()
    if not replay:
        raise MemoryLayerError("missing_replay", "no replay stored for this proof")
    try:
        state = play_replay(rules, replay)
    except TraitGameError as exc:
        raise MemoryLayerError("replay_rejected", str(exc)) from exc
    card = proof_scorecard(state)
    if card.get("live_verified") is True:
        raise MemoryLayerError("live_claim", "replay proof may not claim LIVE VERIFIED")
    got = str(card.get("proof_sha256") or "").lower()
    if got != sha:
        raise MemoryLayerError("proof_mismatch", f"replay hashed {got[:12]} not {sha[:12]}")
    return {
        "matched": True,
        "proof_sha256": sha,
        "replay": replay,
        "xp": card.get("xp"),
        "grade": card.get("grade") or "",
        "live_verified": False,
    }


_XP_IN_FACT = re.compile(r"xp=(-?\d+)")
_GRADE_IN_FACT = re.compile(r"grade=([A-Za-z+\-]+)")
_DIFFICULTY_IN_FACT = re.compile(r"difficulty=([A-Za-z]+)")
_OPERATOR_IN_FACT = re.compile(r"operator=([A-Za-z0-9._-]+)")
_OPERATOR_OK = re.compile(r"^[A-Za-z0-9._-]{1,24}$")
_DAILY_IN_FACT = re.compile(r"daily=([01])")
_PACK_COUNT_IN_FACT = re.compile(r"count=(-?\d+)")


def _trait_lab_run_from_entry(entry: MemoryEntry) -> dict[str, Any]:
    fact = str(entry.value.get("fact") or "")
    xp_match = _XP_IN_FACT.search(fact)
    grade_match = _GRADE_IN_FACT.search(fact)
    difficulty = str(entry.value.get("difficulty") or "")
    if not difficulty:
        difficulty_match = _DIFFICULTY_IN_FACT.search(fact)
        difficulty = difficulty_match.group(1) if difficulty_match else ""
    operator = str(entry.value.get("operator") or "")
    if not operator:
        operator_match = _OPERATOR_IN_FACT.search(fact)
        parsed = operator_match.group(1) if operator_match else ""
        operator = "" if parsed == "-" else parsed
    if "daily" in entry.value:
        daily = bool(entry.value.get("daily"))
    else:
        daily_match = _DAILY_IN_FACT.search(fact)
        daily = bool(daily_match and daily_match.group(1) == "1")
    return {
        "proof_sha256": str(entry.value.get("source") or entry.metadata.get("source") or ""),
        "seed": entry.value.get("seed"),
        "fact": fact,
        "xp": int(xp_match.group(1)) if xp_match else None,
        "grade": grade_match.group(1) if grade_match else "",
        "difficulty": difficulty,
        "operator": operator,
        "daily": daily,
        "agent_id": entry.agent_id,
        "task_id": entry.task_id,
        "live_verified": False,
    }


def list_trait_lab_runs(store: MemoryStore, *, limit: int = 50) -> list[dict[str, Any]]:
    """Index stored Trait Lab proofs. Skips replay rows."""
    if limit < 1:
        raise MemoryLayerError("invalid_limit", "limit must be >= 1")
    runs: list[dict[str, Any]] = []
    for entry in query_layer(store, MemoryLayer.VERIFIED_KNOWLEDGE, prefix="verified:trait-lab-", limit=limit * 2):
        if entry.key.startswith("verified:trait-lab-replay-"):
            continue
        if entry.key.startswith("verified:trait-lab-pack-"):
            continue
        if not entry.key.startswith("verified:trait-lab-"):
            continue
        runs.append(_trait_lab_run_from_entry(entry))
        if len(runs) >= limit:
            break
    return runs


def compare_trait_lab_runs(
    store: MemoryStore,
    proof_a: str,
    proof_b: str,
) -> dict[str, Any]:
    """Compare two stored Trait Lab proofs. Not a live ranking."""
    sha_a = str(proof_a or "").strip().lower()
    sha_b = str(proof_b or "").strip().lower()
    if len(sha_a) != 64 or len(sha_b) != 64:
        raise MemoryLayerError("missing_proof", "compare requires two proof_sha256 values")
    if sha_a == sha_b:
        raise MemoryLayerError("same_run", "compare requires two different proofs")
    left = _trait_lab_run_from_entry(read_verified(store, f"trait-lab-{sha_a[:16]}")["entry"])
    right = _trait_lab_run_from_entry(read_verified(store, f"trait-lab-{sha_b[:16]}")["entry"])
    xp_a = int(left["xp"] or 0)
    xp_b = int(right["xp"] or 0)
    return {
        "a": left,
        "b": right,
        "xp_delta": xp_a - xp_b,
        "same_seed": left.get("seed") == right.get("seed"),
        "live_verified": False,
    }


def board_trait_lab_runs(store: MemoryStore, *, limit: int = 10) -> dict[str, Any]:
    """Local board from stored proofs. Uses rank_board. Not live."""
    if limit < 1:
        raise MemoryLayerError("invalid_limit", "limit must be >= 1")
    from thinkbox.trait_game.engine import rank_board

    runs = list_trait_lab_runs(store, limit=max(limit, 50))
    entries = [
        {
            "xp": int(run.get("xp") or 0),
            "grade": str(run.get("grade") or ""),
            "turn": 0,
            "name": str(run.get("proof_sha256") or "")[:8],
            "seed": run.get("seed"),
            "proof_sha256": run.get("proof_sha256"),
        }
        for run in runs
    ]
    return {
        "board": rank_board(entries, limit=limit),
        "count": len(runs),
        "live_verified": False,
    }


def _seed_key(seed: Any) -> int:
    try:
        return int(seed)
    except (TypeError, ValueError) as exc:
        raise MemoryLayerError("invalid_seed", "seed must be an integer") from exc


def best_trait_lab_by_seed(store: MemoryStore, *, limit: int = 200) -> dict[str, Any]:
    """Highest stored XP per seed. Local only. Not a live ranking."""
    if limit < 1:
        raise MemoryLayerError("invalid_limit", "limit must be >= 1")
    best: dict[int, dict[str, Any]] = {}
    for run in list_trait_lab_runs(store, limit=limit):
        if run.get("seed") is None:
            continue
        key = _seed_key(run["seed"])
        current = best.get(key)
        if current is None or int(run.get("xp") or 0) > int(current.get("xp") or 0):
            best[key] = run
    return {
        "by_seed": best,
        "seeds": len(best),
        "live_verified": False,
    }


def best_trait_lab_seed(store: MemoryStore, seed: int) -> dict[str, Any]:
    """Best stored run for one seed. Fail-closed if none."""
    key = _seed_key(seed)
    bundle = best_trait_lab_by_seed(store)
    run = bundle["by_seed"].get(key)
    if run is None:
        raise MemoryLayerError("missing_seed", f"no stored Trait Lab run for seed {key}")
    return {**run, "live_verified": False}


def trait_lab_seed_history(
    store: MemoryStore,
    seed: int,
    *,
    limit: int = 50,
) -> dict[str, Any]:
    """All stored runs for one seed, highest XP first. Not a live ranking."""
    if limit < 1:
        raise MemoryLayerError("invalid_limit", "limit must be >= 1")
    key = _seed_key(seed)
    runs = [
        run
        for run in list_trait_lab_runs(store, limit=200)
        if run.get("seed") is not None and _seed_key(run["seed"]) == key
    ]
    runs.sort(key=lambda row: int(row.get("xp") or 0), reverse=True)
    if not runs:
        raise MemoryLayerError("missing_seed", f"no stored Trait Lab run for seed {key}")
    return {
        "seed": key,
        "runs": runs[:limit],
        "count": len(runs),
        "best": runs[0],
        "live_verified": False,
    }


def trait_lab_seed_index(store: MemoryStore, *, limit: int = 50) -> dict[str, Any]:
    """Seeds that have stored runs: count + best XP. Not a live ranking."""
    if limit < 1:
        raise MemoryLayerError("invalid_limit", "limit must be >= 1")
    grouped: dict[int, list[dict[str, Any]]] = {}
    for run in list_trait_lab_runs(store, limit=200):
        if run.get("seed") is None:
            continue
        key = _seed_key(run["seed"])
        grouped.setdefault(key, []).append(run)
    rows: list[dict[str, Any]] = []
    for seed, runs in grouped.items():
        runs.sort(key=lambda row: int(row.get("xp") or 0), reverse=True)
        rows.append(
            {
                "seed": seed,
                "count": len(runs),
                "best_xp": int(runs[0].get("xp") or 0),
                "best": runs[0],
            }
        )
    rows.sort(key=lambda row: (-int(row["best_xp"]), int(row["seed"])))
    return {
        "seeds": rows[:limit],
        "count": len(rows),
        "live_verified": False,
    }


_TRAIT_LAB_GRADES = frozenset({"S", "A", "B", "C", "D"})


def trait_lab_seed_history_by_grade(
    store: MemoryStore,
    seed: int,
    grade: str,
    *,
    limit: int = 50,
) -> dict[str, Any]:
    """Seed history rows filtered by letter grade. Not a live ranking."""
    if limit < 1:
        raise MemoryLayerError("invalid_limit", "limit must be >= 1")
    wanted = str(grade or "").strip().upper()
    if wanted not in _TRAIT_LAB_GRADES:
        raise MemoryLayerError("invalid_grade", "grade must be S, A, B, C, or D")
    history = trait_lab_seed_history(store, seed, limit=200)
    runs = [
        row
        for row in history["runs"]
        if str(row.get("grade") or "").upper() == wanted
    ]
    if not runs:
        raise MemoryLayerError(
            "missing_grade",
            f"no stored Trait Lab run for seed {history['seed']} grade {wanted}",
        )
    return {
        "seed": history["seed"],
        "grade": wanted,
        "runs": runs[:limit],
        "count": len(runs),
        "best": runs[0],
        "live_verified": False,
    }


_TRAIT_LAB_DIFFICULTIES = frozenset({"survey", "lab", "thesis"})


def trait_lab_seed_history_by_difficulty(
    store: MemoryStore,
    seed: int,
    difficulty: str,
    *,
    limit: int = 50,
) -> dict[str, Any]:
    """Seed history rows filtered by difficulty tier. Not a live ranking."""
    if limit < 1:
        raise MemoryLayerError("invalid_limit", "limit must be >= 1")
    wanted = str(difficulty or "").strip().lower()
    if wanted not in _TRAIT_LAB_DIFFICULTIES:
        raise MemoryLayerError("invalid_difficulty", "difficulty must be survey, lab, or thesis")
    history = trait_lab_seed_history(store, seed, limit=200)
    runs = [
        row
        for row in history["runs"]
        if str(row.get("difficulty") or "").lower() == wanted
    ]
    if not runs:
        raise MemoryLayerError(
            "missing_difficulty",
            f"no stored Trait Lab run for seed {history['seed']} difficulty {wanted}",
        )
    return {
        "seed": history["seed"],
        "difficulty": wanted,
        "runs": runs[:limit],
        "count": len(runs),
        "best": runs[0],
        "live_verified": False,
    }


def trait_lab_seed_history_by_operator(
    store: MemoryStore,
    seed: int,
    operator: str,
    *,
    limit: int = 50,
) -> dict[str, Any]:
    """Seed history rows filtered by operator name. Not a live ranking."""
    if limit < 1:
        raise MemoryLayerError("invalid_limit", "limit must be >= 1")
    wanted = str(operator or "").strip()
    if not _OPERATOR_OK.fullmatch(wanted):
        raise MemoryLayerError(
            "invalid_operator",
            "operator must be 1-24 ASCII letters, digits, '.', '_', or '-'",
        )
    history = trait_lab_seed_history(store, seed, limit=200)
    runs = [row for row in history["runs"] if str(row.get("operator") or "") == wanted]
    if not runs:
        raise MemoryLayerError(
            "missing_operator",
            f"no stored Trait Lab run for seed {history['seed']} operator {wanted}",
        )
    return {
        "seed": history["seed"],
        "operator": wanted,
        "runs": runs[:limit],
        "count": len(runs),
        "best": runs[0],
        "live_verified": False,
    }


def trait_lab_seed_history_by_daily(
    store: MemoryStore,
    seed: int,
    daily: bool,
    *,
    limit: int = 50,
) -> dict[str, Any]:
    """Seed history rows filtered by daily-seed flag. Not a live ranking."""
    if limit < 1:
        raise MemoryLayerError("invalid_limit", "limit must be >= 1")
    if not isinstance(daily, bool):
        raise MemoryLayerError("invalid_daily", "daily must be a boolean")
    history = trait_lab_seed_history(store, seed, limit=200)
    runs = [row for row in history["runs"] if bool(row.get("daily")) is daily]
    if not runs:
        raise MemoryLayerError(
            "missing_daily",
            f"no stored Trait Lab run for seed {history['seed']} daily={daily}",
        )
    return {
        "seed": history["seed"],
        "daily": daily,
        "runs": runs[:limit],
        "count": len(runs),
        "best": runs[0],
        "live_verified": False,
    }


def trait_lab_seed_history_by_xp_floor(
    store: MemoryStore,
    seed: int,
    floor: int,
    *,
    limit: int = 50,
) -> dict[str, Any]:
    """Seed history rows at or above a stored XP threshold. Not a live ranking."""
    if limit < 1:
        raise MemoryLayerError("invalid_limit", "limit must be >= 1")
    try:
        threshold = int(floor)
    except (TypeError, ValueError) as exc:
        raise MemoryLayerError("invalid_floor", "floor must be an integer") from exc
    if isinstance(floor, bool) or threshold < 0:
        raise MemoryLayerError("invalid_floor", "floor must be an integer >= 0")
    history = trait_lab_seed_history(store, seed, limit=200)
    runs = [row for row in history["runs"] if int(row.get("xp") or 0) >= threshold]
    if not runs:
        raise MemoryLayerError(
            "missing_floor",
            f"no stored Trait Lab run for seed {history['seed']} xp>={threshold}",
        )
    return {
        "seed": history["seed"],
        "floor": threshold,
        "runs": runs[:limit],
        "count": len(runs),
        "best": runs[0],
        "live_verified": False,
    }


def trait_lab_seed_history_by_xp_ceiling(
    store: MemoryStore,
    seed: int,
    ceiling: int,
    *,
    limit: int = 50,
) -> dict[str, Any]:
    """Seed history rows at or below a stored XP threshold. Not a live ranking."""
    if limit < 1:
        raise MemoryLayerError("invalid_limit", "limit must be >= 1")
    try:
        threshold = int(ceiling)
    except (TypeError, ValueError) as exc:
        raise MemoryLayerError("invalid_ceiling", "ceiling must be an integer") from exc
    if isinstance(ceiling, bool) or threshold < 0:
        raise MemoryLayerError("invalid_ceiling", "ceiling must be an integer >= 0")
    history = trait_lab_seed_history(store, seed, limit=200)
    runs = [row for row in history["runs"] if int(row.get("xp") or 0) <= threshold]
    if not runs:
        raise MemoryLayerError(
            "missing_ceiling",
            f"no stored Trait Lab run for seed {history['seed']} xp<={threshold}",
        )
    return {
        "seed": history["seed"],
        "ceiling": threshold,
        "runs": runs[:limit],
        "count": len(runs),
        "best": runs[0],
        "live_verified": False,
    }


def _xp_bound(value: Any, *, code: str, label: str) -> int:
    try:
        threshold = int(value)
    except (TypeError, ValueError) as exc:
        raise MemoryLayerError(code, f"{label} must be an integer") from exc
    if isinstance(value, bool) or threshold < 0:
        raise MemoryLayerError(code, f"{label} must be an integer >= 0")
    return threshold


def trait_lab_seed_history_by_xp_band(
    store: MemoryStore,
    seed: int,
    floor: int,
    ceiling: int,
    *,
    limit: int = 50,
) -> dict[str, Any]:
    """Seed history rows between a stored XP floor and ceiling. Not a live ranking."""
    if limit < 1:
        raise MemoryLayerError("invalid_limit", "limit must be >= 1")
    low = _xp_bound(floor, code="invalid_floor", label="floor")
    high = _xp_bound(ceiling, code="invalid_ceiling", label="ceiling")
    if low > high:
        raise MemoryLayerError("invalid_band", "floor must be <= ceiling")
    history = trait_lab_seed_history(store, seed, limit=200)
    runs = [
        row
        for row in history["runs"]
        if low <= int(row.get("xp") or 0) <= high
    ]
    if not runs:
        raise MemoryLayerError(
            "missing_band",
            f"no stored Trait Lab run for seed {history['seed']} xp {low}-{high}",
        )
    return {
        "seed": history["seed"],
        "floor": low,
        "ceiling": high,
        "runs": runs[:limit],
        "count": len(runs),
        "best": runs[0],
        "live_verified": False,
    }


_TRAIT_LAB_SEED_PACK_KIND = "trait-lab-seed-pack"


def _trait_lab_seed_pack_body(
    *,
    seed: Any,
    count: Any,
    best: Any,
    runs: Any,
) -> dict[str, Any]:
    return {
        "kind": _TRAIT_LAB_SEED_PACK_KIND,
        "seed": seed,
        "count": count,
        "best": best,
        "runs": runs,
        "live_verified": False,
    }


def _trait_lab_seed_pack_sha256(body: dict[str, Any]) -> str:
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def export_trait_lab_seed_pack(
    store: MemoryStore,
    seed: int,
    *,
    limit: int = 50,
) -> dict[str, Any]:
    """Portable snapshot of stored runs for one seed. Not a live ranking."""
    history = trait_lab_seed_history(store, seed, limit=limit)
    body = _trait_lab_seed_pack_body(
        seed=history["seed"],
        count=history["count"],
        best=history["best"],
        runs=history["runs"],
    )
    return {
        **body,
        "pack_sha256": _trait_lab_seed_pack_sha256(body),
        "exported_at": _utc(),
    }


def verify_trait_lab_seed_pack(pack: Any) -> dict[str, Any]:
    """Rematch pack_sha256 over the stable six-key body. Refuse live claims."""
    if not isinstance(pack, dict):
        raise MemoryLayerError("invalid_pack", "seed pack must be an object")
    if pack.get("kind") != _TRAIT_LAB_SEED_PACK_KIND:
        raise MemoryLayerError("invalid_pack", "kind must be trait-lab-seed-pack")
    if pack.get("live_verified") is True:
        raise MemoryLayerError("live_claim", "seed pack may not claim LIVE VERIFIED")
    if pack.get("seed") is None or pack.get("count") is None:
        raise MemoryLayerError("invalid_pack", "seed pack missing seed or count")
    if pack.get("best") is None or pack.get("runs") is None:
        raise MemoryLayerError("invalid_pack", "seed pack missing best or runs")
    if isinstance(pack.get("seed"), bool) or not isinstance(pack.get("seed"), int):
        raise MemoryLayerError("invalid_pack", "seed must be an int")
    if isinstance(pack.get("count"), bool) or not isinstance(pack.get("count"), int):
        raise MemoryLayerError("invalid_pack", "count must be an int")
    if pack["count"] < 0:
        raise MemoryLayerError("invalid_pack", "count must be non-negative")
    if not isinstance(pack.get("runs"), list):
        raise MemoryLayerError("invalid_pack", "runs must be a list")
    sha = str(pack.get("pack_sha256") or "").strip().lower()
    if len(sha) != 64 or any(ch not in "0123456789abcdef" for ch in sha):
        raise MemoryLayerError("missing_pack_hash", "verify requires pack_sha256")
    body = _trait_lab_seed_pack_body(
        seed=pack["seed"],
        count=pack["count"],
        best=pack["best"],
        runs=pack["runs"],
    )
    got = _trait_lab_seed_pack_sha256(body)
    if got != sha:
        raise MemoryLayerError("pack_mismatch", f"pack hashed {got[:12]} not {sha[:12]}")
    return {
        "matched": True,
        "kind": body["kind"],
        "seed": body["seed"],
        "count": body["count"],
        "best": body["best"],
        "runs": body["runs"],
        "pack_sha256": sha,
        "live_verified": False,
    }


def _write_trait_lab_seed_pack_fact(
    store: MemoryStore,
    verified: dict[str, Any],
    *,
    agent_id: str,
    task_id: str,
) -> str:
    sha = str(verified["pack_sha256"])
    fact_id = f"trait-lab-pack-{sha[:16]}"
    write_verified(
        store,
        {
            "id": fact_id,
            "fact": f"seed {verified['seed']} pack={sha[:16]} count={verified['count']}",
            "how": f"verify_trait_lab_seed_pack {sha}",
            "confidence": 1.0,
            "source": sha,
            "agent_id": agent_id,
            "task_id": task_id,
            "kind": _TRAIT_LAB_SEED_PACK_KIND,
            "seed": verified["seed"],
            "count": verified["count"],
        },
    )
    return fact_id


def import_trait_lab_seed_pack(
    store: MemoryStore,
    pack: Any,
    *,
    agent_id: str,
    task_id: str,
) -> dict[str, Any]:
    """Verify a portable seed pack and write a verified fact. Local only."""
    if not str(agent_id or "").strip() or not str(task_id or "").strip():
        raise MemoryLayerError("missing_provenance", "seed pack import requires agent_id and task_id")
    verified = verify_trait_lab_seed_pack(pack)
    sha = str(verified["pack_sha256"])
    _write_trait_lab_seed_pack_fact(store, verified, agent_id=agent_id, task_id=task_id)
    record_task_step(
        store,
        task_id,
        "pack-import",
        {"pack_sha256": sha, "seed": verified["seed"], "count": verified["count"]},
        agent_id=agent_id,
    )
    return {
        **verified,
        "imported": True,
        "fact_id": f"trait-lab-pack-{sha[:16]}",
        "snapshot": snapshot_layers(store),
        "live_verified": False,
    }


def apply_trait_lab_seed_pack(
    store: MemoryStore,
    pack: Any,
    *,
    agent_id: str,
    task_id: str,
) -> dict[str, Any]:
    """Write rematched pack runs into a destination store. Local only."""
    if not str(agent_id or "").strip() or not str(task_id or "").strip():
        raise MemoryLayerError("missing_provenance", "seed pack apply requires agent_id and task_id")
    verified = verify_trait_lab_seed_pack(pack)
    pack_sha = str(verified["pack_sha256"])
    written: list[str] = []
    for index, raw in enumerate(verified["runs"]):
        if not isinstance(raw, dict):
            raise MemoryLayerError("invalid_run", f"run {index} must be an object")
        if raw.get("live_verified") is True:
            raise MemoryLayerError("live_claim", "seed pack run may not claim LIVE VERIFIED")
        sha = str(raw.get("proof_sha256") or "").strip().lower()
        if len(sha) != 64 or any(ch not in "0123456789abcdef" for ch in sha):
            raise MemoryLayerError("invalid_run", f"run {index} requires proof_sha256")
        fact = str(raw.get("fact") or "").strip()
        if not fact:
            raise MemoryLayerError("invalid_run", f"run {index} requires a fact")
        seed = raw.get("seed")
        if seed is None:
            seed = verified["seed"]
        if isinstance(seed, bool) or not isinstance(seed, int):
            raise MemoryLayerError("invalid_run", f"run {index} seed must be an int")
        if seed != verified["seed"]:
            raise MemoryLayerError("invalid_run", f"run {index} seed {seed} != pack {verified['seed']}")
        write_verified(
            store,
            {
                "id": f"trait-lab-{sha[:16]}",
                "fact": fact,
                "how": f"apply_trait_lab_seed_pack {pack_sha}",
                "confidence": 1.0,
                "source": sha,
                "agent_id": agent_id,
                "task_id": task_id,
                "seed": seed,
                "difficulty": raw.get("difficulty") or "",
                "operator": raw.get("operator") or "",
                "daily": bool(raw.get("daily")),
            },
        )
        written.append(sha)
    if not written:
        raise MemoryLayerError("missing_run", "seed pack has no runs to apply")
    _write_trait_lab_seed_pack_fact(store, verified, agent_id=agent_id, task_id=task_id)
    record_task_step(
        store,
        task_id,
        "pack-apply",
        {"pack_sha256": pack_sha, "seed": verified["seed"], "count": len(written)},
        agent_id=agent_id,
    )
    history = trait_lab_seed_history(store, verified["seed"])
    return {
        "applied": True,
        "seed": verified["seed"],
        "count": len(written),
        "proofs": written,
        "pack_sha256": pack_sha,
        "best": history["best"],
        "live_verified": False,
    }


def _pack_run_proof(raw: Any, index: int) -> str:
    if not isinstance(raw, dict):
        raise MemoryLayerError("invalid_run", f"run {index} must be an object")
    if raw.get("live_verified") is True:
        raise MemoryLayerError("live_claim", "seed pack run may not claim LIVE VERIFIED")
    sha = str(raw.get("proof_sha256") or "").strip().lower()
    if len(sha) != 64 or any(ch not in "0123456789abcdef" for ch in sha):
        raise MemoryLayerError("invalid_run", f"run {index} requires proof_sha256")
    return sha


def diff_trait_lab_seed_packs(pack_a: Any, pack_b: Any) -> dict[str, Any]:
    """Compare two rematched packs for one seed. Not a live ranking."""
    left = verify_trait_lab_seed_pack(pack_a)
    right = verify_trait_lab_seed_pack(pack_b)
    if left["seed"] != right["seed"]:
        raise MemoryLayerError(
            "seed_mismatch",
            f"pack seeds {left['seed']} != {right['seed']}",
        )
    if left["pack_sha256"] == right["pack_sha256"]:
        raise MemoryLayerError("same_pack", "diff requires two different pack hashes")
    proofs_a = [_pack_run_proof(raw, index) for index, raw in enumerate(left["runs"])]
    proofs_b = [_pack_run_proof(raw, index) for index, raw in enumerate(right["runs"])]
    set_b = set(proofs_b)
    set_a = set(proofs_a)
    best_a = left["best"] if isinstance(left["best"], dict) else {}
    best_b = right["best"] if isinstance(right["best"], dict) else {}
    return {
        "seed": left["seed"],
        "a": {
            "pack_sha256": left["pack_sha256"],
            "count": left["count"],
            "best": best_a,
        },
        "b": {
            "pack_sha256": right["pack_sha256"],
            "count": right["count"],
            "best": best_b,
        },
        "only_a": [sha for sha in proofs_a if sha not in set_b],
        "only_b": [sha for sha in proofs_b if sha not in set_a],
        "shared": [sha for sha in proofs_a if sha in set_b],
        "count_delta": int(left["count"]) - int(right["count"]),
        "xp_delta": int(best_a.get("xp") or 0) - int(best_b.get("xp") or 0),
        "same_seed": True,
        "live_verified": False,
    }


def _pack_catalog_row(entry: MemoryEntry) -> dict[str, Any] | None:
    if not entry.key.startswith("verified:trait-lab-pack-"):
        return None
    if entry.value.get("live_verified") is True:
        return None
    sha = str(entry.value.get("source") or entry.metadata.get("source") or "").strip().lower()
    if len(sha) != 64 or any(ch not in "0123456789abcdef" for ch in sha):
        return None
    seed = entry.value.get("seed")
    if isinstance(seed, bool) or not isinstance(seed, int):
        return None
    count = entry.value.get("count")
    if isinstance(count, bool) or not isinstance(count, int):
        match = _PACK_COUNT_IN_FACT.search(str(entry.value.get("fact") or ""))
        if not match:
            return None
        count = int(match.group(1))
    return {
        "pack_sha256": sha,
        "fact_id": f"trait-lab-pack-{sha[:16]}",
        "kind": _TRAIT_LAB_SEED_PACK_KIND,
        "seed": seed,
        "count": count,
        "agent_id": entry.agent_id,
        "task_id": entry.task_id,
        "live_verified": False,
    }


_TRAIT_LAB_CATALOG_KIND = "trait-lab-seed-pack-catalog"
TRAIT_LAB_CATALOG_OPS: tuple[str, ...] = (
    "catalog_for_seed",
    "has_pack",
    "list_ids",
    "count_packs",
    "list_seeds",
    "by_count_floor",
    "by_count_ceiling",
    "by_count_band",
    "page",
    "purge_pack",
    "digest",
    "export_catalog",
    "verify_catalog",
    "import_catalog",
    "by_agent",
    "by_task",
    "malformed_report",
    "has_seed",
    "best_for_seed",
    "diff_catalogs",
    "ids_for_seed",
    "etag",
    "refuse_live",
    "public_row",
    "get_pack",
)


def _require_catalog_limit(limit: int) -> int:
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise MemoryLayerError("invalid_limit", "limit must be >= 1")
    return limit


def _require_catalog_offset(offset: int) -> int:
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
        raise MemoryLayerError("invalid_offset", "offset must be >= 0")
    return offset


def _collect_trait_lab_seed_pack_rows(store: MemoryStore, *, scan: int = 200) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in query_layer(
        store,
        MemoryLayer.VERIFIED_KNOWLEDGE,
        prefix="verified:trait-lab-pack-",
        limit=scan,
    ):
        row = _pack_catalog_row(entry)
        if row is None or row["pack_sha256"] in seen:
            continue
        seen.add(row["pack_sha256"])
        found.append(row)
    found.sort(key=lambda row: (int(row["seed"]), str(row["pack_sha256"])))
    return found


def _catalog_public_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "pack_sha256": row["pack_sha256"],
        "fact_id": row["fact_id"],
        "kind": _TRAIT_LAB_SEED_PACK_KIND,
        "seed": row["seed"],
        "count": row["count"],
        "live_verified": False,
    }


def _catalog_bundle(rows: list[dict[str, Any]], *, limit: int | None = None) -> dict[str, Any]:
    selected = rows if limit is None else rows[:limit]
    return {
        "kind": _TRAIT_LAB_CATALOG_KIND,
        "packs": selected,
        "count": len(rows),
        "live_verified": False,
    }


def refuse_trait_lab_catalog_live(payload: Any) -> None:
    """C23 — catalog payloads may not claim LIVE VERIFIED."""
    if isinstance(payload, dict) and payload.get("live_verified") is True:
        raise MemoryLayerError("live_claim", "seed pack catalog may not claim LIVE VERIFIED")


def catalog_trait_lab_seed_packs(store: MemoryStore, *, limit: int = 50) -> dict[str, Any]:
    """Index imported or applied seed packs. Not a live ranking."""
    limit = _require_catalog_limit(limit)
    found = _collect_trait_lab_seed_pack_rows(store, scan=max(limit * 4, 200))
    return _catalog_bundle(found, limit=limit)


def get_trait_lab_seed_pack(store: MemoryStore, pack_sha256: str) -> dict[str, Any]:
    """Select one cataloged pack by pack_sha256. Does not execute the pack."""
    sha = str(pack_sha256 or "").strip().lower()
    if len(sha) != 64 or any(ch not in "0123456789abcdef" for ch in sha):
        raise MemoryLayerError("missing_pack_hash", "catalog select requires pack_sha256")
    try:
        viewed = read_verified(store, f"trait-lab-pack-{sha[:16]}")
    except MemoryLayerError as exc:
        if exc.code == "missing_verified":
            raise MemoryLayerError("missing_pack", f"no cataloged seed pack {sha[:12]}") from exc
        raise
    row = _pack_catalog_row(viewed["entry"])
    if row is None or row["pack_sha256"] != sha:
        raise MemoryLayerError("missing_pack", f"no cataloged seed pack {sha[:12]}")
    return row


def catalog_trait_lab_seed_packs_for_seed(
    store: MemoryStore,
    seed: int,
    *,
    limit: int = 50,
) -> dict[str, Any]:
    """C01 — catalog imported or applied packs for one seed."""
    limit = _require_catalog_limit(limit)
    key = _seed_key(seed)
    rows = [row for row in _collect_trait_lab_seed_pack_rows(store) if int(row["seed"]) == key]
    if not rows:
        raise MemoryLayerError("missing_seed", f"no cataloged seed pack for seed {key}")
    rows.sort(key=lambda row: str(row["pack_sha256"]))
    return {**_catalog_bundle(rows, limit=limit), "seed": key}


def has_trait_lab_seed_pack(store: MemoryStore, pack_sha256: str) -> bool:
    """C02 — true when a catalog row exists for pack_sha256."""
    sha = str(pack_sha256 or "").strip().lower()
    if len(sha) != 64 or any(ch not in "0123456789abcdef" for ch in sha):
        raise MemoryLayerError("missing_pack_hash", "has_pack requires pack_sha256")
    return any(row["pack_sha256"] == sha for row in _collect_trait_lab_seed_pack_rows(store))


def list_trait_lab_seed_pack_ids(store: MemoryStore, *, limit: int = 50) -> list[str]:
    """C03 — stable pack_sha256 identifiers."""
    limit = _require_catalog_limit(limit)
    return [row["pack_sha256"] for row in _collect_trait_lab_seed_pack_rows(store)[:limit]]


def count_trait_lab_seed_packs(store: MemoryStore) -> int:
    """C04 — number of cataloged packs."""
    return len(_collect_trait_lab_seed_pack_rows(store))


def list_trait_lab_seed_pack_seeds(store: MemoryStore, *, limit: int = 50) -> list[int]:
    """C05 — distinct seeds that have cataloged packs, ascending."""
    limit = _require_catalog_limit(limit)
    seeds: list[int] = []
    seen: set[int] = set()
    for row in _collect_trait_lab_seed_pack_rows(store):
        seed = int(row["seed"])
        if seed in seen:
            continue
        seen.add(seed)
        seeds.append(seed)
    return seeds[:limit]


def catalog_trait_lab_seed_packs_by_count_floor(
    store: MemoryStore,
    floor: int,
    *,
    limit: int = 50,
) -> dict[str, Any]:
    """C06 — packs whose stored count is at or above floor."""
    limit = _require_catalog_limit(limit)
    low = _xp_bound(floor, code="invalid_floor", label="floor")
    rows = [row for row in _collect_trait_lab_seed_pack_rows(store) if int(row["count"]) >= low]
    if not rows:
        raise MemoryLayerError("missing_floor", f"no cataloged pack with count >= {low}")
    return {**_catalog_bundle(rows, limit=limit), "floor": low}


def catalog_trait_lab_seed_packs_by_count_ceiling(
    store: MemoryStore,
    ceiling: int,
    *,
    limit: int = 50,
) -> dict[str, Any]:
    """C07 — packs whose stored count is at or below ceiling."""
    limit = _require_catalog_limit(limit)
    high = _xp_bound(ceiling, code="invalid_ceiling", label="ceiling")
    rows = [row for row in _collect_trait_lab_seed_pack_rows(store) if int(row["count"]) <= high]
    if not rows:
        raise MemoryLayerError("missing_ceiling", f"no cataloged pack with count <= {high}")
    return {**_catalog_bundle(rows, limit=limit), "ceiling": high}


def catalog_trait_lab_seed_packs_by_count_band(
    store: MemoryStore,
    floor: int,
    ceiling: int,
    *,
    limit: int = 50,
) -> dict[str, Any]:
    """C08 — packs whose stored count is inside [floor, ceiling]."""
    limit = _require_catalog_limit(limit)
    low = _xp_bound(floor, code="invalid_floor", label="floor")
    high = _xp_bound(ceiling, code="invalid_ceiling", label="ceiling")
    if low > high:
        raise MemoryLayerError("invalid_band", "floor must be <= ceiling")
    rows = [row for row in _collect_trait_lab_seed_pack_rows(store) if low <= int(row["count"]) <= high]
    if not rows:
        raise MemoryLayerError("missing_band", f"no cataloged pack with count {low}-{high}")
    return {**_catalog_bundle(rows, limit=limit), "floor": low, "ceiling": high}


def catalog_trait_lab_seed_packs_page(
    store: MemoryStore,
    *,
    offset: int = 0,
    limit: int = 50,
) -> dict[str, Any]:
    """C09 — deterministic catalog page."""
    limit = _require_catalog_limit(limit)
    start = _require_catalog_offset(offset)
    rows = _collect_trait_lab_seed_pack_rows(store)
    page = rows[start : start + limit]
    return {
        "kind": _TRAIT_LAB_CATALOG_KIND,
        "packs": page,
        "count": len(rows),
        "offset": start,
        "limit": limit,
        "live_verified": False,
    }


def purge_trait_lab_seed_pack(store: MemoryStore, pack_sha256: str) -> dict[str, Any]:
    """C10 — drop the catalog fact only. Run rows stay."""
    row = get_trait_lab_seed_pack(store, pack_sha256)
    key = f"verified:{row['fact_id']}"
    if not store.delete(key):
        raise MemoryLayerError("missing_pack", f"no cataloged seed pack {row['pack_sha256'][:12]}")
    return {
        "purged": True,
        "pack_sha256": row["pack_sha256"],
        "fact_id": row["fact_id"],
        "live_verified": False,
    }


def catalog_trait_lab_seed_packs_digest(store: MemoryStore) -> str:
    """C11 — SHA-256 over the stable public catalog body."""
    exported = export_trait_lab_seed_pack_catalog(store)
    return str(exported["catalog_sha256"])


def _catalog_export_body(rows: list[dict[str, Any]]) -> dict[str, Any]:
    public = [_catalog_public_row(row) for row in rows]
    return {
        "kind": _TRAIT_LAB_CATALOG_KIND,
        "packs": public,
        "count": len(public),
        "live_verified": False,
    }


def export_trait_lab_seed_pack_catalog(store: MemoryStore, *, limit: int = 50) -> dict[str, Any]:
    """C12 — portable catalog snapshot. Not a live ranking."""
    limit = _require_catalog_limit(limit)
    rows = _collect_trait_lab_seed_pack_rows(store)[:limit]
    body = _catalog_export_body(rows)
    refuse_trait_lab_catalog_live(body)
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        **body,
        "catalog_sha256": hashlib.sha256(encoded).hexdigest(),
        "exported_at": _utc(),
    }


def verify_trait_lab_seed_pack_catalog(catalog: Any) -> dict[str, Any]:
    """C13 — rematch catalog_sha256 over the stable catalog body."""
    if not isinstance(catalog, dict):
        raise MemoryLayerError("invalid_catalog", "catalog must be an object")
    if catalog.get("kind") != _TRAIT_LAB_CATALOG_KIND:
        raise MemoryLayerError("invalid_catalog", "kind must be trait-lab-seed-pack-catalog")
    refuse_trait_lab_catalog_live(catalog)
    if not isinstance(catalog.get("packs"), list):
        raise MemoryLayerError("invalid_catalog", "packs must be a list")
    sha = str(catalog.get("catalog_sha256") or "").strip().lower()
    if len(sha) != 64 or any(ch not in "0123456789abcdef" for ch in sha):
        raise MemoryLayerError("missing_catalog_hash", "verify requires catalog_sha256")
    public = [_catalog_public_row(row) for row in catalog["packs"] if isinstance(row, dict)]
    if len(public) != len(catalog["packs"]):
        raise MemoryLayerError("invalid_catalog", "every catalog pack must be an object")
    body = _catalog_export_body(public)
    got = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    if got != sha:
        raise MemoryLayerError("catalog_mismatch", f"catalog hashed {got[:12]} not {sha[:12]}")
    return {**body, "matched": True, "catalog_sha256": sha, "live_verified": False}


def import_trait_lab_seed_pack_catalog(
    store: MemoryStore,
    catalog: Any,
    *,
    agent_id: str,
    task_id: str,
) -> dict[str, Any]:
    """C14 — write rematched catalog facts. Does not apply runs."""
    if not str(agent_id or "").strip() or not str(task_id or "").strip():
        raise MemoryLayerError("missing_provenance", "catalog import requires agent_id and task_id")
    verified = verify_trait_lab_seed_pack_catalog(catalog)
    written: list[str] = []
    for row in verified["packs"]:
        _write_trait_lab_seed_pack_fact(
            store,
            {
                "pack_sha256": row["pack_sha256"],
                "seed": row["seed"],
                "count": row["count"],
            },
            agent_id=agent_id,
            task_id=task_id,
        )
        written.append(row["pack_sha256"])
    return {
        "imported": True,
        "count": len(written),
        "ids": written,
        "catalog_sha256": verified["catalog_sha256"],
        "live_verified": False,
    }


def catalog_trait_lab_seed_packs_by_agent(
    store: MemoryStore,
    agent_id: str,
    *,
    limit: int = 50,
) -> dict[str, Any]:
    """C15 — catalog rows written by one agent."""
    limit = _require_catalog_limit(limit)
    wanted = str(agent_id or "").strip()
    if not wanted:
        raise MemoryLayerError("missing_agent", "catalog by agent requires agent_id")
    rows = [row for row in _collect_trait_lab_seed_pack_rows(store) if row.get("agent_id") == wanted]
    if not rows:
        raise MemoryLayerError("missing_agent", f"no cataloged pack for agent {wanted}")
    return {**_catalog_bundle(rows, limit=limit), "agent_id": wanted}


def catalog_trait_lab_seed_packs_by_task(
    store: MemoryStore,
    task_id: str,
    *,
    limit: int = 50,
) -> dict[str, Any]:
    """C16 — catalog rows written by one task."""
    limit = _require_catalog_limit(limit)
    wanted = str(task_id or "").strip()
    if not wanted:
        raise MemoryLayerError("missing_task", "catalog by task requires task_id")
    rows = [row for row in _collect_trait_lab_seed_pack_rows(store) if row.get("task_id") == wanted]
    if not rows:
        raise MemoryLayerError("missing_task", f"no cataloged pack for task {wanted}")
    return {**_catalog_bundle(rows, limit=limit), "task_id": wanted}


def report_malformed_trait_lab_seed_packs(store: MemoryStore, *, limit: int = 50) -> dict[str, Any]:
    """C17 — keys that look like pack facts but fail the catalog row contract."""
    limit = _require_catalog_limit(limit)
    bad: list[str] = []
    for entry in query_layer(
        store,
        MemoryLayer.VERIFIED_KNOWLEDGE,
        prefix="verified:trait-lab-pack-",
        limit=max(limit * 4, 200),
    ):
        if _pack_catalog_row(entry) is None:
            bad.append(entry.key)
        if len(bad) >= limit:
            break
    return {"kind": "trait-lab-seed-pack-malformed", "keys": bad, "count": len(bad), "live_verified": False}


def catalog_has_seed(store: MemoryStore, seed: int) -> bool:
    """C18 — true when any catalog row exists for the seed."""
    key = _seed_key(seed)
    return any(int(row["seed"]) == key for row in _collect_trait_lab_seed_pack_rows(store))


def best_trait_lab_seed_pack_for_seed(store: MemoryStore, seed: int) -> dict[str, Any]:
    """C19 — highest count for one seed; hash breaks ties. Not a live ranking."""
    catalog = catalog_trait_lab_seed_packs_for_seed(store, seed, limit=200)
    rows = list(catalog["packs"])
    rows.sort(key=lambda row: (-int(row["count"]), str(row["pack_sha256"])))
    return {**rows[0], "live_verified": False}


def diff_trait_lab_seed_pack_catalogs(catalog_a: Any, catalog_b: Any) -> dict[str, Any]:
    """C20 — compare two rematched catalog snapshots."""
    left = verify_trait_lab_seed_pack_catalog(catalog_a)
    right = verify_trait_lab_seed_pack_catalog(catalog_b)
    if left["catalog_sha256"] == right["catalog_sha256"]:
        raise MemoryLayerError("same_catalog", "diff requires two different catalog hashes")
    ids_a = [row["pack_sha256"] for row in left["packs"]]
    ids_b = [row["pack_sha256"] for row in right["packs"]]
    set_a = set(ids_a)
    set_b = set(ids_b)
    return {
        "kind": _TRAIT_LAB_CATALOG_KIND,
        "only_a": [sha for sha in ids_a if sha not in set_b],
        "only_b": [sha for sha in ids_b if sha not in set_a],
        "shared": [sha for sha in ids_a if sha in set_b],
        "count_delta": int(left["count"]) - int(right["count"]),
        "live_verified": False,
    }


def _public_pack_map(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    for row in rows:
        public = _catalog_public_row(row)
        sha = str(public["pack_sha256"])
        prior = found.get(sha)
        if prior is not None:
            if int(prior["seed"]) != int(public["seed"]) or int(prior["count"]) != int(public["count"]):
                raise MemoryLayerError("pack_conflict", f"pack {sha[:12]} disagrees")
            continue
        found[sha] = public
    return found


def _compose_trait_lab_seed_pack_catalogs(
    catalog_a: Any,
    catalog_b: Any,
    *,
    mode: str,
) -> dict[str, Any]:
    if mode not in {"merge", "intersect", "subtract", "xor"}:
        raise MemoryLayerError("invalid_compose", f"unknown compose mode {mode}")
    left = verify_trait_lab_seed_pack_catalog(catalog_a)
    right = verify_trait_lab_seed_pack_catalog(catalog_b)
    if left["catalog_sha256"] == right["catalog_sha256"]:
        raise MemoryLayerError("same_catalog", f"{mode} requires two different catalog hashes")
    map_a = _public_pack_map(left["packs"])
    map_b = _public_pack_map(right["packs"])
    for sha, row in map_b.items():
        prior = map_a.get(sha)
        if prior is not None and (
            int(prior["seed"]) != int(row["seed"]) or int(prior["count"]) != int(row["count"])
        ):
            raise MemoryLayerError("pack_conflict", f"pack {sha[:12]} disagrees across catalogs")
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
    rows = sorted(selected.values(), key=lambda row: (int(row["seed"]), str(row["pack_sha256"])))
    body = _catalog_export_body(rows)
    refuse_trait_lab_catalog_live(body)
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        **body,
        "catalog_sha256": hashlib.sha256(encoded).hexdigest(),
        "mode": mode,
        "a": left["catalog_sha256"],
        "b": right["catalog_sha256"],
        "live_verified": False,
    }


def merge_trait_lab_seed_pack_catalogs(catalog_a: Any, catalog_b: Any) -> dict[str, Any]:
    """Union two rematched catalog snapshots. Not a live ranking."""
    return _compose_trait_lab_seed_pack_catalogs(catalog_a, catalog_b, mode="merge")


def intersect_trait_lab_seed_pack_catalogs(catalog_a: Any, catalog_b: Any) -> dict[str, Any]:
    """Shared packs of two rematched catalogs. Not a live ranking."""
    return _compose_trait_lab_seed_pack_catalogs(catalog_a, catalog_b, mode="intersect")


def subtract_trait_lab_seed_pack_catalogs(catalog_a: Any, catalog_b: Any) -> dict[str, Any]:
    """Packs in A that are not in B. Not a live ranking."""
    return _compose_trait_lab_seed_pack_catalogs(catalog_a, catalog_b, mode="subtract")


def symmetric_diff_trait_lab_seed_pack_catalogs(catalog_a: Any, catalog_b: Any) -> dict[str, Any]:
    """Packs in exactly one rematched catalog. Not a live ranking."""
    return _compose_trait_lab_seed_pack_catalogs(catalog_a, catalog_b, mode="xor")


def retain_trait_lab_seed_pack_catalog(catalog: Any, *, keep: int = 1) -> dict[str, Any]:
    """Keep the highest-count packs from a rematched catalog. Not a live ranking."""
    if isinstance(keep, bool) or not isinstance(keep, int) or keep < 1:
        raise MemoryLayerError("invalid_keep", "keep must be >= 1")
    verified = verify_trait_lab_seed_pack_catalog(catalog)
    rows = [_catalog_public_row(row) for row in verified["packs"]]
    if not rows:
        raise MemoryLayerError("missing_pack", "retain requires at least one pack")
    rows.sort(key=lambda row: (-int(row["count"]), str(row["pack_sha256"])))
    selected = rows[:keep]
    body = _catalog_export_body(selected)
    refuse_trait_lab_catalog_live(body)
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        **body,
        "catalog_sha256": hashlib.sha256(encoded).hexdigest(),
        "kept": len(selected),
        "keep": keep,
        "live_verified": False,
    }


def list_trait_lab_seed_pack_ids_for_seed(store: MemoryStore, seed: int, *, limit: int = 50) -> list[str]:
    """C21 — pack_sha256 values for one seed, sorted."""
    catalog = catalog_trait_lab_seed_packs_for_seed(store, seed, limit=limit)
    return [row["pack_sha256"] for row in catalog["packs"]]


def catalog_trait_lab_seed_pack_etag(store: MemoryStore) -> str:
    """C22 — short digest for catalog identity."""
    return catalog_trait_lab_seed_packs_digest(store)[:16]


def public_trait_lab_seed_pack_row(row: dict[str, Any]) -> dict[str, Any]:
    """C24 — stable selector row without agent/task fields."""
    if not isinstance(row, dict) or not row.get("pack_sha256"):
        raise MemoryLayerError("invalid_pack", "public row requires a pack")
    return _catalog_public_row(row)


_TRAIT_LAB_CATALOG_PIN_KIND = "trait-lab-seed-pack-catalog-pin"


def _require_catalog_sha(catalog_sha256: Any) -> str:
    sha = str(catalog_sha256 or "").strip().lower()
    if len(sha) != 64 or any(ch not in "0123456789abcdef" for ch in sha):
        raise MemoryLayerError("missing_catalog_hash", "catalog pin requires catalog_sha256")
    return sha


_CATALOG_PIN_FACT_PREFIX = "trait-lab-catalog-"


def _catalog_pin_fact_id(catalog_sha256: str) -> str:
    return f"{_CATALOG_PIN_FACT_PREFIX}{catalog_sha256[:16]}"


def _require_catalog_pin_fact_id(fact_id: Any) -> str:
    wanted = str(fact_id or "").strip()
    suffix = wanted[len(_CATALOG_PIN_FACT_PREFIX) :] if wanted.startswith(_CATALOG_PIN_FACT_PREFIX) else ""
    if (
        not wanted.startswith(_CATALOG_PIN_FACT_PREFIX)
        or len(suffix) != 16
        or any(ch not in "0123456789abcdef" for ch in suffix)
    ):
        raise MemoryLayerError("missing_pin", "pin select requires fact_id")
    return wanted


def _pin_ids_key(ids: list[str]) -> frozenset[str]:
    return frozenset(str(item) for item in ids)


def _catalog_pin_row(entry: MemoryEntry) -> dict[str, Any] | None:
    if not entry.key.startswith("verified:trait-lab-catalog-"):
        return None
    if entry.value.get("live_verified") is True:
        return None
    sha = str(entry.value.get("source") or entry.metadata.get("source") or "").strip().lower()
    if len(sha) != 64 or any(ch not in "0123456789abcdef" for ch in sha):
        return None
    count = entry.value.get("count")
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        return None
    raw_ids = entry.value.get("ids")
    if not isinstance(raw_ids, list):
        return None
    ids = [str(item).strip().lower() for item in raw_ids]
    if any(len(item) != 64 or any(ch not in "0123456789abcdef" for ch in item) for item in ids):
        return None
    return {
        "catalog_sha256": sha,
        "fact_id": _catalog_pin_fact_id(sha),
        "kind": _TRAIT_LAB_CATALOG_PIN_KIND,
        "count": count,
        "ids": ids,
        "agent_id": entry.agent_id,
        "task_id": entry.task_id,
        "live_verified": False,
    }


def _collect_trait_lab_catalog_pins(store: MemoryStore, *, scan: int = 200) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in query_layer(
        store,
        MemoryLayer.VERIFIED_KNOWLEDGE,
        prefix="verified:trait-lab-catalog-",
        limit=scan,
    ):
        row = _catalog_pin_row(entry)
        if row is None or row["catalog_sha256"] in seen:
            continue
        seen.add(row["catalog_sha256"])
        found.append(row)
    found.sort(key=lambda row: str(row["catalog_sha256"]))
    return found


def pin_trait_lab_seed_pack_catalog(
    store: MemoryStore,
    catalog: Any,
    *,
    agent_id: str,
    task_id: str,
) -> dict[str, Any]:
    """Persist a rematched catalog snapshot. Does not apply runs."""
    if not str(agent_id or "").strip() or not str(task_id or "").strip():
        raise MemoryLayerError("missing_provenance", "catalog pin requires agent_id and task_id")
    verified = verify_trait_lab_seed_pack_catalog(catalog)
    sha = str(verified["catalog_sha256"])
    ids = [str(row["pack_sha256"]) for row in verified["packs"]]
    write_verified(
        store,
        {
            "id": _catalog_pin_fact_id(sha),
            "fact": f"catalog {sha} count={verified['count']}",
            "how": f"pin_trait_lab_seed_pack_catalog {sha}",
            "confidence": 1.0,
            "source": sha,
            "agent_id": agent_id,
            "task_id": task_id,
            "kind": _TRAIT_LAB_CATALOG_PIN_KIND,
            "count": verified["count"],
            "ids": ids,
        },
    )
    record_task_step(
        store,
        task_id,
        "catalog-pin",
        {"catalog_sha256": sha, "count": verified["count"]},
        agent_id=agent_id,
    )
    return {
        "pinned": True,
        "catalog_sha256": sha,
        "fact_id": _catalog_pin_fact_id(sha),
        "count": verified["count"],
        "ids": ids,
        "live_verified": False,
    }


def get_trait_lab_catalog_pin(store: MemoryStore, catalog_sha256: str) -> dict[str, Any]:
    """Select one pinned catalog by catalog_sha256. Does not execute packs."""
    sha = _require_catalog_sha(catalog_sha256)
    entry = store.get(f"verified:{_catalog_pin_fact_id(sha)}")
    if entry is None:
        raise MemoryLayerError("missing_pin", f"no pinned catalog {sha[:12]}")
    row = _catalog_pin_row(entry)
    if row is None:
        raise MemoryLayerError("invalid_pin", f"pinned catalog {sha[:12]} is malformed")
    return {**row, "live_verified": False}


def has_trait_lab_catalog_pin(store: MemoryStore, catalog_sha256: str) -> bool:
    """True when a pin fact exists for catalog_sha256."""
    sha = _require_catalog_sha(catalog_sha256)
    return any(row["catalog_sha256"] == sha for row in _collect_trait_lab_catalog_pins(store))


def list_trait_lab_catalog_pins(store: MemoryStore, *, limit: int = 50) -> dict[str, Any]:
    """Index pinned catalog snapshots. Not a live ranking."""
    limit = _require_catalog_limit(limit)
    rows = _collect_trait_lab_catalog_pins(store, scan=max(limit * 4, 200))
    public = [
        {
            "catalog_sha256": row["catalog_sha256"],
            "fact_id": row["fact_id"],
            "kind": _TRAIT_LAB_CATALOG_PIN_KIND,
            "count": row["count"],
            "ids": row["ids"],
            "live_verified": False,
        }
        for row in rows[:limit]
    ]
    return {
        "kind": _TRAIT_LAB_CATALOG_PIN_KIND,
        "pins": public,
        "count": len(rows),
        "live_verified": False,
    }


def unpin_trait_lab_catalog_pin(store: MemoryStore, catalog_sha256: str) -> dict[str, Any]:
    """Drop the pin fact only. Pack facts and run rows stay."""
    row = get_trait_lab_catalog_pin(store, catalog_sha256)
    key = f"verified:{row['fact_id']}"
    if not store.delete(key):
        raise MemoryLayerError("missing_pin", f"no pinned catalog {row['catalog_sha256'][:12]}")
    return {
        "unpinned": True,
        "catalog_sha256": row["catalog_sha256"],
        "fact_id": row["fact_id"],
        "live_verified": False,
    }


_TRAIT_LAB_CATALOG_PIN_INDEX_KIND = "trait-lab-seed-pack-catalog-pin-index"
TRAIT_LAB_CATALOG_PIN_OPS: tuple[str, ...] = (
    "list_ids",
    "count_pins",
    "page",
    "by_agent",
    "by_task",
    "by_count_floor",
    "by_count_ceiling",
    "by_count_band",
    "digest",
    "etag",
    "export_index",
    "verify_index",
    "import_index",
    "malformed_report",
    "best_pin",
    "diff_indexes",
    "public_row",
    "refuse_live",
    "has_pack",
    "ids_for_pack",
    "get_by_fact_id",
    "pin_from_store",
    "has_count",
    "count_for_pack",
    "ids_for_agent",
)


def _require_pack_sha(pack_sha256: Any) -> str:
    sha = str(pack_sha256 or "").strip().lower()
    if len(sha) != 64 or any(ch not in "0123456789abcdef" for ch in sha):
        raise MemoryLayerError("missing_pack_hash", "pin pack filter requires pack_sha256")
    return sha


def _pin_public_row(row: dict[str, Any]) -> dict[str, Any]:
    sha = _require_catalog_sha(row.get("catalog_sha256"))
    count = row.get("count")
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        raise MemoryLayerError("invalid_pin", "public pin requires count")
    raw_ids = row.get("ids")
    if not isinstance(raw_ids, list):
        raise MemoryLayerError("invalid_pin", "public pin requires ids")
    ids = [str(item).strip().lower() for item in raw_ids]
    if any(len(item) != 64 or any(ch not in "0123456789abcdef" for ch in item) for item in ids):
        raise MemoryLayerError("invalid_pin", "public pin ids must be pack hashes")
    return {
        "catalog_sha256": sha,
        "fact_id": _catalog_pin_fact_id(sha),
        "kind": _TRAIT_LAB_CATALOG_PIN_KIND,
        "count": count,
        "ids": ids,
        "live_verified": False,
    }


def _pin_bundle(rows: list[dict[str, Any]], *, limit: int | None = None) -> dict[str, Any]:
    selected = rows if limit is None else rows[:limit]
    return {
        "kind": _TRAIT_LAB_CATALOG_PIN_KIND,
        "pins": [_pin_public_row(row) for row in selected],
        "count": len(rows),
        "live_verified": False,
    }


def _pin_index_body(rows: list[dict[str, Any]]) -> dict[str, Any]:
    public = [_pin_public_row(row) for row in rows]
    return {
        "kind": _TRAIT_LAB_CATALOG_PIN_INDEX_KIND,
        "pins": public,
        "count": len(public),
        "live_verified": False,
    }


def refuse_trait_lab_catalog_pin_live(payload: Any) -> None:
    """P18 — pin payloads may not claim LIVE VERIFIED."""
    if isinstance(payload, dict) and payload.get("live_verified") is True:
        raise MemoryLayerError("live_claim", "catalog pin may not claim LIVE VERIFIED")


def list_trait_lab_catalog_pin_ids(store: MemoryStore, *, limit: int = 50) -> list[str]:
    """P01 — catalog_sha256 values, sorted."""
    return [row["catalog_sha256"] for row in list_trait_lab_catalog_pins(store, limit=limit)["pins"]]


def count_trait_lab_catalog_pins(store: MemoryStore) -> int:
    """P02 — number of pinned catalogs."""
    return len(_collect_trait_lab_catalog_pins(store))


def catalog_trait_lab_pins_page(
    store: MemoryStore,
    *,
    offset: int = 0,
    limit: int = 50,
) -> dict[str, Any]:
    """P03 — deterministic pin page."""
    limit = _require_catalog_limit(limit)
    start = _require_catalog_offset(offset)
    rows = _collect_trait_lab_catalog_pins(store)
    return {
        **_pin_bundle(rows[start : start + limit]),
        "count": len(rows),
        "offset": start,
        "limit": limit,
    }


def catalog_trait_lab_pins_by_agent(
    store: MemoryStore,
    agent_id: str,
    *,
    limit: int = 50,
) -> dict[str, Any]:
    """P04 — pins written by one agent."""
    limit = _require_catalog_limit(limit)
    wanted = str(agent_id or "").strip()
    if not wanted:
        raise MemoryLayerError("missing_agent", "pin by agent requires agent_id")
    rows = [row for row in _collect_trait_lab_catalog_pins(store) if row.get("agent_id") == wanted]
    if not rows:
        raise MemoryLayerError("missing_agent", f"no pinned catalog for agent {wanted}")
    return {**_pin_bundle(rows, limit=limit), "agent_id": wanted}


def catalog_trait_lab_pins_by_task(
    store: MemoryStore,
    task_id: str,
    *,
    limit: int = 50,
) -> dict[str, Any]:
    """P05 — pins written by one task."""
    limit = _require_catalog_limit(limit)
    wanted = str(task_id or "").strip()
    if not wanted:
        raise MemoryLayerError("missing_task", "pin by task requires task_id")
    rows = [row for row in _collect_trait_lab_catalog_pins(store) if row.get("task_id") == wanted]
    if not rows:
        raise MemoryLayerError("missing_task", f"no pinned catalog for task {wanted}")
    return {**_pin_bundle(rows, limit=limit), "task_id": wanted}


def catalog_trait_lab_pins_by_count_floor(
    store: MemoryStore,
    floor: int,
    *,
    limit: int = 50,
) -> dict[str, Any]:
    """P06 — pins whose stored count is at or above floor."""
    limit = _require_catalog_limit(limit)
    low = _xp_bound(floor, code="invalid_floor", label="floor")
    rows = [row for row in _collect_trait_lab_catalog_pins(store) if int(row["count"]) >= low]
    if not rows:
        raise MemoryLayerError("missing_floor", f"no pinned catalog with count >= {low}")
    return {**_pin_bundle(rows, limit=limit), "floor": low}


def catalog_trait_lab_pins_by_count_ceiling(
    store: MemoryStore,
    ceiling: int,
    *,
    limit: int = 50,
) -> dict[str, Any]:
    """P07 — pins whose stored count is at or below ceiling."""
    limit = _require_catalog_limit(limit)
    high = _xp_bound(ceiling, code="invalid_ceiling", label="ceiling")
    rows = [row for row in _collect_trait_lab_catalog_pins(store) if int(row["count"]) <= high]
    if not rows:
        raise MemoryLayerError("missing_ceiling", f"no pinned catalog with count <= {high}")
    return {**_pin_bundle(rows, limit=limit), "ceiling": high}


def catalog_trait_lab_pins_by_count_band(
    store: MemoryStore,
    floor: int,
    ceiling: int,
    *,
    limit: int = 50,
) -> dict[str, Any]:
    """P08 — pins whose stored count is inside [floor, ceiling]."""
    limit = _require_catalog_limit(limit)
    low = _xp_bound(floor, code="invalid_floor", label="floor")
    high = _xp_bound(ceiling, code="invalid_ceiling", label="ceiling")
    if low > high:
        raise MemoryLayerError("invalid_band", "floor must be <= ceiling")
    rows = [
        row for row in _collect_trait_lab_catalog_pins(store) if low <= int(row["count"]) <= high
    ]
    if not rows:
        raise MemoryLayerError("missing_band", f"no pinned catalog with count {low}-{high}")
    return {**_pin_bundle(rows, limit=limit), "floor": low, "ceiling": high}


def catalog_trait_lab_pins_digest(store: MemoryStore) -> str:
    """P09 — SHA-256 over the stable public pin index body."""
    return str(export_trait_lab_catalog_pins(store)["pin_index_sha256"])


def catalog_trait_lab_pin_etag(store: MemoryStore) -> str:
    """P10 — short digest for pin-index identity."""
    return catalog_trait_lab_pins_digest(store)[:16]


def export_trait_lab_catalog_pins(store: MemoryStore, *, limit: int = 50) -> dict[str, Any]:
    """P11 — portable pin-index snapshot. Not a live ranking."""
    limit = _require_catalog_limit(limit)
    rows = _collect_trait_lab_catalog_pins(store)[:limit]
    body = _pin_index_body(rows)
    refuse_trait_lab_catalog_pin_live(body)
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        **body,
        "pin_index_sha256": hashlib.sha256(encoded).hexdigest(),
        "exported_at": _utc(),
    }


def verify_trait_lab_catalog_pins(index: Any) -> dict[str, Any]:
    """P12 — rematch pin_index_sha256 over the stable pin-index body."""
    if not isinstance(index, dict):
        raise MemoryLayerError("invalid_pin_index", "pin index must be an object")
    if index.get("kind") != _TRAIT_LAB_CATALOG_PIN_INDEX_KIND:
        raise MemoryLayerError("invalid_pin_index", "kind must be trait-lab-seed-pack-catalog-pin-index")
    refuse_trait_lab_catalog_pin_live(index)
    if not isinstance(index.get("pins"), list):
        raise MemoryLayerError("invalid_pin_index", "pins must be a list")
    sha = str(index.get("pin_index_sha256") or "").strip().lower()
    if len(sha) != 64 or any(ch not in "0123456789abcdef" for ch in sha):
        raise MemoryLayerError("missing_pin_index_hash", "verify requires pin_index_sha256")
    public = [_pin_public_row(row) for row in index["pins"] if isinstance(row, dict)]
    if len(public) != len(index["pins"]):
        raise MemoryLayerError("invalid_pin_index", "every pin row must be an object")
    body = _pin_index_body(public)
    got = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    if got != sha:
        raise MemoryLayerError("pin_index_mismatch", f"pin index hashed {got[:12]} not {sha[:12]}")
    return {**body, "matched": True, "pin_index_sha256": sha, "live_verified": False}


def import_trait_lab_catalog_pins(
    store: MemoryStore,
    index: Any,
    *,
    agent_id: str,
    task_id: str,
) -> dict[str, Any]:
    """P13 — write rematched pin facts. Does not apply packs or runs."""
    if not str(agent_id or "").strip() or not str(task_id or "").strip():
        raise MemoryLayerError("missing_provenance", "pin import requires agent_id and task_id")
    verified = verify_trait_lab_catalog_pins(index)
    written: list[str] = []
    for row in verified["pins"]:
        write_verified(
            store,
            {
                "id": row["fact_id"],
                "fact": f"catalog {row['catalog_sha256']} count={row['count']}",
                "how": f"import_trait_lab_catalog_pins {verified['pin_index_sha256']}",
                "confidence": 1.0,
                "source": row["catalog_sha256"],
                "agent_id": agent_id,
                "task_id": task_id,
                "kind": _TRAIT_LAB_CATALOG_PIN_KIND,
                "count": row["count"],
                "ids": row["ids"],
            },
        )
        written.append(row["catalog_sha256"])
    return {
        "imported": True,
        "count": len(written),
        "ids": written,
        "pin_index_sha256": verified["pin_index_sha256"],
        "live_verified": False,
    }


def report_malformed_trait_lab_catalog_pins(store: MemoryStore, *, limit: int = 50) -> dict[str, Any]:
    """P14 — keys that look like pin facts but fail the pin row contract."""
    limit = _require_catalog_limit(limit)
    bad: list[str] = []
    for entry in query_layer(
        store,
        MemoryLayer.VERIFIED_KNOWLEDGE,
        prefix="verified:trait-lab-catalog-",
        limit=max(limit * 4, 200),
    ):
        if _catalog_pin_row(entry) is None:
            bad.append(entry.key)
        if len(bad) >= limit:
            break
    return {
        "kind": "trait-lab-seed-pack-catalog-pin-malformed",
        "keys": bad,
        "count": len(bad),
        "live_verified": False,
    }


def best_trait_lab_catalog_pin(store: MemoryStore) -> dict[str, Any]:
    """P15 — highest pin count; hash breaks ties. Not a live ranking."""
    rows = list(_collect_trait_lab_catalog_pins(store))
    if not rows:
        raise MemoryLayerError("missing_pin", "no pinned catalog")
    rows.sort(key=lambda row: (-int(row["count"]), str(row["catalog_sha256"])))
    return {**_pin_public_row(rows[0]), "live_verified": False}


def diff_trait_lab_catalog_pin_indexes(index_a: Any, index_b: Any) -> dict[str, Any]:
    """P16 — compare two rematched pin-index snapshots."""
    left = verify_trait_lab_catalog_pins(index_a)
    right = verify_trait_lab_catalog_pins(index_b)
    if left["pin_index_sha256"] == right["pin_index_sha256"]:
        raise MemoryLayerError("same_pin_index", "diff requires two different pin-index hashes")
    ids_a = [row["catalog_sha256"] for row in left["pins"]]
    ids_b = [row["catalog_sha256"] for row in right["pins"]]
    set_a = set(ids_a)
    set_b = set(ids_b)
    return {
        "kind": _TRAIT_LAB_CATALOG_PIN_INDEX_KIND,
        "only_a": [sha for sha in ids_a if sha not in set_b],
        "only_b": [sha for sha in ids_b if sha not in set_a],
        "shared": [sha for sha in ids_a if sha in set_b],
        "count_delta": int(left["count"]) - int(right["count"]),
        "live_verified": False,
    }


def public_trait_lab_catalog_pin_row(row: dict[str, Any]) -> dict[str, Any]:
    """P17 — stable selector row without agent/task fields."""
    if not isinstance(row, dict) or not row.get("catalog_sha256"):
        raise MemoryLayerError("invalid_pin", "public row requires a pin")
    return _pin_public_row(row)


def catalog_pin_has_pack(store: MemoryStore, pack_sha256: str) -> bool:
    """P19 — true when any pin lists the pack hash."""
    sha = _require_pack_sha(pack_sha256)
    return any(sha in row["ids"] for row in _collect_trait_lab_catalog_pins(store))


def list_trait_lab_catalog_pin_ids_for_pack(
    store: MemoryStore,
    pack_sha256: str,
    *,
    limit: int = 50,
) -> list[str]:
    """P20 — catalog_sha256 values that include one pack, sorted."""
    sha = _require_pack_sha(pack_sha256)
    limit = _require_catalog_limit(limit)
    ids = [
        row["catalog_sha256"]
        for row in _collect_trait_lab_catalog_pins(store)
        if sha in row["ids"]
    ]
    return ids[:limit]


def get_trait_lab_catalog_pin_by_fact_id(store: MemoryStore, fact_id: str) -> dict[str, Any]:
    """P21 — select one pin by fact_id."""
    wanted = _require_catalog_pin_fact_id(fact_id)
    entry = store.get(f"verified:{wanted}")
    if entry is None:
        raise MemoryLayerError("missing_pin", f"no pinned catalog {wanted}")
    row = _catalog_pin_row(entry)
    if row is None:
        raise MemoryLayerError("invalid_pin", f"pinned catalog {wanted} is malformed")
    return {**row, "live_verified": False}


def pin_trait_lab_seed_pack_catalog_from_store(
    store: MemoryStore,
    *,
    agent_id: str,
    task_id: str,
    limit: int = 50,
) -> dict[str, Any]:
    """P22 — export the store catalog and pin it."""
    catalog = export_trait_lab_seed_pack_catalog(store, limit=limit)
    if int(catalog["count"]) < 1:
        raise MemoryLayerError("missing_catalog", "store has no cataloged packs to pin")
    return pin_trait_lab_seed_pack_catalog(store, catalog, agent_id=agent_id, task_id=task_id)


def catalog_pin_has_count(store: MemoryStore, count: int) -> bool:
    """P23 — true when any pin stores this pack count."""
    wanted = _xp_bound(count, code="invalid_count", label="count")
    return any(int(row["count"]) == wanted for row in _collect_trait_lab_catalog_pins(store))


def count_trait_lab_catalog_pins_for_pack(store: MemoryStore, pack_sha256: str) -> int:
    """P24 — how many pins include one pack hash."""
    return len(list_trait_lab_catalog_pin_ids_for_pack(store, pack_sha256, limit=200))


def list_trait_lab_catalog_pin_ids_for_agent(
    store: MemoryStore,
    agent_id: str,
    *,
    limit: int = 50,
) -> list[str]:
    """P25 — catalog_sha256 values written by one agent."""
    return [row["catalog_sha256"] for row in catalog_trait_lab_pins_by_agent(store, agent_id, limit=limit)["pins"]]


def _public_pin_map(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    for row in rows:
        public = _pin_public_row(row)
        sha = str(public["catalog_sha256"])
        prior = found.get(sha)
        if prior is not None:
            if int(prior["count"]) != int(public["count"]) or _pin_ids_key(prior["ids"]) != _pin_ids_key(
                public["ids"]
            ):
                raise MemoryLayerError("pin_conflict", f"pin {sha[:12]} disagrees")
            continue
        found[sha] = public
    return found


def _compose_trait_lab_catalog_pin_indexes(
    index_a: Any,
    index_b: Any,
    *,
    mode: str,
) -> dict[str, Any]:
    if mode not in {"merge", "intersect", "subtract", "xor"}:
        raise MemoryLayerError("invalid_compose", f"unknown compose mode {mode}")
    left = verify_trait_lab_catalog_pins(index_a)
    right = verify_trait_lab_catalog_pins(index_b)
    if left["pin_index_sha256"] == right["pin_index_sha256"]:
        raise MemoryLayerError("same_pin_index", f"{mode} requires two different pin-index hashes")
    map_a = _public_pin_map(left["pins"])
    map_b = _public_pin_map(right["pins"])
    for sha, row in map_b.items():
        prior = map_a.get(sha)
        if prior is not None and (
            int(prior["count"]) != int(row["count"])
            or _pin_ids_key(prior["ids"]) != _pin_ids_key(row["ids"])
        ):
            raise MemoryLayerError("pin_conflict", f"pin {sha[:12]} disagrees across indexes")
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
    rows = sorted(selected.values(), key=lambda row: str(row["catalog_sha256"]))
    body = _pin_index_body(rows)
    refuse_trait_lab_catalog_pin_live(body)
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        **body,
        "pin_index_sha256": hashlib.sha256(encoded).hexdigest(),
        "mode": mode,
        "a": left["pin_index_sha256"],
        "b": right["pin_index_sha256"],
        "live_verified": False,
    }


def merge_trait_lab_catalog_pin_indexes(index_a: Any, index_b: Any) -> dict[str, Any]:
    """Union two rematched pin-index snapshots. Not a live ranking."""
    return _compose_trait_lab_catalog_pin_indexes(index_a, index_b, mode="merge")


def intersect_trait_lab_catalog_pin_indexes(index_a: Any, index_b: Any) -> dict[str, Any]:
    """Shared pins of two rematched pin indexes. Not a live ranking."""
    return _compose_trait_lab_catalog_pin_indexes(index_a, index_b, mode="intersect")


def subtract_trait_lab_catalog_pin_indexes(index_a: Any, index_b: Any) -> dict[str, Any]:
    """Pins in A that are not in B. Not a live ranking."""
    return _compose_trait_lab_catalog_pin_indexes(index_a, index_b, mode="subtract")


def symmetric_diff_trait_lab_catalog_pin_indexes(index_a: Any, index_b: Any) -> dict[str, Any]:
    """Pins in exactly one rematched index. Not a live ranking."""
    return _compose_trait_lab_catalog_pin_indexes(index_a, index_b, mode="xor")


def retain_trait_lab_catalog_pin_index(index: Any, *, keep: int = 1) -> dict[str, Any]:
    """Keep the highest-count pins from a rematched index. Not a live ranking."""
    if isinstance(keep, bool) or not isinstance(keep, int) or keep < 1:
        raise MemoryLayerError("invalid_keep", "keep must be >= 1")
    verified = verify_trait_lab_catalog_pins(index)
    rows = [_pin_public_row(row) for row in verified["pins"]]
    if not rows:
        raise MemoryLayerError("missing_pin", "retain requires at least one pin")
    rows.sort(key=lambda row: (-int(row["count"]), str(row["catalog_sha256"])))
    selected = rows[:keep]
    body = _pin_index_body(selected)
    refuse_trait_lab_catalog_pin_live(body)
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        **body,
        "pin_index_sha256": hashlib.sha256(encoded).hexdigest(),
        "kept": len(selected),
        "keep": keep,
        "live_verified": False,
    }


_TRAIT_LAB_CATALOG_PIN_BIND_KIND = "trait-lab-seed-pack-catalog-pin-bind"
_TRAIT_LAB_CATALOG_PIN_BIND_INDEX_KIND = "trait-lab-seed-pack-catalog-pin-bind-index"
TRAIT_LAB_CATALOG_PIN_BIND_OPS: tuple[str, ...] = (
    "rematch",
    "is_bound",
    "list_unbound_packs",
    "list_bound_packs",
    "count_bound_packs",
    "count_unbound_packs",
    "list_bound_pin_ids",
    "list_unbound_pin_ids",
    "count_bound_pins",
    "has_unbound_pin",
    "report",
    "export",
    "verify",
    "refuse_live",
    "pin_retained",
    "pin_xor",
    "pin_merged",
    "catalog_from_pin",
    "public_row",
    "digest",
    "etag",
    "page",
    "best_bound",
    "import_retained_index",
    "binds_by_agent",
)


def _store_pack_ids(store: MemoryStore) -> set[str]:
    return {str(row["pack_sha256"]) for row in _collect_trait_lab_seed_pack_rows(store)}


def _bind_public_row(row: dict[str, Any]) -> dict[str, Any]:
    sha = _require_catalog_sha(row.get("catalog_sha256"))
    raw_bound = row.get("bound_ids")
    raw_unbound = row.get("unbound_ids")
    if not isinstance(raw_bound, list) or not isinstance(raw_unbound, list):
        raise MemoryLayerError("invalid_bind", "bind row requires bound_ids and unbound_ids")
    bound_ids = [str(item).strip().lower() for item in raw_bound]
    unbound_ids = [str(item).strip().lower() for item in raw_unbound]
    if any(len(item) != 64 or any(ch not in "0123456789abcdef" for ch in item) for item in bound_ids + unbound_ids):
        raise MemoryLayerError("invalid_bind", "bind ids must be pack hashes")
    count = row.get("count")
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        raise MemoryLayerError("invalid_bind", "bind row requires count")
    bound_count = int(row.get("bound_count", len(bound_ids)))
    unbound_count = int(row.get("unbound_count", len(unbound_ids)))
    if bound_count != len(bound_ids) or unbound_count != len(unbound_ids):
        raise MemoryLayerError("invalid_bind", "bind counts must match id lists")
    return {
        "kind": _TRAIT_LAB_CATALOG_PIN_BIND_KIND,
        "catalog_sha256": sha,
        "fact_id": _catalog_pin_fact_id(sha),
        "bound": bool(row.get("bound")) and unbound_count == 0 and bound_count > 0,
        "count": count,
        "bound_ids": bound_ids,
        "unbound_ids": unbound_ids,
        "bound_count": bound_count,
        "unbound_count": unbound_count,
        "live_verified": False,
    }


def _bind_report_from_pin(store: MemoryStore, pin: dict[str, Any]) -> dict[str, Any]:
    store_ids = _store_pack_ids(store)
    pin_ids = [str(item) for item in pin["ids"]]
    bound_ids = [sha for sha in pin_ids if sha in store_ids]
    unbound_ids = [sha for sha in pin_ids if sha not in store_ids]
    return _bind_public_row(
        {
            "catalog_sha256": pin["catalog_sha256"],
            "fact_id": pin["fact_id"],
            "bound": len(unbound_ids) == 0 and len(bound_ids) > 0,
            "count": pin["count"],
            "bound_ids": bound_ids,
            "unbound_ids": unbound_ids,
            "bound_count": len(bound_ids),
            "unbound_count": len(unbound_ids),
        }
    )


def _collect_trait_lab_catalog_pin_binds(store: MemoryStore) -> list[dict[str, Any]]:
    return [_bind_report_from_pin(store, pin) for pin in _collect_trait_lab_catalog_pins(store)]


def _bind_index_body(rows: list[dict[str, Any]]) -> dict[str, Any]:
    public = [_bind_public_row(row) for row in rows]
    return {
        "kind": _TRAIT_LAB_CATALOG_PIN_BIND_INDEX_KIND,
        "binds": public,
        "count": len(public),
        "live_verified": False,
    }


def rematch_trait_lab_catalog_pin_against_store(
    store: MemoryStore,
    catalog_sha256: str,
) -> dict[str, Any]:
    """B01 — rematch one pin's pack hashes against cataloged store packs."""
    pin = get_trait_lab_catalog_pin(store, catalog_sha256)
    return _bind_report_from_pin(store, pin)


def trait_lab_catalog_pin_is_bound(store: MemoryStore, catalog_sha256: str) -> bool:
    """B02 — true when every pinned pack hash exists in the store."""
    return bool(rematch_trait_lab_catalog_pin_against_store(store, catalog_sha256)["bound"])


def list_unbound_packs_for_pin(store: MemoryStore, catalog_sha256: str) -> list[str]:
    """B03 — pack hashes listed by the pin but missing from the store."""
    return list(rematch_trait_lab_catalog_pin_against_store(store, catalog_sha256)["unbound_ids"])


def list_bound_packs_for_pin(store: MemoryStore, catalog_sha256: str) -> list[str]:
    """B04 — pack hashes listed by the pin and present in the store."""
    return list(rematch_trait_lab_catalog_pin_against_store(store, catalog_sha256)["bound_ids"])


def count_bound_packs_for_pin(store: MemoryStore, catalog_sha256: str) -> int:
    """B05 — how many pinned pack hashes exist in the store."""
    return int(rematch_trait_lab_catalog_pin_against_store(store, catalog_sha256)["bound_count"])


def count_unbound_packs_for_pin(store: MemoryStore, catalog_sha256: str) -> int:
    """B06 — how many pinned pack hashes are missing from the store."""
    return int(rematch_trait_lab_catalog_pin_against_store(store, catalog_sha256)["unbound_count"])


def list_bound_trait_lab_catalog_pin_ids(store: MemoryStore, *, limit: int = 50) -> list[str]:
    """B07 — catalog_sha256 values of fully bound pins, sorted."""
    limit = _require_catalog_limit(limit)
    return [row["catalog_sha256"] for row in _collect_trait_lab_catalog_pin_binds(store) if row["bound"]][:limit]


def list_unbound_trait_lab_catalog_pin_ids(store: MemoryStore, *, limit: int = 50) -> list[str]:
    """B08 — catalog_sha256 values of pins with at least one missing pack."""
    limit = _require_catalog_limit(limit)
    return [row["catalog_sha256"] for row in _collect_trait_lab_catalog_pin_binds(store) if not row["bound"]][:limit]


def count_bound_trait_lab_catalog_pins(store: MemoryStore) -> int:
    """B09 — number of fully bound pins."""
    return len(list_bound_trait_lab_catalog_pin_ids(store, limit=200))


def has_unbound_trait_lab_catalog_pin(store: MemoryStore) -> bool:
    """B10 — true when any pin is missing at least one store pack."""
    return any(not row["bound"] for row in _collect_trait_lab_catalog_pin_binds(store))


def report_trait_lab_catalog_pin_bind(store: MemoryStore, catalog_sha256: str) -> dict[str, Any]:
    """B11 — public bind report for one pin. Not a live ranking."""
    return rematch_trait_lab_catalog_pin_against_store(store, catalog_sha256)


def export_trait_lab_catalog_pin_binds(store: MemoryStore, *, limit: int = 50) -> dict[str, Any]:
    """B12 — portable bind-index snapshot. Not a live ranking."""
    limit = _require_catalog_limit(limit)
    rows = _collect_trait_lab_catalog_pin_binds(store)[:limit]
    body = _bind_index_body(rows)
    refuse_trait_lab_catalog_pin_bind_live(body)
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        **body,
        "bind_index_sha256": hashlib.sha256(encoded).hexdigest(),
        "exported_at": _utc(),
    }


def verify_trait_lab_catalog_pin_binds(index: Any) -> dict[str, Any]:
    """B13 — rematch bind_index_sha256 over the stable bind-index body."""
    if not isinstance(index, dict):
        raise MemoryLayerError("invalid_bind", "bind index must be an object")
    if index.get("kind") != _TRAIT_LAB_CATALOG_PIN_BIND_INDEX_KIND:
        raise MemoryLayerError("invalid_bind", "kind must be trait-lab-seed-pack-catalog-pin-bind-index")
    refuse_trait_lab_catalog_pin_bind_live(index)
    if not isinstance(index.get("binds"), list):
        raise MemoryLayerError("invalid_bind", "binds must be a list")
    sha = str(index.get("bind_index_sha256") or "").strip().lower()
    if len(sha) != 64 or any(ch not in "0123456789abcdef" for ch in sha):
        raise MemoryLayerError("missing_bind_hash", "verify requires bind_index_sha256")
    public = [_bind_public_row(row) for row in index["binds"] if isinstance(row, dict)]
    if len(public) != len(index["binds"]):
        raise MemoryLayerError("invalid_bind", "every bind row must be an object")
    body = _bind_index_body(public)
    got = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    if got != sha:
        raise MemoryLayerError("bind_mismatch", f"bind index hashed {got[:12]} not {sha[:12]}")
    return {**body, "matched": True, "bind_index_sha256": sha, "live_verified": False}


def refuse_trait_lab_catalog_pin_bind_live(payload: Any) -> None:
    """B14 — bind payloads may not claim LIVE VERIFIED."""
    if isinstance(payload, dict) and payload.get("live_verified") is True:
        raise MemoryLayerError("live_claim", "catalog pin bind may not claim LIVE VERIFIED")


def pin_retained_trait_lab_seed_pack_catalog(
    store: MemoryStore,
    catalog: Any,
    *,
    agent_id: str,
    task_id: str,
    keep: int = 1,
) -> dict[str, Any]:
    """B15 — retain the highest-count packs, then pin. Does not apply runs."""
    retained = retain_trait_lab_seed_pack_catalog(catalog, keep=keep)
    return pin_trait_lab_seed_pack_catalog(store, retained, agent_id=agent_id, task_id=task_id)


def pin_xor_trait_lab_seed_pack_catalogs(
    store: MemoryStore,
    catalog_a: Any,
    catalog_b: Any,
    *,
    agent_id: str,
    task_id: str,
) -> dict[str, Any]:
    """B16 — xor two rematched catalogs, then pin. Does not apply runs."""
    composed = symmetric_diff_trait_lab_seed_pack_catalogs(catalog_a, catalog_b)
    if int(composed["count"]) < 1:
        raise MemoryLayerError("missing_pack", "xor pin requires at least one pack")
    return pin_trait_lab_seed_pack_catalog(store, composed, agent_id=agent_id, task_id=task_id)


def pin_merged_trait_lab_seed_pack_catalogs(
    store: MemoryStore,
    catalog_a: Any,
    catalog_b: Any,
    *,
    agent_id: str,
    task_id: str,
) -> dict[str, Any]:
    """B17 — merge two rematched catalogs, then pin. Does not apply runs."""
    composed = merge_trait_lab_seed_pack_catalogs(catalog_a, catalog_b)
    if int(composed["count"]) < 1:
        raise MemoryLayerError("missing_pack", "merge pin requires at least one pack")
    return pin_trait_lab_seed_pack_catalog(store, composed, agent_id=agent_id, task_id=task_id)


def catalog_from_trait_lab_catalog_pin(store: MemoryStore, catalog_sha256: str) -> dict[str, Any]:
    """B18 — rebuild a rematched catalog from a fully bound pin."""
    report = rematch_trait_lab_catalog_pin_against_store(store, catalog_sha256)
    if not report["bound"]:
        raise MemoryLayerError("unbound_pin", f"pin {report['catalog_sha256'][:12]} is not bound")
    rows = [get_trait_lab_seed_pack(store, sha) for sha in report["bound_ids"]]
    body = _catalog_export_body(rows)
    refuse_trait_lab_catalog_live(body)
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    sha = hashlib.sha256(encoded).hexdigest()
    if sha != report["catalog_sha256"]:
        raise MemoryLayerError("catalog_mismatch", f"rebuilt catalog {sha[:12]} not {report['catalog_sha256'][:12]}")
    return {**body, "catalog_sha256": sha, "matched": True, "live_verified": False}


def public_trait_lab_catalog_pin_bind_row(row: dict[str, Any]) -> dict[str, Any]:
    """B19 — stable bind selector row without agent/task fields."""
    if not isinstance(row, dict) or not row.get("catalog_sha256"):
        raise MemoryLayerError("invalid_bind", "public row requires a bind")
    return _bind_public_row(row)


def trait_lab_catalog_pin_binds_digest(store: MemoryStore) -> str:
    """B20 — SHA-256 over the stable public bind-index body."""
    return str(export_trait_lab_catalog_pin_binds(store)["bind_index_sha256"])


def trait_lab_catalog_pin_binds_etag(store: MemoryStore) -> str:
    """B21 — short digest for bind-index identity."""
    return trait_lab_catalog_pin_binds_digest(store)[:16]


def page_trait_lab_catalog_pin_binds(
    store: MemoryStore,
    *,
    offset: int = 0,
    limit: int = 50,
) -> dict[str, Any]:
    """B22 — deterministic bind-report page. Not a live ranking."""
    limit = _require_catalog_limit(limit)
    start = _require_catalog_offset(offset)
    rows = _collect_trait_lab_catalog_pin_binds(store)
    selected = rows[start : start + limit]
    return {
        **_bind_index_body(selected),
        "count": len(rows),
        "offset": start,
        "limit": limit,
        "live_verified": False,
    }


def best_bound_trait_lab_catalog_pin(store: MemoryStore) -> dict[str, Any]:
    """B23 — highest-count fully bound pin; hash breaks ties. Not a live ranking."""
    rows = [row for row in _collect_trait_lab_catalog_pin_binds(store) if row["bound"]]
    if not rows:
        raise MemoryLayerError("missing_pin", "no bound catalog pin")
    rows.sort(key=lambda row: (-int(row["count"]), str(row["catalog_sha256"])))
    return {**rows[0], "live_verified": False}


def import_retained_trait_lab_catalog_pin_index(
    store: MemoryStore,
    index: Any,
    *,
    agent_id: str,
    task_id: str,
    keep: int = 1,
) -> dict[str, Any]:
    """B24 — retain the highest-count pins, then import pin facts. No pack/run writes."""
    retained = retain_trait_lab_catalog_pin_index(index, keep=keep)
    return import_trait_lab_catalog_pins(store, retained, agent_id=agent_id, task_id=task_id)


def list_trait_lab_catalog_pin_binds_by_agent(
    store: MemoryStore,
    agent_id: str,
    *,
    limit: int = 50,
) -> dict[str, Any]:
    """B25 — bind reports for pins written by one agent."""
    limit = _require_catalog_limit(limit)
    wanted = str(agent_id or "").strip()
    if not wanted:
        raise MemoryLayerError("missing_agent", "bind by agent requires agent_id")
    pins = [pin for pin in _collect_trait_lab_catalog_pins(store) if pin.get("agent_id") == wanted]
    if not pins:
        raise MemoryLayerError("missing_agent", f"no pinned catalog for agent {wanted}")
    rows = [_bind_report_from_pin(store, pin) for pin in pins][:limit]
    return {**_bind_index_body(rows), "agent_id": wanted, "live_verified": False}


TRAIT_LAB_CATALOG_PIN_BIND_LANE_OPS: tuple[str, ...] = (
    "list_ids",
    "count_binds",
    "by_task",
    "by_count_floor",
    "by_count_ceiling",
    "by_count_band",
    "bound_only",
    "unbound_only",
    "count_unbound_pins",
    "has_bound_pin",
    "rematch_index",
    "diff_indexes",
    "merge",
    "intersect",
    "subtract",
    "xor",
    "retain",
    "drop_unbound",
    "catalogs_from_bound",
    "has_pack",
    "ids_for_pack",
    "get_by_fact_id",
    "ids_for_agent",
    "count_for_pack",
    "export_bound",
)


def _bind_conflict_key(row: dict[str, Any]) -> tuple[int, frozenset[str], frozenset[str], bool]:
    return (
        int(row["count"]),
        frozenset(str(item) for item in row["bound_ids"]),
        frozenset(str(item) for item in row["unbound_ids"]),
        bool(row["bound"]),
    )


def _public_bind_map(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    for row in rows:
        public = _bind_public_row(row)
        sha = str(public["catalog_sha256"])
        prior = found.get(sha)
        if prior is not None:
            if _bind_conflict_key(prior) != _bind_conflict_key(public):
                raise MemoryLayerError("bind_conflict", f"bind {sha[:12]} disagrees")
            continue
        found[sha] = public
    return found


def _signed_bind_index(rows: list[dict[str, Any]], **extra: Any) -> dict[str, Any]:
    body = _bind_index_body(rows)
    refuse_trait_lab_catalog_pin_bind_live(body)
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        **body,
        "bind_index_sha256": hashlib.sha256(encoded).hexdigest(),
        "live_verified": False,
        **extra,
    }


def list_trait_lab_catalog_pin_bind_ids(store: MemoryStore, *, limit: int = 50) -> list[str]:
    """D01 — catalog_sha256 values of bind reports, sorted."""
    limit = _require_catalog_limit(limit)
    return [row["catalog_sha256"] for row in _collect_trait_lab_catalog_pin_binds(store)][:limit]


def count_trait_lab_catalog_pin_binds(store: MemoryStore) -> int:
    """D02 — number of bind reports (one per pin)."""
    return len(_collect_trait_lab_catalog_pin_binds(store))


def list_trait_lab_catalog_pin_binds_by_task(
    store: MemoryStore,
    task_id: str,
    *,
    limit: int = 50,
) -> dict[str, Any]:
    """D03 — bind reports for pins written by one task."""
    limit = _require_catalog_limit(limit)
    wanted = str(task_id or "").strip()
    if not wanted:
        raise MemoryLayerError("missing_task", "bind by task requires task_id")
    pins = [pin for pin in _collect_trait_lab_catalog_pins(store) if pin.get("task_id") == wanted]
    if not pins:
        raise MemoryLayerError("missing_task", f"no pinned catalog for task {wanted}")
    rows = [_bind_report_from_pin(store, pin) for pin in pins][:limit]
    return {**_bind_index_body(rows), "task_id": wanted, "live_verified": False}


def catalog_pin_binds_by_count_floor(
    store: MemoryStore,
    floor: int,
    *,
    limit: int = 50,
) -> dict[str, Any]:
    """D04 — binds whose pin pack count is at or above floor."""
    limit = _require_catalog_limit(limit)
    low = _xp_bound(floor, code="invalid_floor", label="floor")
    rows = [row for row in _collect_trait_lab_catalog_pin_binds(store) if int(row["count"]) >= low]
    if not rows:
        raise MemoryLayerError("missing_floor", f"no catalog pin bind with count >= {low}")
    return {**_bind_index_body(rows[:limit]), "floor": low, "live_verified": False}


def catalog_pin_binds_by_count_ceiling(
    store: MemoryStore,
    ceiling: int,
    *,
    limit: int = 50,
) -> dict[str, Any]:
    """D05 — binds whose pin pack count is at or below ceiling."""
    limit = _require_catalog_limit(limit)
    high = _xp_bound(ceiling, code="invalid_ceiling", label="ceiling")
    rows = [row for row in _collect_trait_lab_catalog_pin_binds(store) if int(row["count"]) <= high]
    if not rows:
        raise MemoryLayerError("missing_ceiling", f"no catalog pin bind with count <= {high}")
    return {**_bind_index_body(rows[:limit]), "ceiling": high, "live_verified": False}


def catalog_pin_binds_by_count_band(
    store: MemoryStore,
    floor: int,
    ceiling: int,
    *,
    limit: int = 50,
) -> dict[str, Any]:
    """D06 — binds whose pin pack count is inside [floor, ceiling]."""
    limit = _require_catalog_limit(limit)
    low = _xp_bound(floor, code="invalid_floor", label="floor")
    high = _xp_bound(ceiling, code="invalid_ceiling", label="ceiling")
    if low > high:
        raise MemoryLayerError("invalid_band", "floor must be <= ceiling")
    rows = [
        row for row in _collect_trait_lab_catalog_pin_binds(store) if low <= int(row["count"]) <= high
    ]
    if not rows:
        raise MemoryLayerError("missing_band", f"no catalog pin bind with count {low}-{high}")
    return {**_bind_index_body(rows[:limit]), "floor": low, "ceiling": high, "live_verified": False}


def list_bound_only_trait_lab_catalog_pin_binds(store: MemoryStore, *, limit: int = 50) -> dict[str, Any]:
    """D07 — bind reports that are fully bound."""
    limit = _require_catalog_limit(limit)
    rows = [row for row in _collect_trait_lab_catalog_pin_binds(store) if row["bound"]]
    if not rows:
        raise MemoryLayerError("missing_pin", "no bound catalog pin")
    return {**_bind_index_body(rows[:limit]), "live_verified": False}


def list_unbound_only_trait_lab_catalog_pin_binds(store: MemoryStore, *, limit: int = 50) -> dict[str, Any]:
    """D08 — bind reports that are missing at least one store pack."""
    limit = _require_catalog_limit(limit)
    rows = [row for row in _collect_trait_lab_catalog_pin_binds(store) if not row["bound"]]
    if not rows:
        raise MemoryLayerError("missing_pin", "no unbound catalog pin")
    return {**_bind_index_body(rows[:limit]), "live_verified": False}


def count_unbound_trait_lab_catalog_pins(store: MemoryStore) -> int:
    """D09 — number of pins that are not fully bound."""
    return len(list_unbound_trait_lab_catalog_pin_ids(store, limit=200))


def has_bound_trait_lab_catalog_pin(store: MemoryStore) -> bool:
    """D10 — true when at least one pin is fully bound."""
    return any(row["bound"] for row in _collect_trait_lab_catalog_pin_binds(store))


def rematch_trait_lab_catalog_pin_bind_index(store: MemoryStore, index: Any) -> dict[str, Any]:
    """D11 — rematch each bind row's pin against the current store."""
    verified = verify_trait_lab_catalog_pin_binds(index)
    rows = [
        rematch_trait_lab_catalog_pin_against_store(store, str(row["catalog_sha256"]))
        for row in verified["binds"]
    ]
    return _signed_bind_index(rows, rematched=True, source=verified["bind_index_sha256"])


def diff_trait_lab_catalog_pin_bind_indexes(index_a: Any, index_b: Any) -> dict[str, Any]:
    """D12 — compare two rematched bind-index snapshots."""
    left = verify_trait_lab_catalog_pin_binds(index_a)
    right = verify_trait_lab_catalog_pin_binds(index_b)
    if left["bind_index_sha256"] == right["bind_index_sha256"]:
        raise MemoryLayerError("same_bind_index", "diff requires two different bind-index hashes")
    ids_a = [row["catalog_sha256"] for row in left["binds"]]
    ids_b = [row["catalog_sha256"] for row in right["binds"]]
    set_a = set(ids_a)
    set_b = set(ids_b)
    return {
        "kind": _TRAIT_LAB_CATALOG_PIN_BIND_INDEX_KIND,
        "only_a": [sha for sha in ids_a if sha not in set_b],
        "only_b": [sha for sha in ids_b if sha not in set_a],
        "shared": [sha for sha in ids_a if sha in set_b],
        "count_delta": int(left["count"]) - int(right["count"]),
        "live_verified": False,
    }


def _compose_trait_lab_catalog_pin_bind_indexes(
    index_a: Any,
    index_b: Any,
    *,
    mode: str,
) -> dict[str, Any]:
    if mode not in {"merge", "intersect", "subtract", "xor"}:
        raise MemoryLayerError("invalid_compose", f"unknown compose mode {mode}")
    left = verify_trait_lab_catalog_pin_binds(index_a)
    right = verify_trait_lab_catalog_pin_binds(index_b)
    if left["bind_index_sha256"] == right["bind_index_sha256"]:
        raise MemoryLayerError("same_bind_index", f"{mode} requires two different bind-index hashes")
    map_a = _public_bind_map(left["binds"])
    map_b = _public_bind_map(right["binds"])
    for sha, row in map_b.items():
        prior = map_a.get(sha)
        if prior is not None and _bind_conflict_key(prior) != _bind_conflict_key(row):
            raise MemoryLayerError("bind_conflict", f"bind {sha[:12]} disagrees across indexes")
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
    rows = sorted(selected.values(), key=lambda row: str(row["catalog_sha256"]))
    return _signed_bind_index(rows, mode=mode, a=left["bind_index_sha256"], b=right["bind_index_sha256"])


def merge_trait_lab_catalog_pin_bind_indexes(index_a: Any, index_b: Any) -> dict[str, Any]:
    """D13 — union two rematched bind-index snapshots. Not a live ranking."""
    return _compose_trait_lab_catalog_pin_bind_indexes(index_a, index_b, mode="merge")


def intersect_trait_lab_catalog_pin_bind_indexes(index_a: Any, index_b: Any) -> dict[str, Any]:
    """D14 — shared binds of two rematched bind indexes. Not a live ranking."""
    return _compose_trait_lab_catalog_pin_bind_indexes(index_a, index_b, mode="intersect")


def subtract_trait_lab_catalog_pin_bind_indexes(index_a: Any, index_b: Any) -> dict[str, Any]:
    """D15 — binds in A that are not in B. Not a live ranking."""
    return _compose_trait_lab_catalog_pin_bind_indexes(index_a, index_b, mode="subtract")


def symmetric_diff_trait_lab_catalog_pin_bind_indexes(index_a: Any, index_b: Any) -> dict[str, Any]:
    """D16 — binds in exactly one rematched bind index. Not a live ranking."""
    return _compose_trait_lab_catalog_pin_bind_indexes(index_a, index_b, mode="xor")


def retain_trait_lab_catalog_pin_binds(index: Any, *, keep: int = 1) -> dict[str, Any]:
    """D17 — keep the highest-count bind rows. Not a live ranking."""
    if isinstance(keep, bool) or not isinstance(keep, int) or keep < 1:
        raise MemoryLayerError("invalid_keep", "keep must be >= 1")
    verified = verify_trait_lab_catalog_pin_binds(index)
    rows = [_bind_public_row(row) for row in verified["binds"]]
    if not rows:
        raise MemoryLayerError("missing_bind", "retain requires at least one bind")
    rows.sort(key=lambda row: (-int(row["count"]), str(row["catalog_sha256"])))
    selected = rows[:keep]
    return _signed_bind_index(selected, kept=len(selected), keep=keep)


def drop_unbound_trait_lab_catalog_pins(store: MemoryStore) -> dict[str, Any]:
    """D18 — unpin facts that are not fully bound. Pack facts and runs stay."""
    unbound = list_unbound_trait_lab_catalog_pin_ids(store, limit=200)
    if not unbound:
        raise MemoryLayerError("missing_pin", "no unbound catalog pin to drop")
    dropped: list[str] = []
    for sha in unbound:
        unpin_trait_lab_catalog_pin(store, sha)
        dropped.append(sha)
    return {
        "dropped": True,
        "count": len(dropped),
        "ids": dropped,
        "live_verified": False,
    }


def catalogs_from_bound_trait_lab_catalog_pins(store: MemoryStore, *, limit: int = 50) -> dict[str, Any]:
    """D19 — rebuild rematched catalogs for every fully bound pin."""
    limit = _require_catalog_limit(limit)
    ids = list_bound_trait_lab_catalog_pin_ids(store, limit=limit)
    if not ids:
        raise MemoryLayerError("missing_pin", "no bound catalog pin")
    catalogs = [catalog_from_trait_lab_catalog_pin(store, sha) for sha in ids]
    return {
        "kind": _TRAIT_LAB_CATALOG_KIND,
        "catalogs": catalogs,
        "count": len(catalogs),
        "live_verified": False,
    }


def catalog_pin_bind_has_pack(store: MemoryStore, pack_sha256: str) -> bool:
    """D20 — true when any bound bind lists the pack hash."""
    sha = _require_pack_sha(pack_sha256)
    return any(sha in row["bound_ids"] for row in _collect_trait_lab_catalog_pin_binds(store))


def list_trait_lab_catalog_pin_bind_ids_for_pack(
    store: MemoryStore,
    pack_sha256: str,
    *,
    limit: int = 50,
) -> list[str]:
    """D21 — catalog_sha256 values whose bound_ids include one pack."""
    sha = _require_pack_sha(pack_sha256)
    limit = _require_catalog_limit(limit)
    ids = [
        row["catalog_sha256"]
        for row in _collect_trait_lab_catalog_pin_binds(store)
        if sha in row["bound_ids"]
    ]
    return ids[:limit]


def get_trait_lab_catalog_pin_bind_by_fact_id(store: MemoryStore, fact_id: str) -> dict[str, Any]:
    """D22 — rematch one pin by fact_id."""
    pin = get_trait_lab_catalog_pin_by_fact_id(store, fact_id)
    return _bind_report_from_pin(store, pin)


def list_trait_lab_catalog_pin_bind_ids_for_agent(
    store: MemoryStore,
    agent_id: str,
    *,
    limit: int = 50,
) -> list[str]:
    """D23 — catalog_sha256 values of bind reports written by one agent."""
    return [
        row["catalog_sha256"]
        for row in list_trait_lab_catalog_pin_binds_by_agent(store, agent_id, limit=limit)["binds"]
    ]


def count_trait_lab_catalog_pin_binds_for_pack(store: MemoryStore, pack_sha256: str) -> int:
    """D24 — how many bound binds include one pack hash."""
    return len(list_trait_lab_catalog_pin_bind_ids_for_pack(store, pack_sha256, limit=200))


def export_bound_trait_lab_catalog_pin_binds(store: MemoryStore, *, limit: int = 50) -> dict[str, Any]:
    """D25 — portable bind-index of fully bound pins only."""
    limit = _require_catalog_limit(limit)
    rows = [row for row in _collect_trait_lab_catalog_pin_binds(store) if row["bound"]][:limit]
    if not rows:
        raise MemoryLayerError("missing_pin", "no bound catalog pin")
    exported = _signed_bind_index(rows)
    return {**exported, "exported_at": _utc()}
