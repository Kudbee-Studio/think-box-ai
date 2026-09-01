"""Import data command."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from ..ui.colors import bold, cyan, dim, green, yellow
from ..utils.output import is_json_mode, output_json


def handle_import(args) -> None:
    file_path = Path(args.file)
    data_type = args.type

    if not file_path.exists():
        print(yellow(f"  File not found: {file_path}"))
        return

    if file_path.suffix == ".json":
        try:
            data = json.loads(file_path.read_text())
        except json.JSONDecodeError as e:
            print(yellow(f"  Invalid JSON: {e}"))
            return
    elif file_path.suffix == ".csv":
        with open(file_path, newline="") as f:
            reader = csv.DictReader(f)
            data = list(reader)
    else:
        print(yellow(f"  Unsupported format: {file_path.suffix}"))
        return

    if data_type == "jobs":
        _import_jobs(data)
    elif data_type == "findings":
        _import_findings(data)
    elif data_type == "memory":
        _import_memory(data)
    else:
        print(yellow(f"  Unknown import type: {data_type}"))
        return


def _import_jobs(data: list[dict]) -> None:
    jobs_dir = Path("data/jobs")
    jobs_dir.mkdir(parents=True, exist_ok=True)

    if isinstance(data, dict):
        data = [data]

    imported = 0
    for item in data:
        job_id = item.get("id", f"job_{hash(str(item)) % 100000:05d}")
        path = jobs_dir / f"{job_id}.json"
        path.write_text(json.dumps(item, indent=2, default=str))
        imported += 1

    if is_json_mode():
        output_json({"imported": imported, "type": "jobs"})
        return

    print(green(f"  Imported {imported} jobs"))


def _import_findings(data: list[dict]) -> None:
    findings_dir = Path("data/findings")
    findings_dir.mkdir(parents=True, exist_ok=True)

    if isinstance(data, dict):
        data = [data]

    imported = 0
    for item in data:
        name = item.get("name", f"finding_{imported}")
        content = item.get("content", item.get("body", str(item)))
        path = findings_dir / f"{name}.md"
        path.write_text(content)
        imported += 1

    if is_json_mode():
        output_json({"imported": imported, "type": "findings"})
        return

    print(green(f"  Imported {imported} findings"))


def _import_memory(data: list[dict]) -> None:
    from core.indexing.database import init_db
    from core.indexing.memory import ProjectMemory
    init_db()
    project = str(Path.cwd())
    pm = ProjectMemory(project)

    if isinstance(data, dict):
        data = [data]

    imported = 0
    for item in data:
        key = item.get("key", item.get("id", f"mem_{imported}"))
        value = item.get("value", item.get("content", str(item)))
        pm.remember(key, value, source="import")
        imported += 1

    if is_json_mode():
        output_json({"imported": imported, "type": "memory"})
        return

    print(green(f"  Imported {imported} memories"))
