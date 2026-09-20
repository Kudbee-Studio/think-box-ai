"""Live experiment: Upstash Box substrate + Inception Mercury-2 throughput (v2).

Enhanced with:
- Configurable parameters (concurrency levels, calls, iterations)
- Multiple iterations per level for statistical significance
- Results persisted via ExperimentManager
- Comparison with previous runs

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
MODEL = os.environ.get("BOX_MERCURY_MODEL", "mercury-2")
HARD_CALL_GUARD = 32
CONCURRENCY_LEVELS = [int(x) for x in os.environ.get("BOX_MERCURY_LEVELS", "1,4,8,16").split(",")]
CALLS_PER_LEVEL = int(os.environ.get("BOX_MERCURY_CALLS", "4"))
ITERATIONS = int(os.environ.get("BOX_MERCURY_ITERATIONS", "3"))
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


def _load_previous_results(artifacts_dir: Path) -> list[dict[str, Any]]:
    results = []
    if not artifacts_dir.exists():
        return results
    for f in sorted(artifacts_dir.glob("box_mercury_live_*_summary.json")):
        try:
            data = json.loads(f.read_text())
            results.append(data)
        except (json.JSONDecodeError, OSError):
            continue
    return results


def _compare_with_previous(current: dict[str, Any], previous: list[dict[str, Any]]) -> dict[str, Any]:
    if not previous:
        return {"comparison": "no_previous_runs", "improvement": None}

    last = previous[-1]
    current_agg = current.get("aggregate", {})
    previous_agg = last.get("aggregate", {})

    comparison: dict[str, Any] = {
        "comparison": "vs_previous_run",
        "previous_timestamp": last.get("timestamp", ""),
    }

    current_throughput = current_agg.get("global_throughput_rps", 0)
    previous_throughput = previous_agg.get("global_throughput_rps", 0)
    if previous_throughput > 0:
        improvement = (current_throughput - previous_throughput) / previous_throughput * 100
        comparison["throughput_change_pct"] = round(improvement, 2)
        if improvement > 0:
            comparison["verdict"] = "improved"
        elif improvement < 0:
            comparison["verdict"] = "regressed"
        else:
            comparison["verdict"] = "same"
    else:
        comparison["verdict"] = "insufficient_previous_data"

    return comparison


async def run_iteration(
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
        "p95_latency": sorted(latencies)[int(len(latencies) * 0.95)] if latencies else 0,
        "p99_latency": sorted(latencies)[-1] if latencies else 0,
        "avg_latency": sum(latencies) / len(latencies) if latencies else 0,
        "std_latency": (sum((x - sum(latencies)/len(latencies))**2 for x in latencies) / len(latencies)) ** 0.5 if latencies else 0,
        "total_tokens": total_tokens,
        "rps": completed["n"] / (sum(latencies) / max(len(latencies), 1)) if latencies and completed["n"] > 0 and sum(latencies) > 0 else 0,
        "results": results,
    }


def _aggregate_iterations(level_results_list: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    aggregated = []
    for level_results in level_results_list:
        if not level_results:
            continue
        concurrency = level_results[0]["concurrency"]
        all_latencies = []
        all_completed = 0
        all_errors = 0
        all_tokens = 0
        for r in level_results:
            all_latencies.extend(r["latencies"])
            all_completed += r["completed"]
            all_errors += r["errors"]
            all_tokens += r["total_tokens"]
        sorted_lat = sorted(all_latencies)
        wall = sum(r["wall_s"] for r in level_results) if level_results else 0.001
        aggregated.append({
            "concurrency": concurrency,
            "iterations": len(level_results),
            "total_calls": all_completed,
            "total_errors": all_errors,
            "error_rate": all_errors / max(all_completed, 1),
            "p50_latency": sorted_lat[len(sorted_lat) // 2] if sorted_lat else 0,
            "p95_latency": sorted_lat[int(len(sorted_lat) * 0.95)] if sorted_lat else 0,
            "p99_latency": sorted_lat[-1] if sorted_lat else 0,
            "avg_latency": sum(all_latencies) / len(all_latencies) if all_latencies else 0,
            "std_latency": (sum((x - sum(all_latencies)/max(len(all_latencies),1))**2 for x in all_latencies) / max(len(all_latencies),1)) ** 0.5 if all_latencies else 0,
            "total_tokens": all_tokens,
            "wall_s": wall,
            "rps": all_completed / max(wall, 0.001),
        })
    return aggregated


async def main() -> int:
    from core.providers.openai_compat import OpenAICompatProvider
    from core.providers.base import Message

    key = os.environ["INCEPTION_API_KEY"]
    box_url = os.environ["UPSTASH_PUBLIC_BOX_URL"]

    print(f"substrate: {box_url}")
    print(f"model: {MODEL}")
    print(f"base_url: {BASE_URL}")
    print(f"concurrency levels: {CONCURRENCY_LEVELS}")
    print(f"calls per level: {CALLS_PER_LEVEL}")
    print(f"iterations: {ITERATIONS}")

    from thinkbox.substrate import detect_substrate, SubstrateProbe
    substrate = detect_substrate()
    probe = SubstrateProbe()
    report = probe.probe()
    print(f"detected substrate: {substrate}")
    print(f"vector_sync: {report.vector_sync}")

    provider = OpenAICompatProvider({"api_key": key, "model": MODEL, "base_url": BASE_URL})

    all_iterations_by_level: list[list[dict[str, Any]]] = []
    global_calls = {"n": 0}

    for level in CONCURRENCY_LEVELS:
        print(f"\n--- Concurrency {level} ({ITERATIONS} iterations × {CALLS_PER_LEVEL} calls) ---")
        level_iterations = []
        for iteration in range(ITERATIONS):
            semaphore = asyncio.Semaphore(level)
            t0 = time.monotonic()
            result = await run_iteration(provider, semaphore, level, CALLS_PER_LEVEL)
            wall = round(time.monotonic() - t0, 3)
            result["wall_s"] = wall
            result["iteration"] = iteration
            level_iterations.append(result)
            global_calls["n"] += CALLS_PER_LEVEL
            print(f"  iter {iteration}: completed={result['completed']} errors={result['errors']} "
                  f"p50={result['p50_latency']}s p95={result['p95_latency']}s rps={result['rps']:.1f}")
        all_iterations_by_level.append(level_iterations)

    aggregated = _aggregate_iterations(all_iterations_by_level)

    all_latencies = [r["latency_s"] for lr in all_iterations_by_level for r in lr if r["latency_s"] is not None]
    all_errors = sum(r["total_errors"] for r in aggregated)
    all_completed = sum(r["total_calls"] for r in aggregated)

    proof = {
        "experiment": "box-mercury-live-v2",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "substrate": substrate,
        "box_url": box_url,
        "model": MODEL,
        "provider": "openai_compat",
        "base_url": BASE_URL,
        "config": {
            "concurrency_levels": CONCURRENCY_LEVELS,
            "calls_per_level": CALLS_PER_LEVEL,
            "iterations": ITERATIONS,
        },
        "global_calls": global_calls["n"],
        "hard_call_guard": HARD_CALL_GUARD,
        "substrate_report": report.to_dict(),
        "aggregated_results": aggregated,
        "all_iterations": [
            {
                "concurrency": r["concurrency"],
                "iteration": r["iteration"],
                "completed": r["completed"],
                "errors": r["errors"],
                "p50_latency": r["p50_latency"],
                "p95_latency": r["p95_latency"],
                "p99_latency": r["p99_latency"],
                "avg_latency": r["avg_latency"],
                "std_latency": r["std_latency"],
                "wall_s": r["wall_s"],
                "total_tokens": r["total_tokens"],
                "rps": round(r["rps"], 2),
            }
            for lr in all_iterations_by_level
            for r in lr
        ],
        "aggregate": {
            "total_calls": all_completed,
            "total_errors": all_errors,
            "error_rate": all_errors / max(all_completed, 1),
            "global_p50_latency": sorted(all_latencies)[len(all_latencies) // 2] if all_latencies else 0,
            "global_p95_latency": sorted(all_latencies)[int(len(all_latencies) * 0.95)] if all_latencies else 0,
            "global_p99_latency": sorted(all_latencies)[-1] if all_latencies else 0,
            "global_avg_latency": sum(all_latencies) / len(all_latencies) if all_latencies else 0,
            "global_throughput_rps": all_completed / max(sum(r["wall_s"] for r in aggregated), 0.001),
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
    summary_path = artifacts_dir / f"box_mercury_live_{ts}_summary.json"
    summary_path.write_text(json.dumps(proof, indent=2, sort_keys=True, default=str))
    print(f"\nproof: {summary_path}")
    print(f"proof_sha256: {proof_hash}")

    previous = _load_previous_results(artifacts_dir)
    comparison = _compare_with_previous(proof, previous)
    print(f"comparison: {comparison.get('verdict', 'no_previous')}")
    if comparison.get("throughput_change_pct") is not None:
        print(f"throughput change: {comparison['throughput_change_pct']:+.1f}%")

    try:
        from thinkbox.dashboard_state import get_dashboard_state, DashboardCategory, DashboardEvent
        import asyncio as _asyncio

        async def _emit() -> None:
            ds = get_dashboard_state()
            await ds.emit(
                DashboardCategory.EXECUTION,
                DashboardEvent.TASK_COMPLETED,
                {
                    "experiment": "box-mercury-live-v2",
                    "substrate": substrate,
                    "model": MODEL,
                    "global_calls": global_calls["n"],
                    "proof_sha256": proof_hash,
                    "box_url": box_url,
                    "iterations": ITERATIONS,
                },
                "box_mercury_live_v2",
                evidence_label="verified",
            )
        _asyncio.run(_emit())
        print("dashboard: emitted")
    except Exception as e:
        print(f"dashboard: emit skipped ({e})")

    print(f"\n=== SUMMARY ===")
    print(f"Substrate: {substrate}")
    print(f"Model: {MODEL}")
    print(f"Iterations per level: {ITERATIONS}")
    print(f"Total calls: {global_calls['n']}")
    print(f"Errors: {all_errors}")
    print(f"Error rate: {all_errors/max(all_completed,1)*100:.1f}%")
    print(f"P50 latency: {sorted(all_latencies)[len(all_latencies)//2] if all_latencies else 0}s")
    print(f"P95 latency: {sorted(all_latencies)[int(len(all_latencies)*0.95)] if all_latencies else 0}s")
    print(f"Throughput: {all_completed/max(sum(r['wall_s'] for r in aggregated),0.001):.1f} rps")
    print(f"Proof: {proof_hash[:16]}")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
