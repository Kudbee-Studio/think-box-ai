"""Run PR #185 gate verify script locally."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

from thinkbox.kilo_live_proof_readiness import REPO_ROOT


def run_verify_gate() -> dict[str, Any]:
    script = REPO_ROOT / "scripts/verify_kilo_pr185_think_job_lifecycle_fixes.py"
    proc = subprocess.run(
        [sys.executable, str(script)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return {
        "step": "verify_gate",
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "live_api_called": False,
    }
