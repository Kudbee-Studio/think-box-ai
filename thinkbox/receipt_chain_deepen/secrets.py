"""Secret scan helper for exports (PR #182 F23)."""

from __future__ import annotations

import re

_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9]{12,}"),
    re.compile(r"THINKBOX_[A-Z_]+=\S+"),
)


def scan_text_for_secrets(text: str) -> tuple[str, ...]:
    hits: list[str] = []
    for pat in _PATTERNS:
        for match in pat.findall(text):
            hits.append(match[:8] + "...")
    return tuple(hits)
