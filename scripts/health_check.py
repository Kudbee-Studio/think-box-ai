#!/usr/bin/env python3
"""Health check script for Think Box AI."""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
JOBS_DIR = REPO_ROOT / "jobs"


def check_jobs() -> bool:
    """Validate all job files."""
    ok = True
    for state in ["queue", "active", "done", "blocked"]:
        state_dir = JOBS_DIR / state
        if not state_dir.is_dir():
            continue
        for jf in sorted(state_dir.glob("job_*.json")):
            try:
                json.loads(jf.read_text())
            except Exception as e:
                print(f"FAIL: {jf.name} - {e}")
                ok = False
    return ok


def check_index() -> bool:
    """Check INDEX.md exists."""
    index_path = JOBS_DIR / "INDEX.md"
    if not index_path.exists():
        print("FAIL: jobs/INDEX.md missing")
        return False
    return True


def main() -> int:
    print("Think Box AI — Health Check")
    print()

    checks = [
        ("Job files valid", check_jobs()),
        ("INDEX.md exists", check_index()),
    ]

    all_ok = True
    for name, result in checks:
        status = "OK" if result else "FAIL"
        print(f"  [{status}] {name}")
        if not result:
            all_ok = False

    print()
    if all_ok:
        print("All checks passed.")
        return 0
    else:
        print("Some checks failed.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
