#!/usr/bin/env python3
"""Comprehensive health check for Think Box AI."""

import json
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
JOBS_DIR = REPO_ROOT / "jobs"


def check_jobs() -> tuple[bool, str]:
    """Validate all job files."""
    if not JOBS_DIR.exists():
        return False, "jobs/ directory missing"
    ok = True
    count = 0
    for state in ["queue", "active", "done", "blocked"]:
        state_dir = JOBS_DIR / state
        if not state_dir.is_dir():
            continue
        for jf in sorted(state_dir.glob("job_*.json")):
            try:
                job = json.loads(jf.read_text())
                assert "id" in job
                assert "evaluation" in job
                count += 1
            except Exception as e:
                print(f"FAIL: {jf.name} - {e}")
                ok = False
    return ok, f"{count} jobs valid"


def check_index() -> tuple[bool, str]:
    """Check INDEX.md exists."""
    index_path = JOBS_DIR / "INDEX.md"
    if not index_path.exists():
        return False, "INDEX.md missing"
    return True, "present"


def check_database() -> tuple[bool, str]:
    """Check SQLite database."""
    db_path = REPO_ROOT / "data" / "thinkbox.db"
    if not db_path.exists():
        return False, "thinkbox.db missing"
    try:
        conn = sqlite3.connect(str(db_path))
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        conn.close()
        return True, f"{len(tables)} tables"
    except Exception as e:
        return False, str(e)


def check_findings() -> tuple[bool, str]:
    """Check findings directory."""
    findings_dir = REPO_ROOT / "data" / "findings"
    if not findings_dir.exists():
        return False, "data/findings/ missing"
    count = len(list(findings_dir.glob("*.md")))
    return True, f"{count} findings"


def check_templates() -> tuple[bool, str]:
    """Check templates."""
    tmpl_dir = JOBS_DIR / "templates"
    if not tmpl_dir.exists():
        return False, "templates missing"
    count = len(list(tmpl_dir.glob("template_*.json")))
    return True, f"{count} templates"


def main() -> int:
    print("Think Box AI — Health Check")
    print()

    checks = [
        ("Jobs", check_jobs()),
        ("Index", check_index()),
        ("Database", check_database()),
        ("Findings", check_findings()),
        ("Templates", check_templates()),
    ]

    all_ok = True
    for name, (result, msg) in checks:
        status = "OK" if result else "FAIL"
        print(f"  [{status}] {name}: {msg}")
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
