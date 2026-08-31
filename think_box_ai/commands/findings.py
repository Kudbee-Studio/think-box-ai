"""Findings commands for Think Box CLI."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from ..ui.colors import bold, dim
from ..utils.output import output_json, is_json_mode

FINDINGS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "findings"


def list_findings() -> None:
    """List all findings."""
    if not FINDINGS_DIR.exists():
        print("No findings found.")
        return

    findings = sorted(FINDINGS_DIR.glob("*.md"))
    if is_json_mode():
        output_json([str(f.name) for f in findings])
        return

    print(bold("Findings:"))
    for f in findings:
        print(f"  {f.name}")


def show_finding(name: str) -> None:
    """Show a finding by name or partial match."""
    matches = list(FINDINGS_DIR.glob(f"*{name}*.md"))
    if not matches:
        print(f"No finding matches: {name}")
        return
    for m in matches:
        print(f"\n{'='*60}")
        print(bold(f"File: {m.name}"))
        print(f"{'='*60}")
        print(m.read_text())


def preview_finding(name: str) -> None:
    """Preview first 20 lines of a finding."""
    matches = list(FINDINGS_DIR.glob(f"*{name}*.md"))
    if not matches:
        print(f"No finding matches: {name}")
        return
    for m in matches:
        lines = m.read_text().splitlines()
        print(bold(f"\n{m.name}"))
        print(dim(f"  ({len(lines)} lines)\n"))
        for line in lines[:20]:
            print(f"  {line}")
        if len(lines) > 20:
            print(dim(f"  ... ({len(lines) - 20} more lines)"))


def export_findings(output_path: str | None = None) -> None:
    """Export all findings as JSON."""
    if not FINDINGS_DIR.exists():
        print("No findings found.")
        return

    findings = []
    for f in sorted(FINDINGS_DIR.glob("*.md")):
        findings.append({
            "name": f.name,
            "path": str(f),
            "size": f.stat().st_size,
            "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
        })

    if output_path:
        Path(output_path).write_text(json.dumps(findings, indent=2))
        print(f"Exported {len(findings)} findings to {output_path}")
    else:
        print(json.dumps(findings, indent=2))
