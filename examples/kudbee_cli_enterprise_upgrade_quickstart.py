#!/usr/bin/env python3
from __future__ import annotations

import json

from thinkbox.cli_phase4.status_report import cli_phase4_status_report
from thinkbox.kilo_pr196_kudbee_cli_enterprise_upgrade import kudbee_cli_enterprise_upgrade_contract_summary


def main() -> None:
    print(json.dumps({"contract": kudbee_cli_enterprise_upgrade_contract_summary(), "status": cli_phase4_status_report()}, indent=2))


if __name__ == "__main__":
    main()
