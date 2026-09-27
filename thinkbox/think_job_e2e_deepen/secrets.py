"""Export secret scan for Think Job deepen (PR #183 F23)."""

from __future__ import annotations

import re

_PATTERNS = (
    re.compile(r"sk-[a-zA-Z0-9]{12,}"),
    re.compile(r"Bearer\s+[a-zA-Z0-9._-]{8,}"),
    re.compile(r"THINKBOX_[A-Z_]+=\S+"),
)


def scan_text_for_secrets(text: str) -> list[str]:
    hits: list[str] = []
    for pat in _PATTERNS:
        for match in pat.finditer(text):
            hits.append(match.group(0)[:32])
    return hits
