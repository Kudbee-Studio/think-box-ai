#!/usr/bin/env python3
"""Hermetic beyond-KILO lint gate verify (PR #170 — ruff, mypy, bandit)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from thinkbox.kilo_beyond_kilo_lint import beyond_kilo_lint_contract_summary


def main() -> int:
    os.environ.setdefault("KILO_BEYOND_KILO_LINT_EXECUTE", "1")
    if os.environ.get("CI", "").strip().lower() in ("1", "true", "yes"):
        os.environ.setdefault("KILO_BEYOND_KILO_LINT_REQUIRE_TOOLS", "1")
    summary = beyond_kilo_lint_contract_summary()
    print(json.dumps(summary, indent=2, sort_keys=True))
    if not summary.get("hermetic_operator_ok"):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
