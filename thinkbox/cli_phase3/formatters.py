"""Table / JSON / YAML output formatters (PR #180 F04)."""

from __future__ import annotations

import json
from enum import Enum
from typing import Any


class OutputFormat(str, Enum):
    JSON = "json"
    TABLE = "table"
    YAML = "yaml"


def _to_yaml_simple(doc: Any, indent: int = 0) -> str:
    """Minimal YAML emitter (stdlib-only) for flat dicts and lists."""
    pad = "  " * indent
    if isinstance(doc, dict):
        lines: list[str] = []
        for key, value in doc.items():
            if isinstance(value, (dict, list)):
                lines.append(f"{pad}{key}:")
                lines.append(_to_yaml_simple(value, indent + 1))
            else:
                lines.append(f"{pad}{key}: {json.dumps(value)}")
        return "\n".join(lines)
    if isinstance(doc, list):
        lines = []
        for item in doc:
            if isinstance(item, dict):
                lines.append(f"{pad}-")
                lines.append(_to_yaml_simple(item, indent + 1))
            else:
                lines.append(f"{pad}- {json.dumps(item)}")
        return "\n".join(lines)
    return f"{pad}{json.dumps(doc)}"


def format_table(rows: list[dict[str, Any]], columns: tuple[str, ...] | None = None) -> str:
    if not rows:
        return "(empty)"
    cols = columns or tuple(rows[0].keys())
    widths = {c: max(len(c), max(len(str(r.get(c, ""))) for r in rows)) for c in cols}
    header = " | ".join(c.ljust(widths[c]) for c in cols)
    sep = "-+-".join("-" * widths[c] for c in cols)
    body = "\n".join(
        " | ".join(str(r.get(c, "")).ljust(widths[c]) for c in cols) for r in rows
    )
    return f"{header}\n{sep}\n{body}"


def emit_formatted(
    doc: Any,
    fmt: OutputFormat,
    table_rows: list[dict[str, Any]] | None = None,
) -> str:
    if fmt == OutputFormat.JSON:
        return json.dumps(doc, indent=2, sort_keys=True)
    if fmt == OutputFormat.YAML:
        return _to_yaml_simple(doc)
    if table_rows is not None:
        return format_table(table_rows)
    if isinstance(doc, list):
        return format_table([x if isinstance(x, dict) else {"value": x} for x in doc])
    if isinstance(doc, dict):
        return format_table([doc])
    return str(doc)
