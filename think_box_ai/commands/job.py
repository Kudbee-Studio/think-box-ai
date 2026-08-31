"""Job commands for Think Box CLI."""

from __future__ import annotations

import json
from pathlib import Path

from ..ui.colors import colorize, bold, dim, colorize_verdict
from ..ui.table import render_table, render_key_value
from ..utils.output import output_json, is_json_mode, is_quiet_mode, is_dry_run
from ..utils.format import format_verdict, format_supply

JOBS_DIR = Path(__file__).resolve().parent.parent.parent / "jobs"


def _load_job(job_id: str) -> tuple[dict, str] | None:
    """Load a job from any state directory."""
    for state in ["queue", "active", "done", "blocked"]:
        job_file = JOBS_DIR / state / f"{job_id}.json"
        if job_file.exists():
            return json.loads(job_file.read_text()), state
    return None


def _find_all_jobs() -> list[tuple[dict, str]]:
    """Find all jobs across all states."""
    jobs = []
    for state in ["queue", "active", "done", "blocked"]:
        state_dir = JOBS_DIR / state
        if not state_dir.is_dir():
            continue
        for job_file in sorted(state_dir.glob("job_*.json")):
            job = json.loads(job_file.read_text())
            jobs.append((job, state))
    return jobs


def list_jobs(state_filter: str | None = None) -> None:
    """List all jobs."""
    jobs = _find_all_jobs()

    if state_filter:
        jobs = [(j, s) for j, s in jobs if s == state_filter]

    if is_json_mode():
        output_json([{"id": j["id"], "hat": j["hat"], "state": s, "verdict": j.get("evaluation", {}).get("verdict")} for j, s in jobs])
        return

    if not jobs:
        print(dim("  No jobs found."))
        return

    headers = ["ID", "HAT", "STATE", "VERDICT"]
    rows = []
    for job, state in jobs:
        verdict = job.get("evaluation", {}).get("verdict", "—")
        if is_json_mode():
            v = verdict
        else:
            v = format_verdict(verdict)
        rows.append([job["id"], job["hat"], state, v])

    print(render_table(headers, rows))


def show_job(job_id: str) -> None:
    """Show details for a specific job."""
    result = _load_job(job_id)
    if not result:
        print(colorize(f"Job not found: {job_id}", ""))
        return

    job, state = result

    if is_json_mode():
        output_json(job)
        return

    print(bold(f"\n{job['id']}"))
    print(dim("  " + "─" * 40))
    print(f"  Hat: {job['hat']}")
    print(f"  State: {state}")
    print(f"  Verdict: {format_verdict(job.get('evaluation', {}).get('verdict', '—'))}")
    print(f"  Intent: {job.get('intent', '—')}")

    if job.get("inputs"):
        print(f"\n  {bold('Inputs:')}")
        print(render_key_value(job["inputs"], indent=4))

    if job.get("execution"):
        print(f"\n  {bold('Execution:')}")
        for step in job["execution"]:
            status = step.get("status", "?")
            tool = step.get("tool", "?")
            v = format_verdict(status) if status in ["succeeded", "failed", "unproven", "blocked"] else status
            print(f"    Step {step.get('step')}: {tool} → {v}")

    if job.get("artifacts"):
        print(f"\n  {bold('Artifacts:')}")
        for a in job["artifacts"]:
            print(f"    {a.get('path', '—')}")

    if job.get("cost"):
        print(f"\n  {bold('Receipts:')}")
        print(render_key_value(job["cost"], indent=4))


def show_queue() -> None:
    """Show queue contents by state."""
    for state in ["queue", "active", "done", "blocked"]:
        state_dir = JOBS_DIR / state
        if not state_dir.is_dir():
            continue
        jobs = list(state_dir.glob("job_*.json"))
        print(f"\n{bold(state.upper())} ({len(jobs)}):")
        for jf in sorted(jf for jf in jobs):
            job = json.loads(jf.read_text())
            verdict = job.get("evaluation", {}).get("verdict", "—")
            print(f"  {job['id']} [{job['hat']}] → {format_verdict(verdict)}")


def submit_job(template_name: str, args: list[str] | None = None) -> None:
    """Submit a job from template."""
    tmpl_path = JOBS_DIR / "templates" / f"template_{template_name}.json"
    if not tmpl_path.exists():
        print(colorize(f"Template not found: template_{template_name}.json", ""))
        print("Available:")
        for t in sorted((JOBS_DIR / "templates").glob("template_*.json")):
            print(f"  {t.stem.replace('template_', '')}")
        return

    job = json.loads(tmpl_path.read_text())
    job_id = f"job_{template_name}_001"
    job["id"] = job_id

    if args:
        for arg in args:
            if "=" in arg:
                k, v = arg.split("=", 1)
                job["inputs"][k] = v

    if is_dry_run():
        print(f"[dry-run] Would submit: {job_id}")
        print(json.dumps(job, indent=2))
        return

    queue_path = JOBS_DIR / "queue" / f"{job_id}.json"
    queue_path.write_text(json.dumps(job, indent=2))
    print(f"Submitted: {job_id}")
    print(f"Location: {queue_path}")


def submit_wizard() -> None:
    """Interactive job submission wizard."""
    from ..ui.prompt import select, prompt, confirm
    from ..ui.colors import bold

    templates = sorted((JOBS_DIR / "templates").glob("template_*.json"))
    if not templates:
        print("No templates available.")
        return

    names = [t.stem.replace("template_", "") for t in templates]
    print(bold("\nJob Submission Wizard"))
    idx = select("Choose a template:", names)
    if idx < 0:
        return

    tmpl_path = templates[idx]
    job = json.loads(tmpl_path.read_text())
    job_id = prompt("Job ID", f"job_{names[idx]}_001")
    job["id"] = job_id

    # Fill inputs
    if job.get("inputs"):
        print(bold("\nFill inputs (press Enter to skip):"))
        for k, v in job["inputs"].items():
            if isinstance(v, list):
                continue
            val = prompt(f"  {k}", str(v) if v else "")
            if val:
                job["inputs"][k] = val

    if is_dry_run():
        print(f"\n[dry-run] Would submit: {job_id}")
        print(json.dumps(job, indent=2))
        return

    if confirm(f"Submit {job_id}?", default=True):
        queue_path = JOBS_DIR / "queue" / f"{job_id}.json"
        queue_path.write_text(json.dumps(job, indent=2))
        print(f"Submitted: {job_id}")
    else:
        print("Cancelled.")


def diff_jobs(id1: str, id2: str) -> None:
    """Compare two jobs."""
    r1 = _load_job(id1)
    r2 = _load_job(id2)
    if not r1 or not r2:
        print("One or both jobs not found.")
        return

    job1, state1 = r1
    job2, state2 = r2

    print(bold(f"\n{id1} vs {id2}"))
    print(f"  Hat: {job1['hat']} vs {job2['hat']}")
    print(f"  State: {state1} vs {state2}")
    print(f"  Verdict: {format_verdict(job1.get('evaluation',{}).get('verdict','—'))} vs {format_verdict(job2.get('evaluation',{}).get('verdict','—'))}")
