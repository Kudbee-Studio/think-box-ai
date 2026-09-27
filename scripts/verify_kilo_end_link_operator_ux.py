#!/usr/bin/env python3
"""Hermetic verify for PR #159 end-link-operator-ux gate."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from thinkbox.kilo_end_link_operator_ux import (
    end_link_operator_ux_contract_summary,
    hermetic_end_link_operator_ux_check,
    minimal_end_link_operator_ux_environ,
)


def main() -> int:
    env = minimal_end_link_operator_ux_environ()
    result = hermetic_end_link_operator_ux_check(env)
    summary = end_link_operator_ux_contract_summary(env)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
