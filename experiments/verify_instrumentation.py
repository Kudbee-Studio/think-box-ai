#!/usr/bin/env python3
"""End-to-end checks for the swarm instrumentation layer.

Asserts each of the ten instruments actually works — not that it merely ran.
Every check is self-contained and uses ``:memory:`` SQLite so it is fast and
leaves no residue. Prints one line per check and exits non-zero on any failure.

Usage:
    python3 experiments/verify_instrumentation.py
    python3 experiments/verify_instrumentation.py --live   # also run a real swarm
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from thinkbox.swarm_instrumentation_checks import hermetic_checks_tuple_for_experiments

RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, fn) -> None:
    try:
        detail = fn() or ""
        RESULTS.append((name, True, str(detail)))
        print(f"  PASS  {name}" + (f"  · {detail}" if detail else ""))
    except AssertionError as e:
        RESULTS.append((name, False, str(e)))
        print(f"  FAIL  {name}  · {e}")
    except Exception as e:  # noqa: BLE001
        RESULTS.append((name, False, f"{type(e).__name__}: {e}"))
        print(f"  FAIL  {name}  · {type(e).__name__}: {e}")


CHECKS = hermetic_checks_tuple_for_experiments()


def live_swarm_check() -> str:
    """Optional: drive a real swarm and assert the artifacts + index are produced."""
    import subprocess

    out = ROOT / "data" / "thinkboxmd"
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "experiments" / "big_swarm.py"),
            "--primary",
            "24",
            "--validators",
            "8",
            "--concurrency",
            "16",
            "--arena",
        ],
        capture_output=True,
        text=True,
        timeout=300,
        cwd=str(ROOT),
    )
    assert result.returncode == 0, f"swarm exited {result.returncode}: {result.stderr[-400:]}"
    proofs = sorted(out.glob("big_swarm_*.json"))
    assert proofs, "no proof written"
    data = json.loads(proofs[-1].read_text())
    recon = data["reconciliation"]
    assert recon["ledger_valid"], "ledger chain invalid"
    assert data["genome"]["verified"], "genome not verified"
    assert data["proof_chain"]["verified"], "proof chain not verified"
    assert recon["strength"]["index"] > 0, "index not computed"
    assert data["instruments"]["flight_recorder_records"] > 0
    return (
        f"{recon['total_calls']} calls · index={recon['strength']['index']} · "
        f"ledger={recon['ledger_valid']} · chain={data['proof_chain']['verified']}"
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="also run a real swarm end-to-end")
    args = ap.parse_args()

    print("KUDBEE swarm instrumentation — end-to-end checks")
    print("=" * 64)
    for name, fn in CHECKS:
        check(name, fn)

    if args.live:
        print("-" * 64)
        check("LIVE end-to-end swarm", live_swarm_check)

    passed = sum(1 for _, ok, _ in RESULTS if ok)
    total = len(RESULTS)
    print("=" * 64)
    print(f"{passed}/{total} checks passed")
    for name, ok, detail in RESULTS:
        if not ok:
            print(f"  FAILED: {name} — {detail}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
