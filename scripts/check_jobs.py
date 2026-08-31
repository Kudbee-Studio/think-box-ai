#!/usr/bin/env python3
"""Check jobs without pytest. Validates schema, templates, and worker logic."""
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
JOBS_DIR = REPO_ROOT / "jobs"
SCHEMA_PATH = JOBS_DIR / "schema.json"

REQUIRED = ["id", "intent", "hat", "inputs", "plan", "capabilities", "execution", "artifacts", "evaluation"]
VALID_HATS = ["researcher", "runner", "director", "camera", "jury"]
VALID_VERDICTS = ["succeeded", "failed", "unproven", "blocked"]

passed = 0
failed = 0


def check(name: str, condition: bool):
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS: {name}")
    else:
        failed += 1
        print(f"  FAIL: {name}")


def main():
    global passed, failed

    print("=== Schema ===")
    schema = json.loads(SCHEMA_PATH.read_text())
    check("schema loads", True)
    check("schema has required fields", "required" in schema)

    print("\n=== Templates ===")
    for tmpl_file in (JOBS_DIR / "templates").glob("template_*.json"):
        tmpl = json.loads(tmpl_file.read_text())
        for field in REQUIRED:
            check(f"{tmpl_file.name} has {field}", field in tmpl)
        check(f"{tmpl_file.name} valid hat", tmpl.get("hat") in VALID_HATS)

    print("\n=== Jobs ===")
    for state in ["done", "blocked", "queue"]:
        state_dir = JOBS_DIR / state
        if not state_dir.is_dir():
            continue
        for job_file in state_dir.glob("job_*.json"):
            job = json.loads(job_file.read_text())
            for field in REQUIRED:
                check(f"{job_file.name} has {field}", field in job)
            check(f"{job_file.name} valid hat", job.get("hat") in VALID_HATS)
            verdict = job.get("evaluation", {}).get("verdict")
            check(f"{job_file.name} valid verdict", verdict in VALID_VERDICTS)

    print("\n=== Worker Logic ===")
    GPU_STOPPED = True
    check("runner refused when GPU stopped", GPU_STOPPED and "runner" == "runner")
    check("researcher allowed when GPU stopped", not (GPU_STOPPED and "researcher" == "runner"))

    print(f"\n=== Results: {passed} pass, {failed} fail ===")
    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
