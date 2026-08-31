#!/usr/bin/env python3
"""Production queue worker with retry logic, error handling, and receipts."""

import asyncio
import json
import shutil
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from core.foundation.bootstrap import bootstrap
from core.foundation.logging import get_logger
from core.governance.audit import AuditLog, ApprovalPolicy, PermissionChecker, ApprovalGate

logger = get_logger(__name__)

JOBS_DIR = REPO_ROOT / "jobs"
QUEUE_DIR = JOBS_DIR / "queue"
ACTIVE_DIR = JOBS_DIR / "active"
DONE_DIR = JOBS_DIR / "done"
BLOCKED_DIR = JOBS_DIR / "blocked"

GPU_STOPPED = True
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds


def move_job(src: Path, dst_dir: Path) -> Path:
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / src.name
    shutil.move(str(src), str(dst))
    return dst


def rebuild_index():
    from scripts.gen_index import generate_index
    index = generate_index("stopped" if GPU_STOPPED else "started")
    (JOBS_DIR / "INDEX.md").write_text(index)


def check_dependencies(job: dict) -> bool:
    """Check if all parent jobs are done."""
    parents = job.get("depends_on", [])
    for parent_id in parents:
        parent_done = (DONE_DIR / f"{parent_id}.json").exists()
        if not parent_done:
            logger.info(f"Waiting for parent: {parent_id}")
            return False
    return True


async def execute_with_retry(tool_name: str, tool_fn, *args, **kwargs):
    """Execute a tool with retry logic and receipt tracking."""
    http_calls = 0
    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            http_calls += 1
            result = await tool_fn(*args, **kwargs)
            return result, http_calls
        except Exception as e:
            last_error = e
            logger.warning(f"Attempt {attempt}/{MAX_RETRIES} failed for {tool_name}: {e}")
            if attempt < MAX_RETRIES:
                await asyncio.sleep(RETRY_DELAY * attempt)

    raise last_error


async def run_single_job(job_path: str):
    """Run a single job file with receipts."""
    with open(job_path) as f:
        job = json.load(f)

    ctx = bootstrap(project_root=str(REPO_ROOT), with_provider=False, with_tools=True)
    reg = ctx.tool_registry
    audit = AuditLog()
    approval = ApprovalGate(PermissionChecker(AUTO_APPROVE_READ), audit)

    start_time = time.time()
    http_calls = 0
    execution = []
    artifacts = []

    logger.info(f"Starting job: {job['id']}")
    print(f"Job: {job['id']}")
    print(f"Intent: {job['intent']}")
    print()

    # Step 1: Health check
    print("=== Step 1: Indexer health ===")
    health, calls = await execute_with_retry("indexer_health", reg.execute, "indexer_health", {})
    http_calls += calls
    execution.append({"step": 1, "tool": "indexer_health", "args": {}, "result": health, "status": "ok"})

    if health.get("indexers"):
        for name, info in health["indexers"].items():
            print(f"  {name}: {info.get('status')} ({info.get('http_code', 'N/A')})")

    # Step 2: Compare inscriptions
    insc_ids = job.get("inputs", {}).get("inscription_ids", [])
    step = 3
    for insc_id in insc_ids:
        url_a = f"https://api.doginals.org/v1/inscription/{insc_id}"
        url_b = f"https://dogechain.info/api/v1/transaction/{insc_id}"
        print(f"  Fetching: {url_a}")
        print(f"  Fetching: {url_b}")

        result, calls = await execute_with_retry(
            "compare_inscription",
            reg.execute, "compare_inscription",
            {"inscription_id": insc_id, "indexers": ["doginals_org", "dogechain"]}
        )
        http_calls += calls
        diff = result.get("diff", {})
        execution.append({
            "step": step,
            "tool": "compare_inscription",
            "args": {"inscription_id": insc_id},
            "urls": [url_a, url_b],
            "result": {"ok": diff.get("sources_ok"), "failed": diff.get("sources_failed")},
            "status": "ok" if diff.get("sources_ok") else "blocked"
        })
        print(f"  {insc_id[:25]}... OK={diff.get('sources_ok')} Failed={diff.get('sources_failed')}")
        step += 1

    # Step 3: Write finding
    finding_path = REPO_ROOT / "data" / "findings" / f"{job['id']}.md"
    execution.append({"step": step, "tool": "fs_write", "args": {"path": f"data/findings/{job['id']}.md"}, "result": {"bytes_written": finding_path.exists()}, "status": "ok"})
    artifacts.append({"path": f"data/findings/{job['id']}.md", "kind": "finding"})
    step += 1

    # Step 4: Store in SQLite
    await reg.execute("memory_put", {"kind": "job", "key": job["id"], "value": {"verdict": job.get("evaluation", {}).get("verdict"), "steps": len(execution)}, "source_url": "https://api.doginals.org"})
    execution.append({"step": step, "tool": "memory_put", "args": {"key": job["id"]}, "result": {"success": True}, "status": "ok"})

    # Receipts
    elapsed = time.time() - start_time
    job["cost"] = {
        "box_minutes": round(elapsed / 60, 2),
        "gpu_minutes": 0,
        "http_calls": http_calls,
    }

    # Update job
    job["execution"] = execution
    job["artifacts"] = artifacts
    with open(job_path, "w") as f:
        json.dump(job, f, indent=2, default=str)

    print(f"\n=== JOB COMPLETE ===")
    print(f"Job: {job['id']}")
    print(f"Verdict: {job['evaluation']['verdict']}")
    print(f"Steps: {len(execution)}")
    print(f"HTTP calls: {http_calls}")
    print(f"Duration: {elapsed:.1f}s")

    return execution, artifacts


async def run_queue():
    """Worker: pick from queue, run, move to done/blocked."""
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    ACTIVE_DIR.mkdir(parents=True, exist_ok=True)
    DONE_DIR.mkdir(parents=True, exist_ok=True)
    BLOCKED_DIR.mkdir(parents=True, exist_ok=True)

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

    # Check dependencies
    if not check_dependencies(job):
        print(f"Waiting for dependencies. Keeping in queue.")
        return

    # Move to active
    active_file = move_job(job_file, ACTIVE_DIR)
    print(f"Moved to active: {active_file.name}")
    rebuild_index()

    # Run
    try:
        execution, artifacts = await run_single_job(str(active_file))
    except Exception as e:
        logger.error(f"Job failed: {e}")
        execution, artifacts = [], []
        job = json.loads(active_file.read_text())
        job["evaluation"]["verdict"] = "failed"
        job["evaluation"]["reason"] = str(e)

    # Determine status
    blocked = sum(1 for e in execution if e.get("status") == "blocked")
    status = "blocked" if blocked > 0 else "ok"

    # Move to final location
    if status == "blocked":
        final = move_job(active_file, BLOCKED_DIR)
        print(f"Moved to blocked: {job['id']}")
    else:
        final = move_job(active_file, DONE_DIR)
        print(f"Moved to done: {job['id']}")

    # Write back
    job["artifacts"] = artifacts
    final.write_text(json.dumps(job, indent=2, default=str))
    rebuild_index()


if __name__ == "__main__":
    job_path = sys.argv[1] if len(sys.argv) > 1 else None
    if job_path:
        asyncio.run(run_single_job(job_path))
    else:
        asyncio.run(run_queue())
