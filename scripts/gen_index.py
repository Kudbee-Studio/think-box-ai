#!/usr/bin/env python3
"""Generate jobs/INDEX.md from job JSON files."""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
JOBS_DIR = REPO_ROOT / "jobs"
INDEX_PATH = JOBS_DIR / "INDEX.md"

STATES = ["queue", "active", "done", "blocked"]


def load_job(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def get_artifact(job: dict) -> str:
    artifacts = job.get("artifacts", [])
    if artifacts:
        return artifacts[0].get("path", "—")
    return "—"


def generate_index(gpu_state: str = "stopped") -> str:
    rows = []
    for state in STATES:
        state_dir = JOBS_DIR / state
        if not state_dir.is_dir():
            continue
        for job_file in sorted(state_dir.glob("job_*.json")):
            job = load_job(job_file)
            if not job:
                continue
            rows.append({
                "id": job.get("id", "—"),
                "hat": job.get("hat", "—"),
                "state": state,
                "verdict": job.get("evaluation", {}).get("verdict", "—"),
                "artifact": get_artifact(job),
            })

    lines = [
        "# Think Job index",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        f"GPU: {gpu_state}",
        "",
        "| id | hat | state | verdict | artifact |",
        "|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(f"| {r['id']} | {r['hat']} | {r['state']} | {r['verdict']} | {r['artifact']} |")

    return "\n".join(lines) + "\n"


def main():
    gpu_state = sys.argv[1] if len(sys.argv) > 1 else "stopped"
    index = generate_index(gpu_state)
    INDEX_PATH.write_text(index)
    print(index)


if __name__ == "__main__":
    main()
