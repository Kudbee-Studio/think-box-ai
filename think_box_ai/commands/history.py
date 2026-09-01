"""Command history command."""

from __future__ import annotations

import json
from pathlib import Path

from ..ui.colors import bold, cyan, dim, green, yellow
from ..utils.output import is_json_mode, output_json

HISTORY_FILE = Path(".thinkbox/history.jsonl")


def handle_history(args) -> None:
    clear = args.clear
    limit = args.limit

    if clear:
        if HISTORY_FILE.exists():
            HISTORY_FILE.unlink()
        if is_json_mode():
            output_json({"status": "cleared"})
            return
        print(green("  History cleared."))
        return

    if not HISTORY_FILE.exists():
        if is_json_mode():
            output_json({"history": []})
            return
        print(dim("  No history yet."))
        return

    lines = HISTORY_FILE.read_text().strip().split("\n")
    entries = []
    for line in lines[-limit:]:
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    if is_json_mode():
        output_json(entries)
        return

    print(bold(f"\n  Command History (last {len(entries)}):"))
    print(dim("  " + "─" * 50))

    for i, entry in enumerate(entries, 1):
        cmd = entry.get("command", "")
        ts = entry.get("timestamp", "")
        print(f"  {cyan(f'{i:4d}')} {dim(ts[:19])} {cmd}")


def record_command(command: str, args: list[str]) -> None:
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    from datetime import datetime, timezone
    entry = {
        "command": f"{command} {' '.join(args)}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    with open(HISTORY_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")
