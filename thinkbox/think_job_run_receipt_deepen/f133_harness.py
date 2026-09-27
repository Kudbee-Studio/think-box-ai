"""F133 harness probe (PR #186 F21)."""
from __future__ import annotations
from pathlib import Path
from thinkbox.kilo_live_proof_readiness import REPO_ROOT

def f133_test_present() -> bool:
    return (REPO_ROOT / "tests/e2e/test_f133_governed_run_receipts.py").is_file()
