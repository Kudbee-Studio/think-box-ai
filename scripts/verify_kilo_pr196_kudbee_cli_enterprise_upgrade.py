#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from thinkbox.kilo_pr196_kudbee_cli_enterprise_upgrade import kudbee_cli_enterprise_upgrade_contract_summary


def main() -> int:
    summary = kudbee_cli_enterprise_upgrade_contract_summary()
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary.get("hermetic_operator_ok") else 1


if __name__ == "__main__":
    sys.exit(main())
