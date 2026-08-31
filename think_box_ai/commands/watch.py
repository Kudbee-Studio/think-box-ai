"""Watch command for Think Box CLI."""

from __future__ import annotations

import sys
import time
from pathlib import Path

from ..ui.colors import colorize, bold, dim, colorize_verdict
from ..ui.table import render_table

JOBS_DIR = Path(__file__).resolve().parent.parent.parent / "jobs"


def watch(interval: int = 5) -> None:
    """Live monitoring of job states."""
    print(bold("Watching jobs..."))
    print(dim(f"  Refresh: {interval}s  (Ctrl+C to exit)\n"))

    try:
        while True:
            jobs = []
            for state in ["queue", "active", "done", "blocked"]:
                state_dir = JOBS_DIR / state
                if not state_dir.is_dir():
                    continue
                for jf in sorted(state_dir.glob("job_*.json")):
                    import json
                    job = json.loads(jf.read_text())
                    verdict = job.get("evaluation", {}).get("verdict", "—")
                    jobs.append([job["id"], job["hat"], state, colorize_verdict(verdict)])

            # Clear and redraw
            sys.stdout.write("\033[2J\033[H")
            print(bold(f"Think Job Watch — {time.strftime('%H:%M:%S')}"))
            print(dim(f"  {len(jobs)} jobs\n"))
            if jobs:
                print(render_table(["ID", "HAT", "STATE", "VERDICT"], jobs))
            else:
                print(dim("  No jobs."))
            time.sleep(interval)
    except KeyboardInterrupt:
        print(dim("\nStopped."))
