"""Doctor and diagnostic commands for Think Box CLI."""

from __future__ import annotations

import json
import os
import sqlite3
import sys
from pathlib import Path

from ..ui.colors import colorize, bold, dim, green, yellow, red
from ..utils.output import output_json, is_json_mode

from core.indexing.database import init_db, get_db


def doctor() -> None:
    """Run system diagnostics."""
    print(bold("\nThink Box AI — System Doctor"))
    print(dim("  " + "─" * 40))

    checks = []

    # 1. Database
    try:
        init_db()
        conn = get_db()
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        table_names = [t["name"] for t in tables]
        checks.append(("Database", "ok", f"{len(table_names)} tables"))
    except Exception as e:
        checks.append(("Database", "error", str(e)))

    # 2. Jobs
    try:
        jobs_dir = Path("jobs")
        if jobs_dir.exists():
            job_count = len(list(jobs_dir.rglob("job_*.json")))
            checks.append(("Jobs", "ok", f"{job_count} jobs"))
        else:
            checks.append(("Jobs", "warning", "jobs/ directory missing"))
    except Exception as e:
        checks.append(("Jobs", "error", str(e)))

    # 3. Findings
    try:
        findings_dir = Path("data/findings")
        if findings_dir.exists():
            finding_count = len(list(findings_dir.glob("*.md")))
            checks.append(("Findings", "ok", f"{finding_count} findings"))
        else:
            checks.append(("Findings", "warning", "data/findings/ missing"))
    except Exception as e:
        checks.append(("Findings", "error", str(e)))

    # 4. Templates
    try:
        tmpl_dir = Path("jobs/templates")
        if tmpl_dir.exists():
            tmpl_count = len(list(tmpl_dir.glob("template_*.json")))
            checks.append(("Templates", "ok", f"{tmpl_count} templates"))
        else:
            checks.append(("Templates", "warning", "templates missing"))
    except Exception as e:
        checks.append(("Templates", "error", str(e)))

    # 5. Config
    env_file = Path(".env")
    if env_file.exists():
        checks.append((".env", "ok", "present"))
    else:
        checks.append((".env", "warning", "not found (using defaults)"))

    # 6. Provider
    provider = os.environ.get("THINKBOX_DEFAULT_PROVIDER", "ollama")
    checks.append(("Provider", "ok", provider))

    # Print results
    all_ok = True
    for name, status, detail in checks:
        if status == "ok":
            icon = green("✓")
        elif status == "warning":
            icon = yellow("⚠")
            all_ok = False
        else:
            icon = red("✗")
            all_ok = False
        print(f"  {icon} {name}: {detail}")

    print()
    if all_ok:
        print(green("  All systems operational."))
    else:
        print(yellow("  Some checks need attention."))


def init_project() -> None:
    """Initialize a new Think Box project."""
    print(bold("\nInitializing Think Box project..."))

    # Create directories
    dirs = ["data/findings", "data/fixtures", "data/raw", "jobs/queue", "jobs/active", "jobs/done", "jobs/blocked"]
    for d in dirs:
        Path(d).mkdir(parents=True, exist_ok=True)
        print(f"  Created: {d}")

    # Initialize database
    init_db()
    print("  Initialized: data/thinkbox.db")

    # Create .env.example if missing
    if not Path(".env").exists():
        Path(".env").write_text("# Think Box AI Configuration\nTHINKBOX_DEFAULT_PROVIDER=ollama\n")
        print("  Created: .env")

    print(green("\nProject initialized!"))
    print("  Run: thinkbox job list")
    print("  Run: thinkbox doctor")
