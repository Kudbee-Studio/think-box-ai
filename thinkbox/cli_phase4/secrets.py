"""Stronger secrets scanning for CLI examples (PR #196 F16)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from thinkbox.kilo_live_proof_readiness import REPO_ROOT

_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("openai_sk", re.compile(r"sk-[A-Za-z0-9]{20,}")),
    ("bearer_token", re.compile(r"Bearer\s+[A-Za-z0-9._\-]{16,}", re.I)),
    ("aws_key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("generic_api_key", re.compile(r"(?i)api[_-]?key\s*=\s*['\"]?[A-Za-z0-9]{16,}")),
)


@dataclass(frozen=True)
class SecretHit:
    kind: str
    line_no: int
    excerpt: str


def scan_text_for_secrets(text: str) -> tuple[SecretHit, ...]:
    hits: list[SecretHit] = []
    for i, line in enumerate(text.splitlines(), start=1):
        for kind, pat in _PATTERNS:
            if pat.search(line):
                hits.append(SecretHit(kind=kind, line_no=i, excerpt=line[:80]))
    return tuple(hits)


def scan_cli_examples(repo_root: Path | None = None) -> tuple[SecretHit, ...]:
    root = repo_root if repo_root is not None else REPO_ROOT
    paths = [
        root / "examples/kudbee_cli_phase2_quickstart.py",
        root / "examples/kudbee_cli_phase3_quickstart.py",
        root / "examples/kudbee_cli_enterprise_upgrade_quickstart.py",
        root / "docs/guides/kudbee_cli_phase2_quickstart.md",
        root / "docs/guides/kudbee_cli_phase3_quickstart.md",
        root / "docs/guides/kudbee_cli_enterprise_upgrade_quickstart.md",
    ]
    all_hits: list[SecretHit] = []
    for path in paths:
        if not path.is_file():
            continue
        for hit in scan_text_for_secrets(path.read_text(encoding="utf-8")):
            all_hits.append(hit)
    return tuple(all_hits)
