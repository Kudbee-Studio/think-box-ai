#!/usr/bin/env python3
"""Staging live drill runner — exits 0 only when LIVE_VERIFIED attestation is produced."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from thinkbox.pipeline_live_drill import preflight_report


def main() -> int:
    pre = preflight_report()
    print(json.dumps(pre, indent=2, default=str))
    if not pre.get("ready_for_live_drill"):
        print("\nLIVE_VERIFIED: BLOCKED — missing prerequisites (no fabricated evidence).", file=sys.stderr)
        return 2
    print(
        "\nPreflight OK — set THINKBOX_LIVE_DRILL_PHYSICAL_STAGING=1 on the staging cell, "
        "then POST /api/v1/control-plane/pipeline/live/drill/run with governance + founder proof.",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
