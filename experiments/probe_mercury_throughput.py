#!/usr/bin/env python3
"""Bounded concurrency probe for the Inception Mercury 2 endpoint.

Measures real throughput (requests/sec, p50/p95 latency, error classes) so we
know whether a large swarm is feasible and where the ceiling is.

Usage:
    python3 experiments/probe_mercury_throughput.py --levels 1,4,16,32 --per-level 32
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

URL = "https://api.inceptionlabs.ai/v1/chat/completions"
MODEL = "mercury-2"


def one_call(key: str, prompt: str, max_tokens: int) -> dict:
    body = json.dumps(
        {
            "model": MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": 0.0,
        }
    ).encode()
    req = urllib.request.Request(
        URL,
        data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            payload = json.loads(r.read().decode())
            dt = time.monotonic() - t0
            return {"ok": True, "latency": dt, "status": r.status, "usage": payload.get("usage", {})}
    except urllib.error.HTTPError as e:
        dt = time.monotonic() - t0
        return {"ok": False, "latency": dt, "status": e.code, "error": e.read(160).decode(errors="replace")[:160]}
    except Exception as e:
        dt = time.monotonic() - t0
        return {"ok": False, "latency": dt, "status": 0, "error": f"{type(e).__name__}: {str(e)[:120]}"}


def level_run(key: str, concurrency: int, total: int, max_tokens: int) -> dict:
    results: list[dict] = []
    lock = threading.Lock()
    t0 = time.monotonic()

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [
            pool.submit(one_call, key, f"Reply with the single word: ACK{i}", max_tokens)
            for i in range(total)
        ]
        for fut in as_completed(futures):
            with lock:
                results.append(fut.result())

    elapsed = time.monotonic() - t0
    ok = [r for r in results if r["ok"]]
    lat = sorted(r["latency"] for r in ok) or [0.0]
    errs: dict[str, int] = {}
    for r in results:
        if not r["ok"]:
            k = f"{r['status']}:{(r.get('error') or '')[:60]}"
            errs[k] = errs.get(k, 0) + 1

    def pct(p: float) -> float:
        idx = min(len(lat) - 1, int(round((p / 100) * (len(lat) - 1))))
        return round(lat[idx], 3)

    return {
        "concurrency": concurrency,
        "total": total,
        "ok": len(ok),
        "failed": len(results) - len(ok),
        "elapsed_s": round(elapsed, 3),
        "rps": round(len(results) / elapsed, 2),
        "ok_rps": round(len(ok) / elapsed, 2),
        "p50_s": pct(50),
        "p95_s": pct(95),
        "max_s": round(max(lat), 3),
        "errors": errs,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--levels", default="1,4,16,32")
    ap.add_argument("--per-level", type=int, default=32)
    ap.add_argument("--max-tokens", type=int, default=64)
    args = ap.parse_args()

    key = os.environ.get("INCEPTION_API_KEY", "")
    if not key:
        print("INCEPTION_API_KEY missing")
        return 2

    print(f"Mercury 2 throughput probe — model={MODEL}")
    print(f"{'conc':>5} {'ok':>5} {'fail':>5} {'elapsed':>8} {'rps':>7} {'ok_rps':>7} {'p50':>6} {'p95':>6}")
    out = []
    for level in [int(x) for x in args.levels.split(",")]:
        r = level_run(key, level, args.per_level, args.max_tokens)
        out.append(r)
        print(
            f"{r['concurrency']:>5} {r['ok']:>5} {r['failed']:>5} {r['elapsed_s']:>8} "
            f"{r['rps']:>7} {r['ok_rps']:>7} {r['p50_s']:>6} {r['p95_s']:>6}"
        )
        if r["errors"]:
            for k, v in list(r["errors"].items())[:3]:
                print(f"        err x{v}: {k}")

    outp = "data/thinkboxmd/mercury_throughput_probe.json"
    os.makedirs(os.path.dirname(outp), exist_ok=True)
    with open(outp, "w") as fh:
        json.dump(out, fh, indent=2)
    print(f"\nwrote {outp}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
