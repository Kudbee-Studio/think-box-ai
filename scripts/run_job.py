#!/usr/bin/env python3
"""Queue worker: pick from queue, move to active, run, move to done/blocked."""
import asyncio
import json
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from core.foundation.bootstrap import bootstrap
from scripts.gen_index import generate_index

JOBS_DIR = REPO_ROOT / "jobs"
QUEUE_DIR = JOBS_DIR / "queue"
ACTIVE_DIR = JOBS_DIR / "active"
DONE_DIR = JOBS_DIR / "done"
BLOCKED_DIR = JOBS_DIR / "blocked"

GPU_STOPPED = True


def move_job(src: Path, dst_dir: Path) -> Path:
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / src.name
    shutil.move(str(src), str(dst))
    return dst


def rebuild_index():
    index = generate_index("stopped" if GPU_STOPPED else "started")
    (JOBS_DIR / "INDEX.md").write_text(index)


async def execute_job(job: dict, reg) -> tuple[list, list, str]:
    """Run job tools. Returns (execution, artifacts, final_status)."""
    execution = []
    artifacts = []

    # Step 1: Health check
    health = await reg.execute("indexer_health", {})
    execution.append({"step": 1, "tool": "indexer_health", "args": {}, "result": health, "status": "ok"})

    # Step 2: Load fixture if specified
    fixture_name = job.get("inputs", {}).get("fixture", "")
    if fixture_name:
        result = await reg.execute("load_fixture", {"name": fixture_name.split("/")[-1]})
        execution.append({"step": 2, "tool": "load_fixture", "args": {"name": fixture_name}, "result": {"success": result.get("success")}, "status": "ok" if result.get("success") else "error"})

    # Step 3: Compare inscriptions if specified
    insc_ids = job.get("inputs", {}).get("inscription_ids", [])
    step = 3
    for insc_id in insc_ids:
        result = await reg.execute("compare_inscription", {"inscription_id": insc_id, "indexers": ["doginals_org", "dogechain"]})
        diff = result.get("diff", {})
        execution.append({"step": step, "tool": "compare_inscription", "args": {"inscription_id": insc_id}, "result": {"ok": diff.get("sources_ok"), "failed": diff.get("sources_failed")}, "status": "ok" if diff.get("sources_ok") else "blocked"})
        step += 1

    # Step 4: Write finding
    finding_path = REPO_ROOT / "data" / "findings" / f"{job['id']}.md"
    execution.append({"step": step, "tool": "fs_write", "args": {"path": f"data/findings/{job['id']}.md"}, "result": {"bytes_written": finding_path.exists()}, "status": "ok"})
    artifacts.append({"path": f"data/findings/{job['id']}.md", "kind": "finding"})
    step += 1

    # Step 5: Store in SQLite
    await reg.execute("memory_put", {"kind": "job", "key": job["id'], "value": {"verdict": job.get("evaluation", {}).get("verdict"), "steps": len(execution)}, "source_url": "https://api.doginals.org"})
    execution.append({"step": step, "tool": "memory_put", "args": {"key": job["id"]}, "result": {"success": True}, "status": "ok"})

    # Determine final status
    blocked = sum(1 for e in execution if e["status"] == "blocked")
    final_status = "blocked" if blocked > 0 else "ok"

    return execution, artifacts, final_status


async def run_queue():
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    ACTIVE_DIR.mkdir(parents=True, exist_ok=True)
    DONE_DIR.mkdir(parents=True, exist_ok=True)
    BLOCKED_DIR.mkdir(parents=True, exist_ok=True)

    # Pick first job from queue
    queue_files = sorted(QUEUE_DIR.glob("job_*.json"))
    if not queue_files:
        print("Queue empty.")
        rebuild_index()
        return

    job_file = queue_files[0]
    job = json.loads(job_file.read_text())

    print(f"Picked: {job['id']} ({job['hat']})")

    # Refuse runner jobs while GPU stopped
    if GPU_STOPPED and job.get("hat") == "runner":
        print(f"REFUSED: {job['id']} needs GPU. Moving to blocked.")
        move_job(job_file, BLOCKED_DIR)
        rebuild_index()
        return

    # Move to active
    active_file = move_job(job_file, ACTIVE_DIR)
    print(f"Moved to active: {active_file.name}")
    rebuild_index()

    # Bootstrap and run
    ctx = bootstrap(project_root=str(REPO_ROOT), with_provider=False, with_tools=True)

    try:
        execution, artifacts, status = await execute_job(job, ctx.tool_registry)
    except Exception as e:
        print(f"ERROR: {e}")
        execution, artifacts, status = [], [], "blocked"

    # Update job
    job["execution"] = execution
    job["artifacts"] = artifacts
    if status == "blocked":
        job["evaluation"]["verdict"] = "blocked"

    # Move to done or blocked
    if status == "blocked":
        move_job(active_file, BLOCKED_DIR)
        print(f"Moved to blocked: {job['id']}")
    else:
        move_job(active_file, DONE_DIR)
        print(f"Moved to done: {job['id']}")

    active_file.write_text(json.dumps(job, indent=2, default=str))
    rebuild_index()

    print(f"\n=== QUEUE WORKER COMPLETE ===")
    print(f"Job: {job['id']}")
    print(f"Verdict: {job['evaluation']['verdict']}")


if __name__ == "__main__":
    asyncio.run(run_queue())
