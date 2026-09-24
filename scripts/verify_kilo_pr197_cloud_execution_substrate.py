#!/usr/bin/env python3
"""Verify PR #197 cloud execution substrate gate."""

from __future__ import annotations

import json
import sys

from thinkbox.kilo_pr197_cloud_execution_substrate import cloud_execution_substrate_contract_summary


def main() -> int:
    summary = cloud_execution_substrate_contract_summary()
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary.get("hermetic_operator_ok") else 1


if __name__ == "__main__":
    sys.exit(main())
