#!/usr/bin/env python3
"""Run a mutation-testing campaign on one module and write a JSON report.

Example:
  python3 scripts/mutation_test.py thinkbox/multi_model_orchestrator.py \
      tests.unit.test_multi_model_orchestrator \
      --out data/thinkboxmd/artifacts/mutation_multi_model_orchestrator.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from thinkbox.mutation_testing import MutationCampaignError, run_campaign  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("module_path", type=Path)
    parser.add_argument("test_module")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--timeout", type=float, default=60.0)
    args = parser.parse_args()

    module_path = (REPO / args.module_path).resolve()
    module_name = ".".join(module_path.relative_to(REPO).with_suffix("").parts)
    try:
        report = run_campaign(module_path, module_name, args.test_module, REPO, timeout=args.timeout)
    except MutationCampaignError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2

    print(f"{module_name}: {report['killed']}/{report['total']} killed "
          f"(score {report['score']}), {report['survived']} survived")
    for s in report["survivors"]:
        print(f"  L{s['lineno']:<4} {s['kind']:<10} {s['original']!r} -> {s['replacement']!r}: {s['line']}")
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
