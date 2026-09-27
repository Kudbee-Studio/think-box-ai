#!/usr/bin/env python3
"""Run the fault-injection (chaos) campaign and write a JSON report.

Flight readiness item 3: under timeouts, garbage and a persistently lying
provider, does anything report a false success? Exits 0 only if the
campaign found zero silent successes, zero crashes, zero construction
anomalies, and zero under-recovered (fixable-but-unfixed) faults.

  python3 scripts/fault_injection_campaign.py
  python3 scripts/fault_injection_campaign.py --out data/thinkboxmd/artifacts/fault_injection_campaign.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from thinkbox.fault_injection import run_fault_campaign  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    report = run_fault_campaign()
    d = report.to_dict()
    print(
        f"{d['total']} trials: {d['recovered_successes']} recovered, "
        f"{d['loud_failures']} loud failures, "
        f"{d['silent_successes']} silent successes, "
        f"{d['under_recovered']} under-recovered, "
        f"{d['crashed']} crashed, {d['unexpected']} unexpected"
    )
    if not report.passed:
        for t in d["trials"]:
            if t["verdict"] not in ("recovered_success", "loud_failure"):
                print(f"  FAIL {t['kind']}/{t['family']}: {t['verdict']} (expected {t['expected']})")
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(d, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
