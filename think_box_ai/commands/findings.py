"""Findings browser commands."""

from __future__ import annotations

import json
from pathlib import Path

from ..ui.colors import bold, cyan, dim, green, yellow
from ..ui.table import render_table
from ..utils.output import is_json_mode, output_json

FINDINGS_DIR = Path("data/findings")


def _load_findings() -> list[dict]:
    if not FINDINGS_DIR.exists():
        return []
    findings = []
    for f in sorted(FINDINGS_DIR.glob("*.md")):
        content = f.read_text()
        findings.append({
            "name": f.stem,
            "path": str(f),
            "size": len(content),
            "preview": content[:200].replace("\n", " "),
        })
    return findings


def handle_findings_command(args) -> None:
    sub = args.findings_command

    if sub == "list":
        _findings_list(args)
    elif sub == "show":
        _findings_show(args)
    elif sub == "preview":
        _findings_preview(args)
    else:
        print("Usage: thinkbox findings {list|show|preview}")


def _findings_list(args) -> None:
    findings = _load_findings()

    if is_json_mode():
        output_json(findings)
        return

    if not findings:
        print(dim("  No findings yet. Run research jobs to generate findings."))
        return

    headers = ["Name", "Size", "Preview"]
    rows = []
    for f in findings:
        rows.append([
            f["name"],
            f"{f['size']}B",
            f["preview"][:60] + "..." if len(f["preview"]) > 60 else f["preview"],
        ])

    print(bold(f"\n  Findings ({len(findings)}):"))
    print(render_table(headers, rows))


def _findings_show(args) -> None:
    path = FINDINGS_DIR / f"{args.name}.md"

    if not path.exists():
        print(yellow(f"  Finding not found: {args.name}"))
        return

    content = path.read_text()

    if is_json_mode():
        output_json({"name": args.name, "content": content})
        return

    print(bold(f"\n  Finding: {args.name}"))
    print(dim("  " + "─" * 60))
    print(content)


def _findings_preview(args) -> None:
    path = FINDINGS_DIR / f"{args.name}.md"

    if not path.exists():
        print(yellow(f"  Finding not found: {args.name}"))
        return

    content = path.read_text()
    lines = content.split("\n")[:20]

    if is_json_mode():
        output_json({"name": args.name, "preview": "\n".join(lines)})
        return

    print(bold(f"\n  Preview: {args.name}"))
    print(dim("  " + "─" * 40))
    for line in lines:
        print(f"  {line}")
    if len(content.split("\n")) > 20:
        print(dim(f"  ... ({len(content.split(chr(10))) - 20} more lines)"))
