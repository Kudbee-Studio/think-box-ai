"""Interactive REPL command."""

from __future__ import annotations

import shlex
import sys

from ..ui.colors import bold, cyan, dim, green, yellow
from ..ui.prompt import print_error, print_success, print_warning

COMMANDS = {
    "help": "Show available commands",
    "exit": "Exit the REPL",
    "quit": "Exit the REPL",
    "status": "Show system status",
    "jobs": "List jobs",
    "memory": "Show memory entries",
    "findings": "List findings",
    "doctor": "Run diagnostics",
    "clear": "Clear the screen",
}


def handle_repl(args) -> None:
    print(bold("\n  Think Box AI — Interactive REPL"))
    print(dim("  Type 'help' for commands, 'exit' to quit.\n"))

    while True:
        try:
            line = input(cyan("thinkbox> ")).strip()
        except (EOFError, KeyboardInterrupt):
            print(dim("\n  Goodbye."))
            break

        if not line:
            continue

        parts = shlex.split(line)
        cmd = parts[0].lower()
        cmd_args = parts[1:]

        if cmd in ("exit", "quit"):
            print(dim("  Goodbye."))
            break
        elif cmd == "help":
            _repl_help()
        elif cmd == "status":
            _repl_status()
        elif cmd == "jobs":
            _repl_jobs()
        elif cmd == "memory":
            _repl_memory()
        elif cmd == "findings":
            _repl_findings()
        elif cmd == "doctor":
            from .doctor import handle_doctor
            from argparse import Namespace
            handle_doctor(Namespace())
        elif cmd == "clear":
            print("\033[2J\033[H")
        else:
            print(yellow(f"  Unknown command: {cmd}"))
            print(dim("  Type 'help' for available commands."))


def _repl_help() -> None:
    print(bold("\n  Available Commands:"))
    print(dim("  " + "─" * 40))
    for cmd, desc in COMMANDS.items():
        print(f"    {green(cmd):12} {dim(desc)}")
    print()


def _repl_status() -> None:
    from .status import _collect_status
    status = _collect_status()
    env = status["environment"]
    print(f"\n  Python: {cyan(env['python_version'])}")
    print(f"  Version: {cyan(env['thinkbox_version'])}")
    print(f"  Jobs: {cyan(str(status['jobs']['total']))}")
    print(f"  Tools: {cyan(str(status['tools']['registered']))}")
    print()


def _repl_jobs() -> None:
    from pathlib import Path
    import json
    jobs_dir = Path("data/jobs")
    if not jobs_dir.exists():
        print(dim("  No jobs directory."))
        return
    jobs = list(jobs_dir.glob("*.json"))
    print(f"\n  Jobs: {len(jobs)}")
    for f in jobs[:10]:
        try:
            job = json.loads(f.read_text())
            print(f"    {cyan(job.get('id', '')[:12])} {job.get('state', '?'):10} {job.get('intent', '')[:40]}")
        except (json.JSONDecodeError, OSError):
            continue
    print()


def _repl_memory() -> None:
    from pathlib import Path
    import sqlite3
    db_path = Path("data/thinkbox.db")
    if not db_path.exists():
        print(dim("  No memory database."))
        return
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute("SELECT key, value FROM memory_entries LIMIT 10")
        rows = cursor.fetchall()
        conn.close()
        print(f"\n  Memory entries:")
        for key, value in rows:
            print(f"    {cyan(key)}: {value[:60]}")
    except Exception as e:
        print(yellow(f"  Error: {e}"))
    print()


def _repl_findings() -> None:
    from pathlib import Path
    findings_dir = Path("data/findings")
    if not findings_dir.exists():
        print(dim("  No findings directory."))
        return
    findings = list(findings_dir.glob("*.md"))
    print(f"\n  Findings: {len(findings)}")
    for f in findings:
        print(f"    {green(f.stem)}")
    print()
