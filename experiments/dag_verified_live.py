"""Bounded live validation: DAG-level verified execution through the REAL
ThinkBoxEngine.execute_goal lifecycle, GovernedEngine.execute_verified_goal,
and the canonical execute_verified_task / VerifiedRetrySession primitive.

Fresh task instances. Standard v2 task families (no manufactured failures).
Real Mercury-2 via the existing openai_compat path. Bounded: hard call
budget + max 1 retry per task. Reports raw execution facts only — no
invented intelligence score.

Usage: python3 experiments/dag_verified_live.py
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
from thinkbox.engine import ThinkBoxEngine  # noqa: E402
from thinkbox.experiment import ExperimentManager  # noqa: E402
from thinkbox.governed import GovernedEngine, GovernedEngineConfig  # noqa: E402
from thinkbox.pop_arena import system_prompt_for_v2  # noqa: E402

BASE_URL = "https://api.inceptionlabs.ai/v1"
MODEL = "mercury-2"
LEDGER_DB = str(ROOT / "data" / "thinkboxmd" / "db" / "ledger.db")
MAX_CALLS = 10  # hard session budget across the whole DAG
SYSTEM_PROMPT = "You reply with exactly one JSON object and nothing else."

SUBTASKS = [
    ("compute", "add_carry", []),
    ("distractor", "wrongkey", []),
    ("multifield", "double", []),
    ("distractor", "apology", [0, 1]),
]


def build_subtasks() -> list[dict]:
    out = []
    for family, variant, deps in SUBTASKS:
        prompt, spec = system_prompt_for_v2(family, variant)
        out.append({
            "description": prompt,
            "family": family,
            "variant": variant,
            "spec": spec,
            "depends_on": deps,
        })
    return out


async def main() -> int:
    key = os.environ.get("INCEPTION_API_KEY", "")
    if not key:
        print("INCEPTION_API_KEY missing — refusing to start")
        return 2
    provider = OpenAICompatProvider({"api_key": key, "model": MODEL, "base_url": BASE_URL})
    calls = {"n": 0}

    async def complete_async(prompt: str):
        calls["n"] += 1
        if calls["n"] > MAX_CALLS + 2:
            raise RuntimeError("call guard tripped")
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
        print(f"  call {calls['n']}: {latency}s chars={len(text)} "
              f"sha={hashlib.sha256(text.encode()).hexdigest()[:12]} tokens={usage.get('total_tokens')}")
        return text, usage

    engine = ThinkBoxEngine()
    gov = GovernedEngine(GovernedEngineConfig(engine=engine, ledger_path=LEDGER_DB))
    token = gov.register_agent("dag-live-agent", ["goal:execute"])
    manager = ExperimentManager()

    print(f"live DAG run: {len(SUBTASKS)} tasks, max_calls={MAX_CALLS}, model={MODEL}")
    summary = await gov.execute_verified_goal(
        goal="dag-live: verified DAG execution proof (fresh instances, bounded budget)",
        subtasks=build_subtasks(),
        complete_async=complete_async,
        token_value=token,
        agent_id="dag-live-agent",
        max_calls=MAX_CALLS,
        manager=manager,
        emit_dashboard=True,
    )

    v = summary.get("verified", {})
    print(json.dumps({
        "governed": summary.get("governed"),
        "session_id": summary.get("session_id"),
        "goal_experiment_id": summary.get("goal_experiment_id"),
        "task_experiment_ids": summary.get("task_experiment_ids"),
        "tasks": v.get("tasks"),
        "first_try_successes": v.get("first_try_successes"),
        "recovered_successes": v.get("recovered_successes"),
        "failures": v.get("failures"),
        "budget_exhausted": v.get("budget_exhausted"),
        "retries": v.get("retries"),
        "verification_rate": v.get("verification_rate"),
        "calls_spent": summary.get("calls_spent"),
        "budget_remaining": summary.get("budget_remaining"),
        "per_task": v.get("per_task"),
        "ledger_verified": gov.ledger.verify(),
        "proof_artifact": summary.get("proof_artifact"),
        "proof_sha256": summary.get("proof_sha256"),
        "total_time_ms": summary.get("total_time_ms"),
        "live_calls_observed": calls["n"],
    }, indent=2, sort_keys=True))

    from core.memory.store import MemoryStore
    from core.memory.schema import MemoryEntry, MemoryEntryType, MemoryLayer
    mem = MemoryStore(str(ROOT / "data" / "thinkboxmd" / "db" / "memory.db"))
    mem.put(MemoryEntry(
        key="learn:dagpath:verified-goal",
        layer=MemoryLayer.TASK,
        entry_type=MemoryEntryType.PATTERN,
        value={
            "known": ("ThinkBoxEngine.execute_goal DAG tasks route through the canonical "
                      "GovernedEngine.execute_verified_task primitive with shared bounded "
                      "session budget; parent aggregation preserves failure/recovery provenance"),
            "unknown": "large-DAG scaling; multi-goal concurrent budgets",
        },
        agent_id="dag-live-agent",
        task_id=summary.get("goal_experiment_id", ""),
        metadata={"source": "dag_verified_live", "proof": summary.get("proof_artifact", "")},
        confidence=0.9,
    ))
    mem.close()
    print("memory: learn:dagpath:verified-goal written")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
