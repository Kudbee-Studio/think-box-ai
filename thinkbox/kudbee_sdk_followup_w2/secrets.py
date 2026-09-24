"""Secret pattern scan for SDK examples (PR #181 F16)."""

from __future__ import annotations

import re
from dataclasses import dataclass

_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._-]{20,}"),
    re.compile(r"api[_-]?key\s*=\s*['\"][^'\"]+['\"]", re.IGNORECASE),
)


@dataclass(frozen=True)
class SecretScanResult:
    clean: bool
    hits: tuple[str, ...]


def scan_text_for_secrets(text: str) -> SecretScanResult:
    hits: list[str] = []
    for pattern in _PATTERNS:
        if pattern.search(text):
            hits.append(pattern.pattern)
    return SecretScanResult(clean=len(hits) == 0, hits=tuple(hits))
