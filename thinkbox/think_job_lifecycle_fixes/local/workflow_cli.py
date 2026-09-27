"""CLI entry for local PR #185 workflow."""

from __future__ import annotations

import argparse
import json

from thinkbox.think_job_lifecycle_fixes.local.workflow import run_local_workflow


def main() -> int:
    parser = argparse.ArgumentParser(description="PR #185 local environment workflow")
    parser.add_argument("--dry-run", action="store_true", help="List steps only")
    parser.add_argument("--json", action="store_true", help="Print JSON summary")
    args = parser.parse_args()
    summary = run_local_workflow(dry_run=args.dry_run)
    print(json.dumps(summary, indent=2, sort_keys=True))
    if summary.get("dry_run"):
        return 0
    return 0 if summary.get("all_ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
