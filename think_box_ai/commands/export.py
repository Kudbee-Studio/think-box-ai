"""Export data command."""

from __future__ import annotations

import csv
import json
import io
from pathlib import Path

from ..ui.colors import bold, cyan, dim, green, yellow
from ..utils.output import is_json_mode


def handle_export(args) -> None:
    what = args.what
    fmt = args.format
    output = Path(args.output) if args.output else None

    if what == "jobs":
        data = _export_jobs()
    elif what == "findings":
        data = _export_findings()
    elif what == "memory":
        data = _export_memory()
    elif what == "all":
        data = {
            "jobs": _export_jobs(),
            "findings": _export_findings(),
            "memory": _export_memory(),
        }
    else:
        print(yellow(f"  Unknown export target: {what}"))
        return

    if fmt == "json":
        content = json.dumps(data, indent=2, default=str)
        ext = "json"
    elif fmt == "csv":
        content = _to_csv(data)
        ext = "csv"
    elif fmt == "md":
        content = _to_markdown(data)
        ext = "md"
    else:
        content = json.dumps(data, indent=2, default=str)
        ext = "json"

    if output:
        output.write_text(content)
        if is_json_mode():
            import sys
            json.dump({"status": "exported", "path": str(output)}, sys.stdout)
            print()
        else:
            print(green(f"  Exported to {output}"))
    else:
        print(content)


def _export_jobs() -> list[dict]:
    jobs_dir = Path("data/jobs")
    if not jobs_dir.exists():
        return []
    jobs = []
    for f in sorted(jobs_dir.glob("*.json")):
        try:
            jobs.append(json.loads(f.read_text()))
        except (json.JSONDecodeError, OSError):
            continue
    return jobs


def _export_findings() -> list[dict]:
    findings_dir = Path("data/findings")
    if not findings_dir.exists():
        return []
    findings = []
    for f in sorted(findings_dir.glob("*.md")):
        findings.append({
            "name": f.stem,
            "content": f.read_text(),
        })
    return findings


def _export_memory() -> list[dict]:
    from core.indexing.database import init_db
    from core.indexing.memory import ProjectMemory
    init_db()
    project = str(Path.cwd())
    pm = ProjectMemory(project)
    return pm.list_all()


def _to_csv(data) -> str:
    output = io.StringIO()
    if isinstance(data, list) and data:
        if isinstance(data[0], dict):
            writer = csv.DictWriter(output, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)
    return output.getvalue()


def _to_markdown(data) -> str:
    lines = []
    if isinstance(data, dict):
        for key, value in data.items():
            lines.append(f"# {key.title()}")
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        name = item.get("name", item.get("id", item.get("key", "")))
                        lines.append(f"## {name}")
                        for k, v in item.items():
                            if k not in ("name", "id", "key"):
                                lines.append(f"- **{k}**: {v}")
                        lines.append("")
            lines.append("")
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                name = item.get("name", item.get("id", item.get("key", "")))
                lines.append(f"## {name}")
                for k, v in item.items():
                    if k not in ("name", "id", "key"):
                        lines.append(f"- **{k}**: {v}")
                lines.append("")
    return "\n".join(lines)
