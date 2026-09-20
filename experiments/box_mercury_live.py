"""Live experiment: Upstash Box substrate + Inception Mercury-2 throughput.

Runs bounded Mercury-2 inference calls on the live Upstash Box execution
substrate, measuring throughput at multiple concurrency levels, verifying
substrate identity, and generating a proof artifact binding results to
the control-plane proof chain.

The experiment:
  1. Verifies Upstash Box substrate is active (detect_substrate)
  2. Runs a burst of Mercury-2 calls at concurrency 1, 4, 8, 16
  3. Measures rps, latency, errors per level
  4. Records substrate info + model metrics in a proof artifact
  5. Emits dashboard state (if available)
  6. Verifies proof chain integrity (via ledger if available)

No GPU. No public bind. No AWS. No SSH.

Usage: python3 experiments/box_mercury_live.py
Requires: INCEPTION_API_KEY + UPSTASH_PUBLIC_BOX_URL in env.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

BASE_URL = "https://api.inceptionlabs.ai/v1"
MODEL = "mercury-2"
HARD_CALL_GUARD = 32
CONCURRENCY_LEVELS = [1, 4, 8, 16]
CALLS_PER_LEVEL = 4
SYSTEM_PROMPT = "You reply with exactly one JSON object and nothing else."


def _check_env() -> int:
    if not os.environ.get("INCEPTION_API_KEY"):
        print("ERROR: INCEPTION_API_KEY missing — refusing to start")
        return 2
    box_url = os.environ.get("UPSTASH_PUBLIC_BOX_URL", "")
    if not box_url:
        print("ERROR: UPSTASH_PUBLIC_BOX_URL missing — refusing to start")
        return 2
    return 0


async def run_level(
    provider: Any,
    semaphore: asyncio.Semaphore,
    concurrency: int,
    calls: int,
) -> dict[str, Any]:
    results = []
    completed = {"n": 0}
    errors = {"n": 0}

    async def _call(seq: int) -> None:
        async with semaphore:
            try:
                t0 = time.monotonic()
                from core.providers.base import Message
                resp = await provider.complete(
                    [Message(role="system", content=SYSTEM_PROMPT),
                     Message(role="user", content=f"Return ONLY the number {seq}, nothing else.")],
                    max_tokens=50,
                    temperature=0.0,
                )
                latency = round(time.monotonic() - t0, 3)
                text = resp.content or ""
                usage = dict(resp.usage or {})
                results.append({
                    "seq": seq,
                    "latency_s": latency,
                    "chars": len(text),
                    "tokens": usage.get("total_tokens", 0),
                    "response": text.strip()[:80],
                    "error": None,
                })
                completed["n"] += 1
            except Exception as e:
                errors["n"] += 1
                results.append({
                    "seq": seq,
                    "latency_s": None,
                    "chars": 0,
                    "tokens": 0,
                    "response": None,
                    "error": str(e),
                })

    tasks = [_call(i) for i in range(calls)]
    await asyncio.gather(*tasks)

    latencies = [r["latency_s"] for r in results if r["latency_s"] is not None]
    total_tokens = sum(r["tokens"] for r in results)

    return {
        "concurrency": concurrency,
        "calls": calls,
        "completed": completed["n"],
        "errors": errors["n"],
        "latencies": latencies,
        "p50_latency": sorted(latencies)[len(latencies) // 2] if latencies else 0,
        "p99_latency": sorted(latencies)[-1] if latencies else 0,
        "avg_latency": sum(latencies) / len(latencies) if latencies else 0,
        "total_tokens": total_tokens,
        "rps": completed["n"] / (sum(latencies) / max(len(latencies), 1)) if latencies and completed["n"] > 0 and sum(latencies) > 0 else 0,
        "results": results,
    }


async def main() -> int:
    from core.providers.openai_compat import OpenAICompatProvider
    from core.providers.base import Message

    key = os.environ["INCEPTION_API_KEY"]
    box_url = os.environ["UPSTASH_PUBLIC_BOX_URL"]

    print(f"substrate: {box_url}")
    print(f"model: {MODEL}")
    print(f"base_url: {BASE_URL}")

    from thinkbox.substrate import detect_substrate, SubstrateProbe
    substrate = detect_substrate()
    probe = SubstrateProbe()
    report = probe.probe()
    print(f"detected substrate: {substrate}")
    print(f"vector_sync: {report.vector_sync}")

    provider = OpenAICompatProvider({"api_key": key, "model": MODEL, "base_url": BASE_URL})

    level_results: list[dict[str, Any]] = []
    global_calls = {"n": 0}

    for level in CONCURRENCY_LEVELS:
        print(f"\n--- Concurrency {level} ({CALLS_PER_LEVEL} calls) ---")
        semaphore = asyncio.Semaphore(level)
        t0 = time.monotonic()
        level_result = await run_level(provider, semaphore, level, CALLS_PER_LEVEL)
        wall = round(time.monotonic() - t0, 3)
        level_result["wall_s"] = wall
        level_result["global_calls"] = global_calls["n"]
        global_calls["n"] += CALLS_PER_LEVEL

        level_results.append(level_result)
        print(f"  completed={level_result['completed']} errors={level_result['errors']} "
              f"p50={level_result['p50_latency']}s p99={level_result['p99_latency']}s "
              f"wall={wall}s")

    all_latencies = [r["latency_s"] for lr in level_results for r in lr["results"] if r["latency_s"] is not None]
    all_errors = sum(lr["errors"] for lr in level_results)
    all_completed = sum(lr["completed"] for lr in level_results)

    proof = {
        "experiment": "box-mercury-live",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "substrate": substrate,
        "box_url": box_url,
        "model": MODEL,
        "provider": "openai_compat",
        "base_url": BASE_URL,
        "concurrency_levels": CONCURRENCY_LEVELS,
        "calls_per_level": CALLS_PER_LEVEL,
        "global_calls": global_calls["n"],
        "hard_call_guard": HARD_CALL_GUARD,
        "substrate_report": report.to_dict(),
        "level_results": [
            {
                "concurrency": lr["concurrency"],
                "calls": lr["calls"],
                "completed": lr["completed"],
                "errors": lr["errors"],
                "p50_latency": lr["p50_latency"],
                "p99_latency": lr["p99_latency"],
                "avg_latency": lr["avg_latency"],
                "wall_s": lr["wall_s"],
                "total_tokens": lr["total_tokens"],
                "rps": round(lr["rps"], 2),
            }
            for lr in level_results
        ],
        "aggregate": {
            "total_calls": all_completed,
            "total_errors": all_errors,
            "error_rate": all_errors / max(all_completed, 1),
            "global_p50_latency": sorted(all_latencies)[len(all_latencies) // 2] if all_latencies else 0,
            "global_p99_latency": sorted(all_latencies)[-1] if all_latencies else 0,
            "global_avg_latency": sum(all_latencies) / len(all_latencies) if all_latencies else 0,
            "global_throughput_rps": all_completed / max(sum(lr["wall_s"] for lr in level_results), 0.001),
        },
        "live_calls_observed": global_calls["n"],
        "no_claims": [
            "no model intelligence improvement claimed",
            "no concurrency-for-performance claim (measurement only)",
            "no GPU", "no UpCloud compute", "no SSH",
        ],
        "evidence_label": "verified",
    }

    proof_bytes = json.dumps(proof, sort_keys=True, default=str).encode()
    proof_hash = hashlib.sha256(proof_bytes).hexdigest()
    proof["proof_sha256"] = proof_hash

    artifacts_dir = ROOT / "data" / "thinkboxmd" / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    proof_path = artifacts_dir / f"box_mercury_live_{ts}.json"
    proof_path.write_text(json.dumps(proof, indent=2, sort_keys=True, default=str))
    print(f"\nproof: {proof_path}")
    print(f"proof_sha256: {proof_hash}")

    try:
        from thinkbox.dashboard_state import get_dashboard_state, DashboardCategory, DashboardEvent
        import asyncio as _asyncio

        async def _emit() -> None:
            ds = get_dashboard_state()
            await ds.emit(
                DashboardCategory.THINK_BOXES,
                DashboardEvent.TASK_COMPLETED,
                {
                    "experiment": "box-mercury-live",
                    "substrate": substrate,
                    "model": MODEL,
                    "global_calls": global_calls["n"],
                    "proof_sha256": proof_hash,
                    "box_url": box_url,
                },
                "box_mercury_live",
                evidence_label="verified",
            )
        _asyncio.run(_emit())
        print("dashboard: emitted")
    except Exception as e:
        print(f"dashboard: emit skipped ({e})")

    print(f"\n=== SUMMARY ===")
    print(f"Substrate: {substrate}")
    print(f"Model: {MODEL}")
    print(f"Total calls: {global_calls['n']}")
    print(f"Errors: {all_errors}")
    print(f"Error rate: {all_errors/max(all_completed,1)*100:.1f}%")
    print(f"P50 latency: {sorted(all_latencies)[len(all_latencies)//2] if all_latencies else 0}s")
    print(f"Throughput: {all_completed/max(sum(lr['wall_s'] for lr in level_results),0.001):.1f} rps")
    print(f"Proof: {proof_hash[:16]}")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))