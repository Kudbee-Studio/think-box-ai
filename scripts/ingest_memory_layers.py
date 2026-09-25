#!/usr/bin/env python3
"""Ingest markdown into the four memory layers. Local SQLite. Not live."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from core.memory.store import MemoryStore
from thinkbox.memory_layers import ingest_markdown
DEFAULT_DB = REPO / "data" / "thinkboxmd" / "db" / "memory_layers.db"


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest markdown into four memory layers")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--session-id", default="tb_sess_memory_layers")
    parser.add_argument("--task-id", default="pr203-memory-layers")
    parser.add_argument("--agent-id", default="operator")
    args = parser.parse_args()
    args.db.parent.mkdir(parents=True, exist_ok=True)
    store = MemoryStore(args.db)
    try:
        summary = ingest_markdown(
            REPO,
            store,
            session_id=args.session_id,
            task_id=args.task_id,
            agent_id=args.agent_id,
        )
    finally:
        store.close()
    print(
        f"markdown_files={summary['markdown_files']} "
        f"bytes={summary['markdown_bytes']} live_verified={summary['live_verified']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
