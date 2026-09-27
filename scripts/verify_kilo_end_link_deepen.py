#!/usr/bin/env python3
"""Hermetic operator gate for PR #158 END LINK / control-plane deepen."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from thinkbox.kilo_end_link_deepen import (
    end_link_deepen_contract_summary,
    hermetic_end_link_deepen_check,
    minimal_end_link_deepen_environ,
)


def main() -> int:
    env = minimal_end_link_deepen_environ()
    result = hermetic_end_link_deepen_check(env)
    summary = end_link_deepen_contract_summary(env)
    print(json.dumps(summary, indent=2, sort_keys=True))
    if not result.ok:
        for v in result.violations:
            print(f"violation: {v.code}: {v.message}", file=sys.stderr)
        return 1
    if summary.get("live_api_called"):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
