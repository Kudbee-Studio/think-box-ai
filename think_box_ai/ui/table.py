"""Table rendering utilities."""

from __future__ import annotations

from typing import Any

from .colors import bold, dim


def render_table(headers: list[str], rows: list[list[str]]) -> str:
    if not rows:
        return "  No data."

    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(str(cell)))

    separator = "  " + "+".join("-" * (w + 2) for w in col_widths)
    header_row = "  " + " | ".join(
        bold(h.ljust(col_widths[i])) for i, h in enumerate(headers)
    )

    lines = [separator, header_row, separator]
    for row in rows:
        line = "  " + " | ".join(
            str(cell).ljust(col_widths[i]) for i, cell in enumerate(row)
        )
        lines.append(line)
    lines.append(separator)

    return "\n".join(lines)


def render_key_value(data: dict[str, Any], indent: int = 2) -> str:
    if not data:
        return " " * indent + "No data."

    max_key_len = max(len(str(k)) for k in data)
    lines = []
    for key, value in data.items():
        prefix = " " * indent
        lines.append(f"{prefix}{bold(str(key).ljust(max_key_len))}  {value}")
    return "\n".join(lines)
