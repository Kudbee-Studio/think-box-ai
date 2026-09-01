"""GPU job queue commands."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from ..ui.colors import bold, cyan, dim, green, yellow
from ..ui.table import render_table
from ..utils.output import is_json_mode, output_json

QUEUE_FILE = Path("data/gpu_queue.jsonl")


def _load_queue() -> list[dict]:
    if not QUEUE_FILE.exists():
        return []
    items = []
    for line in QUEUE_FILE.read_text().strip().split("\n"):
        if line.strip():
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return items


def _save_queue(items: list[dict]) -> None:
    QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
    QUEUE_FILE.write_text("\n".join(json.dumps(i) for i in items) + "\n")


def handle_queue_command(args) -> None:
    sub = args.queue_command

    if sub == "status":
        _queue_status(args)
    elif sub == "add":
        _queue_add(args)
    elif sub == "batch":
        _queue_batch(args)
    elif sub == "drain":
        _queue_drain(args)
    else:
        print("Usage: thinkbox queue {status|add|batch|drain}")


def _queue_status(args) -> None:
    items = _load_queue()

    if is_json_mode():
        output_json({"queue_length": len(items), "items": items})
        return

    print(bold(f"\n  GPU Queue Status:"))
    print(dim("  " + "─" * 40))
    print(f"  Pending jobs: {cyan(str(len(items)))}")

    if not items:
        print(dim("  Queue is empty."))
        return

    headers = ["Priority", "Intent", "Added"]
    rows = []
    for item in items[:20]:
        pri = item.get("priority", "normal")
        pri_color = {"urgent": green, "normal": cyan, "low": dim}.get(pri, str)
        rows.append([
            pri_color(pri),
            item.get("intent", "")[:50],
            item.get("added_at", "")[:19],
        ])

    print(render_table(headers, rows))


def _queue_add(args) -> None:
    items = _load_queue()
    item = {
        "intent": args.intent,
        "priority": args.priority,
        "added_at": datetime.now(timezone.utc).isoformat(),
        "status": "pending",
    }
    items.append(item)
    _save_queue(items)

    if is_json_mode():
        output_json(item)
        return

    print(green(f"  Added to queue: {args.intent}"))
    print(f"  Priority: {args.priority}")


def _queue_batch(args) -> None:
    try:
        data = json.loads(Path(args.file).read_text())
    except (json.JSONDecodeError, OSError) as e:
        print(yellow(f"  Error reading file: {e}"))
        return

    items = _load_queue()
    for entry in data:
        if isinstance(entry, str):
            entry = {"intent": entry}
        items.append({
            "intent": entry.get("intent", ""),
            "priority": entry.get("priority", "normal"),
            "added_at": datetime.now(timezone.utc).isoformat(),
            "status": "pending",
        })

    _save_queue(items)

    if is_json_mode():
        output_json({"added": len(data), "total": len(items)})
        return

    print(green(f"  Batch added {len(data)} jobs to queue"))


def _queue_drain(args) -> None:
    items = _load_queue()

    if is_json_mode():
        output_json({"drained": len(items)})
        return

    print(bold(f"\n  Draining queue ({len(items)} jobs)..."))
    for item in items:
        print(cyan(f"  Processing: {item.get('intent', '')[:50]}"))

    _save_queue([])
    print(green("  Queue drained."))
