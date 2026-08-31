"""Job commands for Think Box CLI."""

from __future__ import annotations

import json
from pathlib import Path

JOBS_DIR = Path(__file__).resolve().parent.parent.parent / "jobs"


def list_jobs() -> None:
    """List all jobs from INDEX.md."""
    index_path = JOBS_DIR / "INDEX.md"
    if not index_path.exists():
        print("No jobs found.")
        return
    print(index_path.read_text())


def show_job(job_id: str) -> None:
    """Show details for a specific job."""
    for state in ["queue", "active", "done", "blocked"]:
        job_file = JOBS_DIR / state / f"{job_id}.json"
        if job_file.exists():
            job = json.loads(job_file.read_text())
            print(f"ID: {job['id']}")
            print(f"Hat: {job['hat']}")
            print(f"Intent: {job['intent']}")
            print(f"State: {state}")
            print(f"Verdict: {job.get('evaluation', {}).get('verdict', '—')}")
            print(f"Inputs: {json.dumps(job.get('inputs', {}), indent=2)}")
            print(f"Plan: {json.dumps(job.get('plan', []), indent=2)}")
            print(f"Execution steps: {len(job.get('execution', []))}")
            print(f"Artifacts: {json.dumps(job.get('artifacts', []), indent=2)}")
            if job.get("execution"):
                print("\nExecution:")
                for step in job["execution"]:
                    print(f"  Step {step.get('step')}: {step.get('tool')} → {step.get('status')}")
            return
    print(f"Job not found: {job_id}")


def show_queue() -> None:
    """Show queue contents by state."""
    for state in ["queue", "active", "done", "blocked"]:
        state_dir = JOBS_DIR / state
        if not state_dir.is_dir():
            continue
        jobs = list(state_dir.glob("job_*.json"))
        print(f"\n{state.upper()} ({len(jobs)}):")
        for jf in sorted(jobs):
            job = json.loads(jf.read_text())
            verdict = job.get("evaluation", {}).get("verdict", "—")
            print(f"  {job['id']} [{job['hat']}] → {verdict}")


def submit_job(template_name: str, inputs: dict | None = None) -> None:
    """Copy a template to queue and fill inputs."""
    tmpl_path = JOBS_DIR / "templates" / f"template_{template_name}.json"
    if not tmpl_path.exists():
        print(f"Template not found: template_{template_name}.json")
        print("Available templates:")
        for t in sorted((JOBS_DIR / "templates").glob("template_*.json")):
            print(f"  {t.stem.replace('template_', '')}")
        return

    job = json.loads(tmpl_path.read_text())
    job_id = f"job_{template_name}_001"
    job["id"] = job_id

    if inputs:
        job["inputs"].update(inputs)

    queue_path = JOBS_DIR / "queue" / f"{job_id}.json"
    queue_path.write_text(json.dumps(job, indent=2))
    print(f"Submitted: {job_id}")
    print(f"Location: {queue_path}")
    print("Run 'thinkbox job run' to execute.")
