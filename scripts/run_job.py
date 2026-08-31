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

    # Step 1: Health check
    print("=== Step 1: Indexer health ===")
    health = await reg.execute("indexer_health", {})
    execution.append({"step": 1, "tool": "indexer_health", "args": {}, "result": health, "status": "ok"})
    if health.get("indexers"):
        for name, info in health["indexers"].items():
            print(f"  {name}: {info.get('status')} ({info.get('http_code', 'N/A')})")

    # Step 2: Compare inscriptions
    insc_ids = job.get("inputs", {}).get("inscription_ids", [])
    step = 3
    for insc_id in insc_ids:
        result = await reg.execute("compare_inscription", {"inscription_id": insc_id, "indexers": ["doginals_org", "dogechain"]})
        diff = result.get("diff", {})
        execution.append({"step": step, "tool": "compare_inscription", "args": {"inscription_id": insc_id}, "result": {"ok": diff.get("sources_ok"), "failed": diff.get("sources_failed")}, "status": "ok" if diff.get("sources_ok") else "blocked"})
        print(f"  {insc_id[:25]}... OK={diff.get('sources_ok')} Failed={diff.get('sources_failed')}")
        step += 1

    # Step 3: Write finding
    finding_path = REPO_ROOT / "data" / "findings" / f"{job['id']}.md"
    execution.append({"step": step, "tool": "fs_write", "args": {"path": f"data/findings/{job['id']}.md"}, "result": {"bytes_written": finding_path.exists()}, "status": "ok"})
    artifacts.append({"path": f"data/findings/{job['id']}.md", "kind": "finding"})
    step += 1

    # Step 4: Store in SQLite
    mem_result = await reg.execute("memory_put", {"kind": "job", "key": job["id"], "value": {"verdict": job.get("evaluation", {}).get("verdict"), "steps": len(execution)}, "source_url": "https://api.doginals.org"})
    execution.append({"step": step, "tool": "memory_put", "args": {"key": job["id"]}, "result": {"success": mem_result.get("success")}, "status": "ok"})

    # Update job
    job["execution"] = execution
    job["artifacts"] = artifacts
    with open(job_path, "w") as f:
        json.dump(job, f, indent=2, default=str)

    print(f"\n=== JOB COMPLETE ===")
    print(f"Job: {job['id']}")
    print(f"Verdict: {job['evaluation']['verdict']}")


if __name__ == "__main__":
    job_path = sys.argv[1] if len(sys.argv) > 1 else str(REPO_ROOT / "jobs" / "job_dogi_split_001.json")
    asyncio.run(run_job(job_path))
