"""Run PR #185 quickstart example locally."""

from __future__ import annotations

import subprocess
import sys
from typing import Any

from thinkbox.kilo_live_proof_readiness import REPO_ROOT


def run_quickstart() -> dict[str, Any]:
    script = REPO_ROOT / "examples/think_job_lifecycle_fixes_quickstart.py"
    proc = subprocess.run(
        [sys.executable, str(script)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return {
        "step": "quickstart",
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "live_api_called": False,
    }
