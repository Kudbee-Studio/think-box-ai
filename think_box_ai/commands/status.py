"""System status dashboard command."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from ..ui.colors import bold, cyan, dim, green, red, yellow
from ..utils.output import is_json_mode, output_json


def handle_status(args) -> None:
    if is_json_mode():
        output_json(_collect_status())
        return

    status = _collect_status()

    print(bold("\n  Think Box AI — System Status"))
    print(dim("  " + "─" * 55))

    # Environment
    print(f"\n  {bold('Environment:')}")
    env = status["environment"]
    print(f"    Python: {cyan(env['python_version'])}")
    print(f"    Platform: {cyan(env['platform'])}")
    print(f"    Think Box: {cyan(env['thinkbox_version'])}")

    # Directories
    print(f"\n  {bold('Directories:')}")
    for d in status["directories"]:
        icon = green("✓") if d["exists"] else red("✗")
        count = f" ({d['count']} items)" if d["exists"] else ""
        print(f"    {icon} {d['path']}{dim(count)}")

    # Jobs
    print(f"\n  {bold('Jobs:')}")
    jobs = status["jobs"]
    print(f"    Total: {cyan(str(jobs['total']))}")
    for state, count in jobs["by_state"].items():
        if count > 0:
            color = {"done": green, "active": yellow, "queue": cyan, "blocked": red}.get(state, str)
            print(f"    {state:10} {color(str(count))}")

    # Tools
    print(f"\n  {bold('Tools:')}")
    tools = status["tools"]
    print(f"    Registered: {cyan(str(tools['registered']))}")
    for t in tools["list"][:10]:
        print(f"      {green('✓')} {t}")

    # Memory
    print(f"\n  {bold('Memory:')}")
    mem = status["memory"]
    print(f"    Entries: {cyan(str(mem['entries']))}")
    print(f"    Database: {cyan(mem['database'])}")

    # Disk
    print(f"\n  {bold('Disk:')}")
    disk = status["disk"]
    print(f"    Free: {cyan(disk['free'])}")
    print(f"    Total: {cyan(disk['total'])}")


def _collect_status() -> dict:
    import platform

    from think_box_ai import __version__

    return {
        "environment": {
            "python_version": sys.version.split()[0],
            "platform": sys.platform,
            "thinkbox_version": __version__,
        },
        "directories": _check_directories(),
        "jobs": _check_jobs(),
        "tools": _check_tools(),
        "memory": _check_memory(),
        "disk": _check_disk(),
    }


def _check_directories() -> list[dict]:
    dirs = ["data", "data/jobs", "data/findings", "data/raw", "backend", "core"]
    result = []
    for d in dirs:
        path = Path(d)
        exists = path.exists()
        count = len(list(path.iterdir())) if exists and path.is_dir() else 0
        result.append({"path": d, "exists": exists, "count": count})
    return result


def _check_jobs() -> dict:
    jobs_dir = Path("data/jobs")
    if not jobs_dir.exists():
        return {"total": 0, "by_state": {}}

    import json
    jobs = []
    for f in jobs_dir.glob("*.json"):
        try:
            jobs.append(json.loads(f.read_text()))
        except (json.JSONDecodeError, OSError):
            continue

    by_state: dict[str, int] = {}
    for j in jobs:
        state = j.get("state", "unknown")
        by_state[state] = by_state.get(state, 0) + 1

    return {"total": len(jobs), "by_state": by_state}


def _check_tools() -> dict:
    try:
        from core.tools.registry import global_registry
        tools = global_registry.list_tools()
        return {"registered": len(tools), "list": tools}
    except ImportError:
        return {"registered": 0, "list": []}


def _check_memory() -> dict:
    db_path = Path("data/thinkbox.db")
    entries = 0
    if db_path.exists():
        try:
            import sqlite3
            conn = sqlite3.connect(str(db_path))
            cursor = conn.execute("SELECT COUNT(*) FROM memory_entries")
            entries = cursor.fetchone()[0]
            conn.close()
        except Exception:
            pass
    return {"entries": entries, "database": str(db_path)}


def _check_disk() -> dict:
    try:
        usage = shutil.disk_usage(".")
        free_gb = usage.free / (1024**3)
        total_gb = usage.total / (1024**3)
        return {"free": f"{free_gb:.1f}GB", "total": f"{total_gb:.1f}GB"}
    except OSError:
        return {"free": "unknown", "total": "unknown"}
