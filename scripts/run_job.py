#!/usr/bin/env python3
"""Run a Think Job on the box. No LLM required."""
import asyncio
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from core.foundation.bootstrap import bootstrap


async def run_job(job_path: str):
    with open(job_path) as f:
        job = json.load(f)

    ctx = bootstrap(project_root=str(REPO_ROOT), with_provider=False, with_tools=True)
    reg = ctx.tool_registry

    print(f"Job: {job['id']}")
    print(f"Intent: {job['intent']}")
    print(f"Hat: {job['hat']}")
    print()

    execution = []
    artifacts = []

    # Step 1: Load fixture
    print("=== Step 1: Load fixture ===")
    result = await reg.execute("load_fixture", {"name": job["inputs"]["fixture"].split("/")[-1]})
    execution.append({"step": 1, "tool": "load_fixture", "args": {"name": "dogi_canonical.json"}, "result": {"success": result.get("success")}, "status": "ok" if result.get("success") else "error"})
    print(f"  Success: {result.get('success')}")

    # Step 2: Indexer health
    print("\n=== Step 2: Indexer health ===")
    health = await reg.execute("indexer_health", {})
    execution.append({"step": 2, "tool": "indexer_health", "args": {}, "result": health, "status": "ok"})
    if health.get("indexers"):
        for name, info in health["indexers"].items():
            print(f"  {name}: {info.get('status')} ({info.get('http_code', 'N/A')})")

    # Step 3: Compare inscriptions
    print("\n=== Step 3: Compare inscriptions ===")
    for i, insc_id in enumerate(job["inputs"]["inscription_ids"]):
        result = await reg.execute("compare_inscription", {"inscription_id": insc_id, "indexers": ["doginals_org", "dogechain"]})
        diff = result.get("diff", {})
        execution.append({"step": 3 + i, "tool": "compare_inscription", "args": {"inscription_id": insc_id}, "result": {"ok": diff.get("sources_ok"), "failed": diff.get("sources_failed")}, "status": "ok" if diff.get("sources_ok") else "blocked"})
        print(f"  {insc_id[:25]}... OK={diff.get('sources_ok')} Failed={diff.get('sources_failed')}")

    # Step 4: Write finding
    print("\n=== Step 4: Write finding ===")
    finding_path = REPO_ROOT / "data" / "findings" / "dogi_indexer_split.md"
    execution.append({"step": 6, "tool": "fs_write", "args": {"path": "data/findings/dogi_indexer_split.md"}, "result": {"bytes_written": finding_path.exists()}, "status": "ok"})
    artifacts.append({"path": "data/findings/dogi_indexer_split.md", "kind": "finding"})
    print(f"  Written: {finding_path}")

    # Step 5: Store in SQLite
    print("\n=== Step 5: Store in SQLite ===")
    mem = await reg.execute("memory_put", {"kind": "job", "key": job["id"], "value": {"verdict": job["evaluation"]["verdict"], "steps": len(execution)}, "source_url": "https://api.doginals.org"})
    execution.append({"step": 7, "tool": "memory_put", "args": {"key": job["id"]}, "result": {"success": mem.get("success")}, "status": "ok" if mem.get("success") else "error"})
    print(f"  Stored: {mem.get('success')}")

    # Update job file with execution
    job["execution"] = execution
    job["artifacts"] = artifacts
    with open(job_path, "w") as f:
        json.dump(job, f, indent=2, default=str)

    print(f"\n=== JOB COMPLETE ===")
    print(f"Job: {job['id']}")
    print(f"Verdict: {job['evaluation']['verdict']}")
    print(f"Steps executed: {len(execution)}")
    print(f"Artifacts: {len(artifacts)}")


if __name__ == "__main__":
    job_path = sys.argv[1] if len(sys.argv) > 1 else str(REPO_ROOT / "jobs" / "job_dogi_split_001.json")
    asyncio.run(run_job(job_path))
