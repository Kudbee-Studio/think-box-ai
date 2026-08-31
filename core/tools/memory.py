"""Memory tools for THINK BOX AI — SQLite-backed research memory."""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.tools.registry import tool

_DB_PATH: Path | None = None
_lock = threading.Lock()


def init_memory_db(db_path: Path) -> None:
    global _DB_PATH
    _DB_PATH = db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS research_records (
                id TEXT PRIMARY KEY,
                ts TEXT NOT NULL,
                kind TEXT NOT NULL,
                key TEXT NOT NULL,
                value_json TEXT NOT NULL,
                source_url TEXT DEFAULT ''
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_research_kind ON research_records(kind)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_research_key ON research_records(key)")


def _conn() -> sqlite3.Connection:
    if _DB_PATH is None:
        raise RuntimeError("Memory DB not initialized. Call init_memory_db first.")
    conn = sqlite3.connect(str(_DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


@tool(
    name="memory_put",
    description="Store a research record in SQLite. kind: run|finding|artifact|observation. Returns the record id.",
    permission="read_write",
    input_schema={"type": "object", "properties": {"kind": {"type": "string"}, "key": {"type": "string"}, "value": {"type": "object"}, "source_url": {"type": "string"}}, "required": ["kind", "key", "value"]},
)
async def memory_put(args: dict[str, Any], context: dict[str, Any] | None = None) -> dict[str, Any]:
    kind = args.get("kind", "")
    key = args.get("key", "")
    value = args.get("value", {})
    source_url = args.get("source_url", "")
    if not kind or not key:
        return {"success": False, "error": "Missing 'kind' or 'key' argument"}

    record_id = str(uuid.uuid4())[:12]
    ts = datetime.now(timezone.utc).isoformat()

    with _lock:
        try:
            conn = _conn()
            conn.execute(
                "INSERT INTO research_records (id, ts, kind, key, value_json, source_url) VALUES (?, ?, ?, ?, ?, ?)",
                (record_id, ts, kind, key, json.dumps(value, default=str), source_url),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            return {"success": False, "error": str(e)}

    return {"success": True, "id": record_id, "kind": kind, "key": key}


@tool(
    name="memory_get",
    description="Retrieve a research record by id or key. Returns the full record including value.",
    permission="read_only",
    input_schema={"type": "object", "properties": {"id": {"type": "string"}, "key": {"type": "string"}}, "required": []},
)
async def memory_get(args: dict[str, Any], context: dict[str, Any] | None = None) -> dict[str, Any]:
    record_id = args.get("id", "")
    key = args.get("key", "")

    try:
        conn = _conn()
        if record_id:
            row = conn.execute("SELECT * FROM research_records WHERE id = ?", (record_id,)).fetchone()
        elif key:
            row = conn.execute("SELECT * FROM research_records WHERE key = ? ORDER BY ts DESC LIMIT 1", (key,)).fetchone()
        else:
            conn.close()
            return {"success": False, "error": "Provide 'id' or 'key'"}
        conn.close()

        if not row:
            return {"success": False, "error": "Record not found"}

        return {
            "success": True,
            "record": {
                "id": row["id"],
                "ts": row["ts"],
                "kind": row["kind"],
                "key": row["key"],
                "value": json.loads(row["value_json"]),
                "source_url": row["source_url"],
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@tool(
    name="memory_search",
    description="Search research records by kind or key prefix. Returns matching records (limit 50).",
    permission="read_only",
    input_schema={"type": "object", "properties": {"kind": {"type": "string"}, "key_prefix": {"type": "string"}, "limit": {"type": "integer"}}, "required": []},
)
async def memory_search(args: dict[str, Any], context: dict[str, Any] | None = None) -> dict[str, Any]:
    kind = args.get("kind", "")
    key_prefix = args.get("key_prefix", "")
    limit = min(int(args.get("limit", 20)), 100)

    try:
        conn = _conn()
        query = "SELECT * FROM research_records WHERE 1=1"
        params: list[Any] = []
        if kind:
            query += " AND kind = ?"
            params.append(kind)
        if key_prefix:
            query += " AND key LIKE ?"
            params.append(f"{key_prefix}%")
        query += " ORDER BY ts DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(query, params).fetchall()
        conn.close()

        records = []
        for row in rows:
            records.append({
                "id": row["id"],
                "ts": row["ts"],
                "kind": row["kind"],
                "key": row["key"],
                "value": json.loads(row["value_json"]),
                "source_url": row["source_url"],
            })
        return {"success": True, "records": records, "count": len(records)}
    except Exception as e:
        return {"success": False, "error": str(e)}
