#!/usr/bin/env python3
"""Fail if secret-like literals appear in tracked documentation.

Scans AGENTS.md, STATUS.md, docs/ (not data/ proof JSON). Hermetic-safe for CI.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

DOC_PATHS: tuple[Path, ...] = (
    REPO_ROOT / "AGENTS.md",
    REPO_ROOT / "STATUS.md",
    REPO_ROOT / "docs",
)

# Descriptive placeholders allowed in setup guides (not live credentials).
ALLOW_SUBSTRINGS: frozenset[str] = frozenset(
    {
        "REDACTED_",
        "sk-your-key",
        "gsk_your_key",
        "your-key",
        "super-secret",  # unit-test examples in docs only — skip if in tests/
    }
)

SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("upcloud_token", re.compile(r"ucat_[A-Z0-9]{10,}")),
    ("openai_sk", re.compile(r"sk-[a-zA-Z0-9]{20,}")),
    ("github_pat", re.compile(r"ghp_[a-zA-Z0-9]{20,}")),
    ("github_pat_v2", re.compile(r"github_pat_[a-zA-Z0-9_]{20,}")),
    ("aws_access_key", re.compile(r"AKIA[0-9A-Z]{16}")),
)


def iter_doc_files() -> list[Path]:
    """Collect markdown and text files under the documentation roots."""
    found: list[Path] = []
    for root in DOC_PATHS:
        if root.is_file():
            found.append(root)
            continue
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix.lower() not in {".md", ".json", ".txt"}:
                continue
            rel = path.relative_to(REPO_ROOT).as_posix()
            if rel.startswith("data/"):
                continue
            found.append(path)
    return found


def line_allowed(line: str) -> bool:
    return any(token in line for token in ALLOW_SUBSTRINGS)


def _display_path(path: Path) -> str:
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def scan_file(path: Path) -> list[str]:
    violations: list[str] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return [f"{path}: read error: {exc}"]
    disp = _display_path(path)
    for line_no, line in enumerate(text.splitlines(), start=1):
        if line_allowed(line):
            continue
        for label, pattern in SECRET_PATTERNS:
            if pattern.search(line):
                violations.append(f"{disp}:{line_no}: {label} pattern")
    return violations


def main() -> int:
    all_violations: list[str] = []
    for doc in iter_doc_files():
        all_violations.extend(scan_file(doc))
    if all_violations:
        print("Documentation secret scan FAILED:", file=sys.stderr)
        for item in all_violations:
            print(f"  {item}", file=sys.stderr)
        return 1
    print("Documentation secret scan OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
