"""Table rendering for Think Box CLI."""

from __future__ import annotations

from typing import Sequence

from .colors import colorize, dim, bold


def render_table(headers: list[str], rows: list[list[str]]) -> str:
    """Render a simple text table."""
    if not rows:
        return dim("  (empty)")

    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(str(cell)))

    lines = []

    # Header
    header_cells = [bold(headers[i].ljust(col_widths[i])) for i in range(len(headers))]
    lines.append("  " + " │ ".join(header_cells))
    lines.append("  " + "─┼─".join("─" * w for w in col_widths))

    # Rows
    for row in rows:
        cells = [str(row[i]).ljust(col_widths[i]) for i in range(len(row))]
        lines.append("  │ ".join(cells))

    return "\n".join(lines)


def render_key_value(data: dict, indent: int = 2) -> str:
    """Render key-value pairs."""
    max_key = max(len(str(k)) for k in data) if data else 0
    lines = []
    for k, v in data.items():
        key = str(k).rjust(max_key)
        lines.append(f"{' ' * indent}{bold(key)}: {v}")
    return "\n".join(lines)
