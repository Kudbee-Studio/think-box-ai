"""Agent logs command."""

from __future__ import annotations

from pathlib import Path

from ..ui.colors import bold, cyan, dim, green, yellow
from ..utils.output import is_json_mode, output_json

LOGS_DIR = Path("data/logs")


def handle_logs(args) -> None:
    tail = args.tail
    job_filter = args.job
    follow = args.follow

    log_files = []
    if LOGS_DIR.exists():
        log_files = sorted(LOGS_DIR.glob("*.log"), key=lambda p: p.stat().st_mtime, reverse=True)

    if job_filter:
        log_files = [f for f in log_files if job_filter in f.name]

    if not log_files:
        if is_json_mode():
            output_json({"logs": [], "message": "No log files found"})
            return
        print(dim("  No log files found."))
        return

    if is_json_mode():
        logs = []
        for f in log_files[:5]:
            lines = f.read_text().strip().split("\n")
            if job_filter:
                lines = [l for l in lines if job_filter in l]
            logs.append({"file": f.name, "lines": lines[-tail:]})
        output_json(logs)
        return

    print(bold(f"\n  Agent Logs:"))
    print(dim("  " + "─" * 50))

    for f in log_files[:5]:
        lines = f.read_text().strip().split("\n")
        if job_filter:
            lines = [l for l in lines if job_filter in l]
        lines = lines[-tail:]

        print(f"\n  {cyan(f.name)} ({len(lines)} lines):")
        for line in lines:
            if "ERROR" in line or "error" in line:
                print(f"    {yellow(line)}")
            elif "WARN" in line or "warn" in line:
                print(f"    {dim(line)}")
            else:
                print(f"    {line}")

    if follow:
        print(dim("\n  Following logs... (Ctrl+C to stop)"))
        try:
            import time
            while True:
                time.sleep(2)
                for f in log_files[:1]:
                    new_lines = f.read_text().strip().split("\n")[-tail:]
                    for line in new_lines[-5:]:
                        print(f"  {line}")
        except KeyboardInterrupt:
            print(dim("\n  Stopped."))
