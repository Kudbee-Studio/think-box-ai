"""Job management commands."""

from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from ..ui.colors import bold, cyan, dim, green, red, yellow
from ..ui.table import render_table
from ..utils.output import is_json_mode, output_json

JOBS_DIR = Path("data/jobs")
QUEUE_FILE = Path("data/queue.jsonl")


def _ensure_dirs() -> None:
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not QUEUE_FILE.exists():
        QUEUE_FILE.write_text("")


def _load_jobs() -> list[dict]:
    _ensure_dirs()
    jobs = []
    for f in sorted(JOBS_DIR.glob("*.json")):
        try:
            jobs.append(json.loads(f.read_text()))
        except (json.JSONDecodeError, OSError):
            continue
    return jobs


def _save_job(job: dict) -> None:
    _ensure_dirs()
    path = JOBS_DIR / f"{job['id']}.json"
    path.write_text(json.dumps(job, indent=2, default=str))


def handle_job_command(args) -> None:
    sub = args.job_command

    if sub == "list":
        _job_list(args)
    elif sub == "show":
        _job_show(args)
    elif sub == "create":
        _job_create(args)
    elif sub == "submit":
        _job_submit(args)
    elif sub == "run":
        _job_run(args)
    elif sub == "cancel":
        _job_cancel(args)
    elif sub == "retry":
        _job_retry(args)
    elif sub == "diff":
        _job_diff(args)
    else:
        print("Usage: thinkbox job {list|show|create|submit|run|cancel|retry|diff}")


def _job_list(args) -> None:
    jobs = _load_jobs()
    if args.state:
        jobs = [j for j in jobs if j.get("state") == args.state]
    jobs = jobs[: args.limit]

    if is_json_mode():
        output_json(jobs)
        return

    if not jobs:
        print(dim("  No jobs found."))
        return

    headers = ["ID", "Intent", "Hat", "State", "Verdict", "Created"]
    rows = []
    for j in jobs:
        state_color = {
            "queue": cyan,
            "active": yellow,
            "done": green,
            "blocked": red,
        }.get(j.get("state", ""), str)
        rows.append([
            j["id"][:12],
            j.get("intent", "")[:40],
            j.get("hat", "researcher"),
            state_color(j.get("state", "unknown")),
            j.get("verdict", "-"),
            j.get("created_at", "")[:10],
        ])

    print(bold(f"\n  Jobs ({len(jobs)}):"))
    print(render_table(headers, rows))


def _job_show(args) -> None:
    jobs = _load_jobs()
    job = next((j for j in jobs if j["id"].startswith(args.job_id)), None)

    if is_json_mode():
        output_json(job or {"error": "not found"})
        return

    if not job:
        print(red(f"  Job not found: {args.job_id}"))
        return

    print(bold(f"\n  Job: {job['id']}"))
    print(dim("  " + "─" * 50))
    for key, value in job.items():
        if key == "results":
            print(f"  {bold(key)}:")
            for r in value[:5]:
                print(f"    - {r}")
        else:
            print(f"  {bold(key):15} {value}")


def _job_create(args) -> None:
    _ensure_dirs()
    job = {
        "id": f"job_{uuid.uuid4().hex[:12]}",
        "intent": args.intent,
        "hat": args.hat,
        "state": "queue",
        "verdict": None,
        "results": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    if args.file:
        try:
            data = json.loads(Path(args.file).read_text())
            job.update(data)
        except (json.JSONDecodeError, OSError) as e:
            print(red(f"  Error reading file: {e}"))
            return

    _save_job(job)

    if is_json_mode():
        output_json(job)
        return

    print(green(f"  Created job: {job['id']}"))
    print(f"  Intent: {job['intent']}")
    print(f"  Hat: {job['hat']}")


def _job_submit(args) -> None:
    _ensure_dirs()
    templates_dir = Path("data/templates")
    template_file = templates_dir / f"{args.template}.json"

    if not template_file.exists():
        print(red(f"  Template not found: {args.template}"))
        print(dim(f"  Available templates: {list(templates_dir.glob('*.json'))}"))
        return

    try:
        template = json.loads(template_file.read_text())
    except (json.JSONDecodeError, OSError) as e:
        print(red(f"  Error reading template: {e}"))
        return

    job = {
        "id": f"job_{uuid.uuid4().hex[:12]}",
        "intent": template.get("intent", args.template),
        "hat": template.get("hat", "researcher"),
        "state": "queue",
        "verdict": None,
        "results": [],
        "template": args.template,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    _save_job(job)

    if is_json_mode():
        output_json(job)
        return

    print(green(f"  Submitted job from template: {args.template}"))
    print(f"  Job ID: {job['id']}")


def _job_run(args) -> None:
    jobs = _load_jobs()
    queued = [j for j in jobs if j.get("state") == "queue"]

    if is_json_mode():
        output_json({"queued": len(queued), "message": "Queue worker started"})
        return

    if not queued:
        print(dim("  No jobs in queue."))
        return

    print(bold(f"\n  Running queue worker ({len(queued)} jobs)..."))
    for job in queued:
        if args.dry_run:
            print(cyan(f"  [DRY RUN] Would run: {job['id']}"))
        else:
            job["state"] = "active"
            job["updated_at"] = datetime.now(timezone.utc).isoformat()
            _save_job(job)
            print(green(f"  Started: {job['id']}"))


def _job_cancel(args) -> None:
    jobs = _load_jobs()
    job = next((j for j in jobs if j["id"].startswith(args.job_id)), None)

    if not job:
        print(red(f"  Job not found: {args.job_id}"))
        return

    job["state"] = "cancelled"
    job["updated_at"] = datetime.now(timezone.utc).isoformat()
    _save_job(job)

    if is_json_mode():
        output_json(job)
        return

    print(yellow(f"  Cancelled: {job['id']}"))


def _job_retry(args) -> None:
    jobs = _load_jobs()
    job = next((j for j in jobs if j["id"].startswith(args.job_id)), None)

    if not job:
        print(red(f"  Job not found: {args.job_id}"))
        return

    job["state"] = "queue"
    job["verdict"] = None
    job["updated_at"] = datetime.now(timezone.utc).isoformat()
    _save_job(job)

    if is_json_mode():
        output_json(job)
        return

    print(green(f"  Retrying: {job['id']}"))


def _job_diff(args) -> None:
    jobs = _load_jobs()
    job1 = next((j for j in jobs if j["id"].startswith(args.id1)), None)
    job2 = next((j for j in jobs if j["id"].startswith(args.id2)), None)

    if not job1 or not job2:
        print(red("  One or both jobs not found"))
        return

    if is_json_mode():
        output_json({"job1": job1, "job2": job2})
        return

    print(bold(f"\n  Diff: {job1['id'][:12]} vs {job2['id'][:12]}"))
    print(dim("  " + "─" * 50))

    all_keys = set(job1.keys()) | set(job2.keys())
    for key in sorted(all_keys):
        v1 = job1.get(key, "<missing>")
        v2 = job2.get(key, "<missing>")
        if v1 != v2:
            print(f"  {red('-')} {key}: {v1}")
            print(f"  {green('+')} {key}: {v2}")
        else:
            print(f"  {dim('=')} {key}: {v1}")
