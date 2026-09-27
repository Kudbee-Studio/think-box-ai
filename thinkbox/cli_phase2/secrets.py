"""Scan strings for accidental secrets in examples (PR #178 F19)."""

from __future__ import annotations

import re
from dataclasses import dataclass

_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._\-]{20,}"),
    re.compile(r"UPSTASH_[A-Z_]+=[^\s\"']{8,}"),
)


@dataclass(frozen=True)
class SecretFinding:
    pattern: str
    snippet: str


def scan_for_secrets(text: str) -> tuple[SecretFinding, ...]:
    findings: list[SecretFinding] = []
    for pat in _SECRET_PATTERNS:
        match = pat.search(text)
        if match:
            findings.append(SecretFinding(pattern=pat.pattern, snippet=match.group(0)[:24] + "..."))
    return tuple(findings)
