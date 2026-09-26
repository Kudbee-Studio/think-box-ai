#!/usr/bin/env python3
"""Prove a Think Box actually runs against a real model on this machine.

Every check below can fail. Nothing is simulated:

1. model_reachable     one real call to the configured provider
2. governed_answer     a random multiplication goal, run through GovernedEngine
                       with a real token; the model's answer is checked
3. no_token_denied     a goal without a token is refused and never reaches the model
4. forged_token_denied a forged token is refused
5. ledger_verified     the on-disk ActionLedger hash chain verifies
6. tamper_detected     flipping one ledger row in a copy breaks verification

Provider selection uses the same env vars as ``thinkbox run``
(THINKBOX_DEFAULT_PROVIDER, THINKBOX_DEFAULT_MODEL, INCEPTION_API_KEY, ...)
or the flags below. Writes a JSON proof artifact and exits 0 only if every
check passes.

    python3 scripts/prove_think_box_local.py --model qwen2.5:1.5b
    THINKBOX_DEFAULT_PROVIDER=inception INCEPTION_API_KEY=... python3 scripts/prove_think_box_local.py
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import random
import re
import shutil
import sqlite3
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from thinkbox.engine import EngineConfig, ThinkBoxEngine  # noqa: E402
from thinkbox.governed import GovernedEngine, GovernedEngineConfig  # noqa: E402
from thinkbox.ledger import ActionLedger  # noqa: E402
from thinkbox.model_client import AsyncModelClient, ModelCallError, ModelConfig  # noqa: E402


def _check(name: str, ok: bool, **detail: Any) -> dict[str, Any]:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {json.dumps(detail, default=str)[:300]}")
    return {"check": name, "passed": ok, **detail}


def _numbers_in(text: str) -> list[int]:
    return [int(n) for n in re.findall(r"-?\d+", text.replace(",", ""))]


async def _prove(cfg: ModelConfig, ledger_path: Path) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []

    t0 = time.monotonic()
    try:
        reply = await AsyncModelClient(cfg).generate("Reply with exactly: OK", max_tokens=cfg.max_tokens)
        checks.append(_check("model_reachable", True, latency_s=round(time.monotonic() - t0, 3), reply=reply.strip()[:80]))
    except ModelCallError as exc:
        checks.append(_check("model_reachable", False, error=str(exc)))
        return checks

    engine = ThinkBoxEngine(EngineConfig(model_config=cfg, speculative=False))
    governed = GovernedEngine(GovernedEngineConfig(engine=engine, ledger_path=str(ledger_path)))
    token = governed.register_agent("prover", ["goal:execute"])

    a, b = random.randint(11, 99), random.randint(11, 99)
    goal = f"What is {a} * {b}? Reply with only the number."
    t0 = time.monotonic()
    result = await governed.execute_goal(goal, token_value=token, agent_id="prover")
    outputs = [t["output"] for t in result.get("tasks", []) if t.get("success")]
    correct = any(a * b in _numbers_in(o) for o in outputs)
    checks.append(_check(
        "governed_answer", bool(outputs) and correct,
        goal=goal, expected=a * b, outputs=outputs,
        task_errors=[t["output"] for t in result.get("tasks", []) if not t.get("success")],
        latency_s=round(time.monotonic() - t0, 3),
    ))

    calls_before = len(engine.swarm.results)
    denied = await governed.execute_goal("What is 2 + 2?")
    checks.append(_check(
        "no_token_denied",
        denied.get("governed") is False and len(engine.swarm.results) == calls_before,
        reason=denied.get("reason"),
    ))

    forged = await governed.execute_goal("What is 2 + 2?", token_value="govt.forged", agent_id="prover")
    checks.append(_check(
        "forged_token_denied",
        forged.get("governed") is False and len(engine.swarm.results) == calls_before,
        reason=forged.get("reason"),
    ))

    entries = governed.ledger.entries()
    checks.append(_check("ledger_verified", governed.ledger.verify(), entries=len(entries), path=str(ledger_path)))

    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp) / "tampered.db"
        shutil.copy(ledger_path, copy)
        conn = sqlite3.connect(copy)
        conn.execute("UPDATE ledger SET allowed = 1 - allowed WHERE rowid = (SELECT MIN(rowid) FROM ledger)")
        conn.commit()
        conn.close()
        checks.append(_check("tamper_detected", ActionLedger(str(copy)).verify() is False))
    return checks


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--provider", choices=["ollama", "openai_compat", "inception"], default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--max-tokens", type=int, default=None)
    parser.add_argument("--out-dir", default=str(ROOT / "data" / "proofs"), help="Where to write the proof JSON")
    args = parser.parse_args(argv)

    try:
        cfg = ModelConfig.from_env(api_type=args.provider, model=args.model, base_url=args.base_url,
                                   max_tokens=args.max_tokens)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    ledger_path = out_dir / f"local_proof_ledger_{stamp}.db"
    print(f"Provider: {cfg.api_type} @ {cfg.base_url}  model={cfg.model}")

    checks = asyncio.run(_prove(cfg, ledger_path))
    passed = bool(checks) and all(c["passed"] for c in checks) and len(checks) == 6
    artifact = {
        "kind": "think_box_local_proof",
        "created_at": stamp,
        "provider": cfg.api_type,
        "base_url": cfg.base_url,
        "model": cfg.model,
        "live_model_called": any(c["check"] == "model_reachable" and c["passed"] for c in checks),
        "all_passed": passed,
        "evidence_label": "verified" if passed else "failed",
        "checks": checks,
        "ledger_path": str(ledger_path),
        "not_checked": [
            "Upstash Vector memory",
            "Upstash Box remote execution",
            "UpCloud",
            "multi-agent swarm at scale",
        ],
    }
    body = json.dumps(artifact, indent=2, default=str, sort_keys=True)
    proof_path = out_dir / f"local_proof_{stamp}.json"
    proof_path.write_text(body, encoding="utf-8")
    print(f"\nproof: {proof_path}\nsha256: {hashlib.sha256(body.encode()).hexdigest()}")
    print("RESULT:", "ALL CHECKS PASSED" if passed else "FAILED")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
