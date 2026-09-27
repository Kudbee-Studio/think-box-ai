#!/usr/bin/env python3
"""Run the JPL Power of 10 audit and check it against the committed baseline.

  python3 scripts/power_of_ten_audit.py                    # ratchet check, exit 1 on new violations
  python3 scripts/power_of_ten_audit.py --write-baseline   # record current findings as the baseline
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from thinkbox.power_of_ten import (  # noqa: E402
    audit_tree,
    load_baseline,
    ratchet,
    summarize,
    write_baseline,
)

PACKAGES = ("thinkbox", "core", "backend")
BASELINE = REPO / "data" / "thinkboxmd" / "artifacts" / "power_of_ten_baseline.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--write-baseline", action="store_true")
    args = parser.parse_args()

    findings = audit_tree(REPO, PACKAGES)
    summary = summarize(findings)
    print(f"{summary['total']} findings: {summary['by_rule']}")
    if args.write_baseline:
        write_baseline(BASELINE, findings)
        print(f"baseline written: {BASELINE.relative_to(REPO)}")
        return 0

    result = ratchet(findings, load_baseline(BASELINE))
    for f in result["new"]:
        print(f"NEW {f['rule']} {f['path']}:{f['lineno']} {f['qualname']}: {f['detail']}")
    if result["fixed"]:
        print(f"{sum(result['fixed'].values())} baseline findings fixed; "
              "rerun with --write-baseline to lock them in")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
