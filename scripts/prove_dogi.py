#!/usr/bin/env python3
"""Proof script for the Doginals indexer-split thesis.

Runs the agent against live public APIs to prove that different indexers
report different data for the same Doginals inscriptions.

Usage:
    python scripts/prove_dogi.py
    python scripts/prove_dogi.py --inscription <inscription_id>
"""

import argparse
import asyncio
import json
import sys
import os
from pathlib import Path

# Add repo root to path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

os.chdir(str(REPO_ROOT))


async def main():
    from core.foundation.bootstrap import bootstrap
    from core.runtime.loop import AgentLoop

    parser = argparse.ArgumentParser(description="Prove Doginals indexer-split thesis")
    parser.add_argument("--inscription", type=str, default=None, help="Specific inscription ID to test")
    parser.add_argument("--model", type=str, default=None, help="Ollama model to use")
    args = parser.parse_args()

    if args.model:
        os.environ["OLLAMA_MODEL"] = args.model

    print("=" * 60)
    print("DOGINALS INDEXER-SPLIT PROOF")
    print("=" * 60)

    ctx = bootstrap(project_root=str(REPO_ROOT), with_provider=True, with_tools=True)

    if not ctx.provider:
        print("ERROR: No provider available. Install Ollama or set API key.")
        sys.exit(1)

    print(f"Provider: {ctx.provider.__class__.__name__}")
    print(f"Tools: {len(ctx.tool_registry.list_tools())}")
    print(f"Tools: {[t.name for t in ctx.tool_registry.list_tools()]}")
    print()

    if args.inscription:
        goal = (
            f"Research the Doginals inscription '{args.inscription}'.\n"
            f"1) Run compare_inscription with indexers: ordinalsdotcom, wonky, doginals_org.\n"
            f"2) Report what each indexer returns.\n"
            f"3) Write findings to data/findings/dogi_indexer_split.md\n"
            f"4) Store the record in memory with kind=finding."
        )
    else:
        goal = (
            "Verify the Doginals indexer-split case.\n"
            "1) Load the fixture data/fixtures/dogi_canonical.json.\n"
            "2) For each inscription id in the fixture, run compare_inscription across available indexers.\n"
            "3) Parse any DRC-20 JSON found.\n"
            "4) Write data/findings/dogi_indexer_split.md with:\n"
            "   - what each source returned\n"
            "   - whether the original 21M deploy is visible on each source\n"
            "   - whether the later 2.1B deploy is visible\n"
            "   - explicit statement of what this does and does not prove\n"
            "5) Store the same record in SQLite with memory_put."
        )

    print(f"GOAL:\n{goal}\n")
    print("-" * 60)

    loop = AgentLoop(
        provider=ctx.provider,
        tool_registry=ctx.tool_registry,
        max_iterations=20,
    )

    result = await loop.run(goal)

    print("\n" + "=" * 60)
    print("RESULT")
    print("=" * 60)
    print(json.dumps(result, indent=2, default=str))

    findings_path = REPO_ROOT / "data" / "findings" / "dogi_indexer_split.md"
    if findings_path.exists():
        print(f"\nFINDING WRITTEN: {findings_path}")
        print("-" * 40)
        print(findings_path.read_text()[:2000])
    else:
        print("\nWARNING: No finding file written.")

    db_path = REPO_ROOT / "data" / "thinkbox.sqlite"
    if db_path.exists():
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT COUNT(*) as cnt FROM research_records").fetchone()
        print(f"\nSQLITE RECORDS: {rows['cnt']}")
        conn.close()


if __name__ == "__main__":
    asyncio.run(main())
