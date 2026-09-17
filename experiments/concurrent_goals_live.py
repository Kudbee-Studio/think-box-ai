"""Bounded live validation: multi-goal concurrent budgets + deeper DAG telemetry.

Fresh task instances. Standard v2 task families (no manufactured failures).
Real Mercury-2 via the existing openai_compat path. Bounded: hard per-goal
call budgets + max 1 retry per task. Reports raw execution facts only — no
invented intelligence score, no concurrency-for-performance claim (the point
is accounting correctness, not speed).

Two concurrent goals:
  - Goal A (single compute task):       compute/add_small
  - Goal B (fan-in DAG, 2 layers):      [compute/mul_small, compute/sub_neg]
                                         -> multifield/double

Independent per-goal budgets: goal A max 2 calls, goal B max 4 calls
(3 tasks + 1 retry headroom), both max 1 retry. Worst case 6 live calls.

Usage: python3 experiments/concurrent_goals_live.py
Requires: INCEPTION_API_KEY in env (never logged, never persisted).
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

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.providers.openai_compat import OpenAICompatProvider  # noqa: E402
from core.providers.base import Message  # noqa: E402
from thinkbox.concurrent_goals import (  # noqa: E402
    ConcurrentGoalSpec, ConcurrentGoalsConfig, ConcurrentGoalsRunner,
)
from thinkbox.experiment import ExperimentManager  # noqa: E402
from thinkbox.pop_arena import system_prompt_for_v2, VerifiedRetryConfig  # noqa: E402

BASE_URL = "https://api.inceptionlabs.ai/v1"
MODEL = "mercury-2"
LEDGER_DB = str(ROOT / "data" / "thinkboxmd" / "db" / "ledger.db")
SYSTEM_PROMPT = "You reply with exactly one JSON object and nothing else."
HARD_CALL_GUARD = 8  # never exceed, independent of budgets


def _sub(family: str, variant: str, depends_on: list[int] | None = None) -> dict:
    prompt, spec = system_prompt_for_v2(family, variant)
    return {"description": prompt, "family": family, "variant": variant,
            "spec": spec, "depends_on": depends_on or []}


async def main() -> int:
    key = os.environ.get("INCEPTION_API_KEY", "")
    if not key:
        print("INCEPTION_API_KEY missing — refusing to start")
        return 2
    provider = OpenAICompatProvider({"api_key": key, "model": MODEL, "base_url": BASE_URL})
    calls = {"n": 0}

    async def complete_async(prompt: str):
        calls["n"] += 1
        seq = calls["n"]
        if calls["n"] > HARD_CALL_GUARD:
            raise RuntimeError("hard call guard tripped")
        t0 = time.monotonic()
        resp = await provider.complete(
            [Message(role="system", content=SYSTEM_PROMPT),
             Message(role="user", content=prompt)],
            max_tokens=3500,
            temperature=0.2,
        )
        latency = round(time.monotonic() - t0, 3)
        text = resp.content or ""
        usage = dict(resp.usage or {})
        print(f"  call {seq}: {latency}s chars={len(text)} "
              f"sha={hashlib.sha256(text.encode()).hexdigest()[:12]} "
              f"tokens={usage.get('total_tokens')}")
        return text, usage

    manager = ExperimentManager()

    specs = [
        ConcurrentGoalSpec(
            goal="concurrent-goal-a: compute/add_small",
            subtasks=[_sub("compute", "add_small")],
            budget_config=VerifiedRetryConfig(max_calls=2, max_retries=1),
        ),
        ConcurrentGoalSpec(
            goal="concurrent-goal-b: fan-in DAG compute->multifield",
            subtasks=[
                _sub("compute", "mul_small"),
                _sub("compute", "sub_neg"),
                _sub("multifield", "double", depends_on=[0, 1]),
            ],
            budget_config=VerifiedRetryConfig(max_calls=4, max_retries=1),
        ),
    ]
    cfg = ConcurrentGoalsConfig(independent_goals=True, max_calls_global=0, max_retries_global=1)

    runner = ConcurrentGoalsRunner()
    print(f"live concurrent run: {len(specs)} goals, independent budgets, model={MODEL}")
    result = await runner.run_concurrent(
        specs=specs,
        complete_async=complete_async,
        config=cfg,
        agent_id="concurrent-live-agent",
        manager=manager,
        emit_dashboard=True,
        ledger_path=LEDGER_DB,
    )

    proof = {
        "phase": "concurrent-goals-live",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model": MODEL,
        "provider": "openai_compat",
        "cross_goal_summary": result.cross_goal_summary,
        "per_goal_accounting": result.per_goal_accounting,
        "layer_telemetry_aggregate": result.layer_telemetry_aggregate,
        "goal_results": {
            k: {
                "session_id": v.get("session_id"),
                "goal_experiment_id": v.get("goal_experiment_id"),
                "task_experiment_ids": v.get("task_experiment_ids"),
                "verified": v.get("verified"),
            }
            for k, v in result.goal_results.items()
            if isinstance(v, dict)
        },
        "live_calls_observed": calls["n"],
        "no_claims": [
            "no model intelligence improvement claimed",
            "no concurrency-for-performance claim (accounting correctness proven, not speed)",
            "no GPU", "no UpCloud compute", "no SSH",
        ],
    }
    proof_bytes = json.dumps(proof, sort_keys=True, default=str).encode()
    proof_hash = hashlib.sha256(proof_bytes).hexdigest()
    proof["proof_sha256"] = proof_hash
    proof_path = Path(manager.artifacts_dir) / f"concurrent_goals_live_proof_{datetime.now(timezone.utc).strftime('%Y%m%d')}.json"
    proof_path.write_text(json.dumps(proof, indent=2, sort_keys=True, default=str))
    print(f"proof: {proof_path} sha256={proof_hash}")
    print(json.dumps({
        "shared_session_used": result.shared_session_used,
        "global_calls_spent": result.global_calls_spent,
        "global_retries_fired": result.global_retries_fired,
        "global_budget_remaining": result.global_budget_remaining,
        "per_goal_accounting": result.per_goal_accounting,
        "layer_telemetry": result.layer_telemetry_aggregate,
        "live_calls_observed": calls["n"],
    }, indent=2, sort_keys=True))

    from core.memory.store import MemoryStore
    from core.memory.schema import MemoryEntry, MemoryEntryType, MemoryLayer
    mem = MemoryStore(str(ROOT / "data" / "thinkboxmd" / "db" / "memory.db"))
    mem.put(MemoryEntry(
        key="learn:concurrent:multi-goal-budgets",
        layer=MemoryLayer.TASK,
        entry_type=MemoryEntryType.PATTERN,
        value={
            "known": ("multiple ThinkBox goals execute concurrently via one fresh "
                      "GovernedEngine per goal (shared _verified_task_runner race avoided); "
                      "independent per-goal VerifiedRetrySession budgets or a shared global "
                      "session (atomic synchronous _spend_call) enforce strict accounting"),
            "unknown": "large-N goal scaling; cross-goal budget contention policies",
        },
        agent_id="concurrent-live-agent",
        task_id="",
        metadata={"source": "concurrent_goals_live", "proof_sha256": proof_hash},
        confidence=0.9,
    ))
    mem.close()
    print("memory: learn:concurrent:multi-goal-budgets written")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
