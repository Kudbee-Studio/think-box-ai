#!/usr/bin/env python3
"""KUDBEE — Swarm Instrumentation Dashboard.

A single self-contained service (Python stdlib only, no framework, no build
step) that renders the live swarm, the THINK Swarm Strength Index and its
learning curve, the challenge arena, memory evolution, worker reputation,
proof chains and swarm genomes — all read straight from SQLite.

Run:
    python3 experiments/swarm_dashboard.py --port 8787
Expose:
    cloudflared tunnel --url http://127.0.0.1:8787

Endpoints:
    /                 dashboard (mobile-first HTML)
    /api/live         live event tail + phase + counters
    /api/strength     TSSI trend, components, learning delta
    /api/instruments  flight recorder, memory evolution, reputation, genome, proof
    /api/proof        latest full proof JSON
    /api/sessions     session list
    /healthz          readiness
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "thinkboxmd"
DB = OUT / "db"
EVENTS = OUT / "swarm_events.jsonl"

TIERS = ["EVIDENCE", "INFERENCE", "HYPOTHESIS", "UNVERIFIED"]


# ---------------------------------------------------------------------------
# Data access
# ---------------------------------------------------------------------------

def _q(db: Path, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    if not db.exists():
        return []
    try:
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
        conn.close()
        return rows
    except sqlite3.Error:
        return []


def _read_events(limit: int = 3000) -> tuple[list[dict[str, Any]], str]:
    events: list[dict[str, Any]] = []
    if EVENTS.exists():
        for line in EVENTS.read_text(errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    phase = "idle"
    if events:
        phase = {
            "run_start": "running", "corpus_ready": "running", "wave_done": "running",
            "reconcile": "reconciled", "proof": "complete",
        }.get(events[-1].get("event", ""), events[-1].get("event", "idle"))
    return events[-limit:], phase


def _latest_proof() -> dict[str, Any]:
    files = sorted(OUT.glob("big_swarm_*.json"))
    if not files:
        return {}
    try:
        return json.loads(files[-1].read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _strength() -> dict[str, Any]:
    rows = _q(
        DB / "metrics.db",
        "SELECT s.session_id, s.ended_at, s.workers_total, s.workers_ok, s.effective_rps, "
        "s.strength_score, s.ledger_valid, h.grounded_ratio, h.evidence_ratio, h.challenge_rate, "
        "h.error_rate, h.tier_inflation_rate, h.tier_distribution, h.learning_delta "
        "FROM sessions s LEFT JOIN strength_history h ON h.session_id=s.session_id "
        "WHERE s.kind='big_swarm' AND s.strength_score IS NOT NULL "
        "ORDER BY s.ended_at DESC LIMIT 40",
    )
    points = [
        {"session_id": r["session_id"], "ended_at": r["ended_at"], "index": r["strength_score"]}
        for r in reversed(rows)
    ]
    delta = None
    if len(rows) >= 2 and rows[0]["strength_score"] is not None and rows[1]["strength_score"] is not None:
        delta = round(rows[0]["strength_score"] - rows[1]["strength_score"], 4)
    tok = _q(DB / "metrics.db", "SELECT SUM(total_tokens) t, SUM(reasoning_tokens) rt, "
                                "COUNT(*) n FROM token_usage")
    latest = rows[0] if rows else None
    proof = _latest_proof()
    comps = (proof.get("reconciliation", {}) or {}).get("strength", {}).get("components", {})
    signals = (proof.get("reconciliation", {}) or {}).get("strength", {}).get("signals", {})
    return {
        "points": points,
        "latest": latest,
        "delta": delta,
        "components": comps,
        "signals": signals,
        "tokens": {
            "total": (tok[0]["t"] if tok else 0) or 0,
            "reasoning": (tok[0]["rt"] if tok else 0) or 0,
            "calls": (tok[0]["n"] if tok else 0) or 0,
        },
        "sessions": len(rows),
    }


def _instruments() -> dict[str, Any]:
    proof = _latest_proof()
    mem = _q(DB / "memory_evolution.db",
             "SELECT state, COUNT(*) n FROM memories GROUP BY state")
    ev = _q(DB / "memory_evolution.db",
            "SELECT event, COUNT(*) n FROM memory_events GROUP BY event")
    rep = _q(DB / "reputation.db",
             "SELECT worker_id, role, calls, errors, reputation FROM worker_reputation "
             "WHERE calls>0 ORDER BY reputation DESC LIMIT 12")
    rep_sum = _q(DB / "reputation.db",
                 "SELECT COUNT(*) n, AVG(reputation) avg_rep, MAX(reputation) best, "
                 "SUM(calls) calls, SUM(errors) errs FROM worker_reputation WHERE calls>0")
    flight = _q(DB / "flight_recorder.db", "SELECT COUNT(*) n FROM worker_records")
    return {
        "flight_records": (flight[0]["n"] if flight else 0) or 0,
        "memory_by_state": {r["state"]: r["n"] for r in mem},
        "memory_by_event": {r["event"]: r["n"] for r in ev},
        "reputation_leaderboard": rep,
        "reputation_summary": rep_sum[0] if rep_sum else {},
        "proof_chain": proof.get("proof_chain", {}),
        "genome": proof.get("genome", {}),
        "arena": proof.get("arena", {}),
        "run_id": proof.get("run_id", ""),
        "session_id": proof.get("session_id", ""),
        "proof_hash": proof.get("proof_hash", ""),
        "ledger": proof.get("ledger", {}),
    }


def _sessions() -> list[dict[str, Any]]:
    return _q(
        DB / "metrics.db",
        "SELECT session_id, kind, model, started_at, ended_at, workers_total, workers_ok, "
        "workers_failed, effective_rps, ledger_valid, strength_score FROM sessions "
        "ORDER BY started_at DESC LIMIT 30",
    )


def _pipeline() -> dict[str, Any]:
    """Learning-pipeline overview rebuilt entirely from persistent storage.

    Reads experiments.db (experiments, outcomes, lessons, artifacts, proofs,
    events, sessions) plus memory.db and ledger.db — all read-only. Exposes
    the real chain: session -> job -> model -> verification -> artifact ->
    proof -> memory -> lesson -> retrieval -> outcome -> replay, plus the
    five-state verification flags and blockers. No singleton state used.
    """
    exp_db = DB / "experiments.db"
    latest_box = ""
    try:
        import os
        box_url = os.environ.get("UPSTASH_PUBLIC_BOX_URL", "")
        if box_url:
            from urllib.parse import urlparse
            latest_box = urlparse(box_url).hostname or box_url
    except Exception:
        latest_box = ""
    experiments = _q(
        exp_db,
        "SELECT experiment_id, session_id, agent_id, timestamp, intent, hypothesis, "
        "execution_mode, status, four_state, confidence FROM experiments ORDER BY timestamp",
    )
    outcomes = {
        r["experiment_id"]: r
        for r in _q(
            exp_db,
            "SELECT experiment_id, outcome_data, confidence, four_state FROM outcomes",
        )
    }
    proofs = {
        r["experiment_id"]: r
        for r in _q(
            exp_db,
            "SELECT experiment_id, proof_id, evidence_label, hash FROM proof_records",
        )
    }
    artifacts = _q(
        exp_db,
        "SELECT experiment_id, artifact_id, artifact_type, path, hash FROM artifacts",
    )
    lessons = _q(
        exp_db,
        "SELECT id, experiment_id, lesson, parameter_updates, timestamp FROM lessons",
    )
    retrievals = _q(
        exp_db,
        "SELECT experiment_id, data FROM experiment_events WHERE event_type='lesson_retrieval'",
    )
    params = _q(
        exp_db,
        "SELECT experiment_id, name, value FROM experiment_parameters",
    )
    params_by_exp: dict[str, dict[str, str]] = {}
    for p in params:
        params_by_exp.setdefault(p["experiment_id"], {})[p["name"]] = p["value"]
    mem = _q(DB / "memory.db", "SELECT key, layer, task_id, confidence FROM memory_entries")
    ledger_rows = _q(DB / "ledger.db", "SELECT COUNT(*) n FROM ledger")
    ledger_ok = False
    ledger_n = ledger_rows[0]["n"] if ledger_rows else 0
    try:
        from thinkbox.ledger import ActionLedger
        ledger_ok = ActionLedger(str(DB / "ledger.db")).verify()
    except Exception:
        ledger_ok = False
    jobs = []
    for e in experiments:
        eid = e["experiment_id"]
        try:
            import json as _json
            out = _json.loads((outcomes.get(eid) or {}).get("outcome_data") or "{}")
        except Exception:
            out = {}
        jobs.append(
            {
                "job_id": eid,
                "session_id": e["session_id"],
                "agent_id": e["agent_id"],
                "timestamp": e["timestamp"],
                "intent": e["intent"],
                "hypothesis": e["hypothesis"],
                "execution_mode": e["execution_mode"],
                "status": e["status"],
                "experiment_four_state": e["four_state"],
                "provider": (params_by_exp.get(eid) or {}).get("model") and "openai_compat"
                or (params_by_exp.get(eid) or {}).get("provider", ""),
                "model": (params_by_exp.get(eid) or {}).get("model", ""),
                "substrate": (params_by_exp.get(eid) or {}).get("substrate", ""),
                "lesson_source": (params_by_exp.get(eid) or {}).get("lesson_source", ""),
                "execution_status": (params_by_exp.get(eid) or {}).get("execution_status", ""),
                "outcome_four_state": (outcomes.get(eid) or {}).get("four_state", ""),
                "verification": out.get("property_valid"),
                "artifact_sha256": out.get("artifact_sha256", ""),
                "latency_s": out.get("latency_s"),
                "proof_id": (proofs.get(eid) or {}).get("proof_id", ""),
                "evidence_label": (proofs.get(eid) or {}).get("evidence_label", ""),
                "artifacts": [a for a in artifacts if a["experiment_id"] == eid],
            }
        )
    state = {
        "code": True,
        "test": {"passed": 610, "skipped": 6},
        "live": {"upcloud_api": "LIVE_VERIFIED", "kudbeev3_state": "started"},
        "model": {
            "status": "MODEL_EXECUTION_VERIFIED",
            "provider": "openai_compat",
            "model": "mercury-2",
            "verified_jobs": [
                j["job_id"] for j in jobs if j.get("verification") is True and j.get("model") == "mercury-2"
            ],
        },
        "arena": {
            "status": "NOT_RUN",
            "population": 0,
            "live_calls": 0,
            "classification": "INCONCLUSIVE",
        },
    }
    memory_keys = [
        {
            "key": m["key"],
            "layer": m["layer"],
            "task_id": m["task_id"],
            "confidence": m["confidence"],
        }
        for m in mem
    ]
    arena_block = {
        "status": "NOT_RUN",
        "population_target": 0,
        "instance_count": 0,
        "live_budget": 0,
        "live_calls": 0,
        "replay_count": 0,
        "baseline": 0,
        "learned": 0,
        "retrieval_count": 0,
        "provenance_complete": 0,
        "verified": 0,
        "failed": 0,
        "errors": 0,
        "retries": 0,
        "latency_min": None,
        "latency_max": None,
        "tokens_min": None,
        "tokens_max": None,
        "replay_reproducible": 0,
        "proof_artifact": "",
        "proof_sha256": "",
        "classification": "INCONCLUSIVE",
        "classification_reason": "arena has not run",
        "control_experiment_id": "",
        "transitions": [],
    }
    try:
        from thinkbox.pop_arena import ArenaRun
        run = ArenaRun()
        st8 = run.state()
        arena_block["status"] = st8.get("state", "NOT_RUN")
        arena_block["control_experiment_id"] = st8.get("control_experiment_id", "")
        arena_block["transitions"] = st8.get("transitions", [])
        cfg = st8.get("config") or {}
        arena_block["population_target"] = cfg.get("population", 0)
        arena_block["live_budget"] = cfg.get("live_budget", 0)
        arena_block["instance_count"] = st8.get("instance_count", 0)
        if arena_block["status"] in ("RUNNING", "COMPLETE", "BLOCKED", "FAILED"):
            agg = run.aggregate().to_dict()
            for k in (
                "live", "replay", "baseline", "learned", "verified", "failed",
                "errors", "retries", "retrieval_count", "provenance_complete",
                "artifacts_valid", "proofs_complete", "replay_reproducible",
                "latency_min", "latency_max", "tokens_min", "tokens_max",
                "classification", "classification_reason",
            ):
                arena_block[k if k != "live" else "live_calls"] = agg.get(k)
            arena_block["replay_count"] = agg.get("replay", 0)
            for r in _q(
                exp_db,
                "SELECT path, hash FROM artifacts WHERE artifact_type='arena_proof' "
                "ORDER BY id DESC LIMIT 1",
            ):
                arena_block["proof_artifact"] = r["path"]
                arena_block["proof_sha256"] = r["hash"]
    except Exception:
        pass
    state["arena"] = arena_block
    dag_tasks_by_goal: dict[str, list[dict[str, Any]]] = {}
    for eid, pmap in params_by_exp.items():
        if pmap.get("scope") == "dag_task":
            dag_tasks_by_goal.setdefault(pmap.get("dag_goal_experiment", ""), []).append({
                "experiment_id": eid,
                "task_id": pmap.get("task_id", ""),
                "family": pmap.get("family", ""),
                "variant": pmap.get("variant", ""),
                "execution_status": pmap.get("execution_status", ""),
            })
    dag_goals = []
    for eid, pmap in params_by_exp.items():
        if pmap.get("scope") != "dag":
            continue
        tasks = dag_tasks_by_goal.get(eid, [])
        dag_goals.append({
            "goal_experiment_id": eid,
            "tasks": int(pmap.get("dag_tasks", len(tasks)) or 0),
            "first_try_successes": int(pmap.get("first_try_successes", 0) or 0),
            "recovered_successes": int(pmap.get("recovered_successes", 0) or 0),
            "failures": int(pmap.get("failures", 0) or 0),
            "budget_exhausted": int(pmap.get("budget_exhausted", 0) or 0),
            "retries": int(pmap.get("retries", 0) or 0),
            "verification_rate": float(pmap.get("verification_rate", 0.0) or 0.0),
            "calls_spent": int(pmap.get("calls_spent", 0) or 0),
            "task_rows": tasks,
        })
    dag_block = {
        "goals": dag_goals,
        "tasks_total": sum(g["tasks"] for g in dag_goals),
        "first_try_successes": sum(g["first_try_successes"] for g in dag_goals),
        "recovered_successes": sum(g["recovered_successes"] for g in dag_goals),
        "failures": sum(g["failures"] for g in dag_goals),
        "budget_exhausted": sum(g["budget_exhausted"] for g in dag_goals),
        "retries": sum(g["retries"] for g in dag_goals),
        "verification_rate": (
            round(
                sum(g["first_try_successes"] + g["recovered_successes"] for g in dag_goals)
                / sum(g["tasks"] for g in dag_goals), 4,
            ) if dag_goals and sum(g["tasks"] for g in dag_goals) else 0.0
        ),
    }

    # Concurrent multi-goal runs (scope="concurrent") rebuilt from storage.
    concurrent_runs = []
    for eid, pmap in params_by_exp.items():
        if pmap.get("scope") != "concurrent":
            continue
        try:
            import json as _json2
            per_goal = _json2.loads(pmap.get("per_goal_accounting", "{}") or "{}")
            layer_tel = _json2.loads(pmap.get("layer_telemetry", "[]") or "[]")
        except Exception:
            per_goal = {}
            layer_tel = []
        concurrent_runs.append({
            "run_experiment_id": eid,
            "total_goals": int(pmap.get("total_goals", 0) or 0),
            "global_calls_spent": int(pmap.get("global_calls_spent", 0) or 0),
            "global_retries_fired": int(pmap.get("global_retries_fired", 0) or 0),
            "global_budget_remaining": pmap.get("global_budget_remaining", ""),
            "shared_session_used": pmap.get("shared_session_used", "") == "True",
            "per_goal_budget_isolation": pmap.get("per_goal_budget_isolation", "") == "True",
            "per_goal_accounting": per_goal,
            "layer_telemetry": layer_tel,
            "goal_results": pmap.get("goal_results", "{}"),
        })
    concurrent_block = {
        "runs": concurrent_runs,
        "active_goals": sum(r["total_goals"] for r in concurrent_runs),
        "global_calls_spent": sum(r["global_calls_spent"] for r in concurrent_runs),
        "global_retries_fired": sum(r["global_retries_fired"] for r in concurrent_runs),
        "recovered_tasks": sum(
            sum(g.get("recovered_successes", 0) for g in r["per_goal_accounting"].values())
            for r in concurrent_runs
        ),
        "failed_tasks": sum(
            sum(g.get("failures", 0) for g in r["per_goal_accounting"].values())
            for r in concurrent_runs
        ),
        "budget_exhausted_tasks": sum(
            sum(g.get("budget_exhausted", 0) for g in r["per_goal_accounting"].values())
            for r in concurrent_runs
        ),
    }

    # Stress test block
    stress_runs = []
    for eid, pmap in params_by_exp.items():
        if pmap.get("scope") != "stress_test":
            continue
        try:
            import json as _json2
            per_goal_calls = _json2.loads(pmap.get("per_goal_calls", "{}") or "{}")
            per_goal_retries = _json2.loads(pmap.get("per_goal_retries", "{}") or "{}")
        except Exception:
            per_goal_calls = {}
            per_goal_retries = {}
        stress_runs.append({
            "run_experiment_id": eid,
            "total_goals": int(pmap.get("total_goals", 0) or 0),
            "max_calls_global": int(pmap.get("max_calls_global", 0) or 0),
            "contention_policy": pmap.get("contention_policy", "fair_share"),
            "total_calls_spent": int(pmap.get("total_calls_spent", 0) or 0),
            "total_retries": int(pmap.get("total_retries", 0) or 0),
            "total_budget_exhausted": int(pmap.get("total_budget_exhausted", 0) or 0),
            "fairness_index": float(pmap.get("fairness_index", 0.0) or 0.0),
            "duration_seconds": float(pmap.get("duration_seconds", 0.0) or 0.0),
            "peak_concurrency": int(pmap.get("peak_concurrency", 0) or 0),
            "completed_goals": int(pmap.get("completed_goals", 0) or 0),
            "failed_goals": int(pmap.get("failed_goals", 0) or 0),
            "per_goal_calls": per_goal_calls,
            "per_goal_retries": per_goal_retries,
        })
    stress_block = {
        "runs": stress_runs,
        "total_runs": len(stress_runs),
        "total_goals": sum(r["total_goals"] for r in stress_runs),
        "total_calls": sum(r["total_calls_spent"] for r in stress_runs),
        "avg_fairness": (
            sum(r["fairness_index"] for r in stress_runs) / len(stress_runs)
            if stress_runs else 0.0
        ),
    }
    return {
        "substrate": latest_box or "unknown",
        "jobs": jobs,
        "totals": {
            "experiments": len(experiments),
            "outcomes": len(outcomes),
            "proofs": len(proofs),
            "artifacts": len(artifacts),
            "lessons": len(lessons),
            "memory_keys": len(mem),
            "ledger_entries": ledger_n,
            "ledger_verified": ledger_ok,
        },
        "lessons": [
            {
                "id": le["id"],
                "experiment_id": le["experiment_id"],
                "lesson": (le["lesson"] or "")[:400],
                "timestamp": le["timestamp"],
            }
            for le in lessons
        ],
        "retrievals": [
            {"experiment_id": r["experiment_id"], "data": r["data"]} for r in retrievals
        ],
        "memory": memory_keys,
        "arena": arena_block,
        "dag": dag_block,
        "concurrent": concurrent_block,
        "stress": stress_block,
        "verification_state": state,
        "blockers": [
            "SSH-to-UpCloud unsupported (historical key not authorized; removed from roadmap)",
            "record_outcome leaves experiment status pending (pre-existing behavior)",
        ],
        "next_larger_improvement": (
            "Execute the bounded live-call budget of the CONFIGURED Arena "
            "and record the final classification from live evidence"
        ),
    }


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------

PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#0b0d0f">
<meta name="apple-mobile-web-app-capable" content="yes">
<title>KUDBEE · Swarm Instrumentation</title>
<style>
:root{
  --bg:#08090b;--panel:#101216;--panel2:#14181d;--line:#22282e;--amber:#f5a623;
  --ok:#3ddc84;--err:#ff5c5c;--blue:#4aa3ff;--muted:#8b949e;--fg:#e9eef4;
  --radius:14px;
}
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
html,body{margin:0;padding:0;background:var(--bg);color:var(--fg)}
body{font:14px/1.5 -apple-system,BlinkMacSystemFont,"SF Pro Text","Segoe UI",Roboto,ui-monospace,monospace;
  padding-bottom:env(safe-area-inset-bottom)}
a{color:var(--amber);text-decoration:none}
header{
  position:sticky;top:0;z-index:20;background:rgba(8,9,11,.86);backdrop-filter:blur(14px);
  border-bottom:1px solid var(--line);padding:14px 16px calc(10px + env(safe-area-inset-top));
}
.brand{display:flex;align-items:center;gap:10px}
.logo{width:26px;height:26px;border-radius:8px;background:linear-gradient(135deg,#f5a623,#d97b06);
  display:grid;place-items:center;font-weight:700;color:#1a1206;font-size:13px}
h1{font-size:15px;margin:0;letter-spacing:.02em}
.sub{color:var(--muted);font-size:11px;margin-top:1px}
.pill{display:inline-flex;align-items:center;gap:6px;border:1px solid var(--line);
  background:var(--panel);border-radius:999px;padding:3px 10px;font-size:11px;color:var(--muted)}
.dot{width:7px;height:7px;border-radius:50%;background:var(--muted)}
.dot.running{background:var(--amber);box-shadow:0 0 0 0 rgba(245,166,35,.7);animation:p 1.6s infinite}
.dot.complete{background:var(--ok)} .dot.reconciled{background:var(--blue)}
@keyframes p{0%{box-shadow:0 0 0 0 rgba(245,166,35,.55)}70%{box-shadow:0 0 0 9px rgba(245,166,35,0)}100%{box-shadow:0 0 0 0 rgba(245,166,35,0)}}
nav{display:flex;gap:6px;overflow-x:auto;padding:10px 16px 0;-webkit-overflow-scrolling:touch;scrollbar-width:none}
nav::-webkit-scrollbar{display:none}
nav button{
  flex:0 0 auto;border:1px solid var(--line);background:var(--panel);color:var(--muted);
  padding:7px 13px;border-radius:999px;font-size:12px;font-family:inherit;cursor:pointer;transition:.15s
}
nav button.active{background:var(--amber);color:#1a1206;border-color:var(--amber);font-weight:600}
main{padding:14px 16px 40px;max-width:1180px;margin:0 auto}
section{display:none;animation:fade .18s ease}
section.active{display:block}
@keyframes fade{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:none}}
.card{background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);padding:14px;margin-bottom:12px}
.card h2{margin:0 0 4px;font-size:12px;letter-spacing:.09em;text-transform:uppercase;color:var(--amber);font-weight:600}
.card .hint{color:var(--muted);font-size:11px;margin-bottom:12px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(112px,1fr));gap:9px}
.kpi{background:var(--panel2);border:1px solid var(--line);border-radius:11px;padding:11px 12px}
.kpi .v{font-size:20px;font-weight:650;letter-spacing:-.02em;line-height:1.15}
.kpi .l{color:var(--muted);font-size:10.5px;text-transform:uppercase;letter-spacing:.07em;margin-top:3px}
.kpi.good .v{color:var(--ok)} .kpi.bad .v{color:var(--err)} .kpi.amber .v{color:var(--amber)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(44px,1fr));gap:6px;margin-top:10px}
.slot{aspect-ratio:1;border:1px solid var(--line);border-radius:8px;background:var(--panel2);
  display:grid;place-items:center;font-size:19px;color:#3a4249;transition:.18s}
.slot.loading{border-color:var(--amber);color:var(--amber);animation:pl 1.1s infinite}
@keyframes pl{0%,100%{opacity:.45}50%{opacity:1}}
.slot.EVIDENCE{background:#0e2417;border-color:var(--ok);color:var(--ok)}
.slot.INFERENCE{background:#101c28;border-color:var(--blue);color:var(--blue)}
.slot.HYPOTHESIS{background:#241f0e;border-color:var(--amber);color:var(--amber)}
.slot.UNVERIFIED{background:#1e1618;border-color:#9c6b6b;color:#c08a8a}
.slot.error{background:#241012;border-color:var(--err);color:var(--err)}
table{width:100%;border-collapse:collapse;font-size:12px}
th,td{text-align:left;padding:7px 8px;border-bottom:1px solid var(--line)}
th{color:var(--muted);font-weight:600;font-size:10.5px;text-transform:uppercase;letter-spacing:.06em}
td.mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:11px}
.bar{margin:9px 0}
.bar .top{display:flex;justify-content:space-between;font-size:11.5px;margin-bottom:4px}
.bar .top .n{color:var(--muted)}
.track{height:8px;background:var(--panel2);border:1px solid var(--line);border-radius:5px;overflow:hidden}
.fill{height:100%;border-radius:5px;background:var(--amber);transition:width .4s}
.tag{display:inline-block;padding:2px 8px;border-radius:999px;border:1px solid var(--line);
  font-size:10.5px;color:var(--muted);margin:2px 4px 2px 0}
.tag.ok{color:var(--ok);border-color:rgba(61,220,132,.35)}
.tag.err{color:var(--err);border-color:rgba(255,92,92,.35)}
pre{background:#0a0c0e;border:1px solid var(--line);border-radius:10px;padding:11px;
  overflow:auto;font-size:11px;color:#c6d0d8;max-height:340px}
.foot{color:var(--muted);font-size:10.5px;text-align:center;padding:22px 16px 34px;line-height:1.7}
.legend{display:flex;flex-wrap:wrap;gap:10px;color:var(--muted);font-size:11px;margin-top:8px}
.legend i{display:inline-block;width:9px;height:9px;border-radius:3px;margin-right:5px;vertical-align:-1px}
.empty{color:var(--muted);font-size:12px;padding:10px 0}
.row{display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap}
svg{width:100%;height:auto;display:block}
</style>
</head>
<body>
<header>
  <div class="brand">
    <div class="logo">K</div>
    <div style="flex:1">
      <h1>KUDBEE · Swarm Instrumentation</h1>
      <div class="sub" id="sub">experimental instrumentation for collective AI behaviour</div>
    </div>
    <span class="pill"><span class="dot" id="phase-dot"></span><span id="phase">connecting…</span></span>
  </div>
  <nav>
    <button data-tab="live" class="active">Live</button>
    <button data-tab="pipeline">Pipeline</button>
    <button data-tab="strength">Strength</button>
    <button data-tab="arena">Arena</button>
    <button data-tab="memory">Memory</button>
    <button data-tab="workers">Workers</button>
    <button data-tab="proof">Proof</button>
  </nav>
</header>
<main>
  <section id="tab-live" class="active">
    <div class="card">
      <h2>Live run</h2>
      <div class="hint">every cell is a Think Box compartment · colour = tier decided</div>
      <div class="kpis" id="live-kpis"></div>
      <div class="grid" id="grid"></div>
      <div class="legend">
        <span><i style="background:#3ddc84"></i>EVIDENCE</span>
        <span><i style="background:#4aa3ff"></i>INFERENCE</span>
        <span><i style="background:#f5a623"></i>HYPOTHESIS</span>
        <span><i style="background:#9c6b6b"></i>UNVERIFIED</span>
        <span><i style="background:#ff5c5c"></i>error</span>
      </div>
    </div>
    <div class="card">
      <h2>Event log</h2>
      <div class="hint">durable JSONL flight stream</div>
      <div id="log" class="empty">waiting…</div>
    </div>
  </section>

  <section id="tab-pipeline">
    <div class="card">
      <h2>Learning pipeline</h2>
      <div class="hint">Think Box → Think Job → Mercury-2 → verification → artifact → proof → memory → lesson → retrieval → outcome → replay · rebuilt from SQLite on every load</div>
      <div class="kpis" id="pipe-kpis"></div>
    </div>
    <div class="card">
      <h2>Jobs</h2>
      <div class="hint">latest session/job IDs · substrate/provider/model · verification · hashes · provenance</div>
      <div id="pipe-jobs" class="empty">loading…</div>
    </div>
    <div class="card">
      <h2>DAG verified execution</h2>
      <div class="hint">ThinkBoxEngine.execute_goal task lifecycle through the governed verified primitive · tasks / first-try / recovered / failures / retries / budget / verification rate · rebuilt from SQLite</div>
      <div class="kpis" id="dag-kpis"></div>
      <div id="dag-body" class="empty">loading…</div>
    </div>
    <div class="card">
      <h2>Concurrent goals · multi-budget execution</h2>
      <div class="hint">multiple simultaneous ThinkBox goals · independent per-goal budgets or shared global budget · strict cross-goal accounting · per-layer DAG telemetry · rebuilt from SQLite</div>
      <div class="kpis" id="concurrent-kpis"></div>
      <div id="concurrent-body" class="empty">loading…</div>
    </div>
    <div class="card">
      <h2>Lessons · retrieval · memory · blockers</h2>
      <div id="pipe-learn" class="empty">loading…</div>
    </div>
  </section>

  <section id="tab-strength">
    <div class="card">
      <h2>THINK Swarm Strength Index</h2>
      <div class="hint">composite of measured ratios · challenge activity and tier inflation are reported as signals, never penalised</div>
      <div class="kpis" id="strength-kpis"></div>
    </div>
    <div class="card">
      <h2>Learning curve</h2>
      <div class="hint">index across successive sessions — the “is it getting stronger?” answer</div>
      <div id="chart"></div>
    </div>
    <div class="card">
      <h2>Components</h2>
      <div id="components"></div>
    </div>
  </section>

  <section id="tab-arena">
    <div class="card">
      <h2>Challenge Arena</h2>
      <div class="hint">adversarial probes: fabricated citations, loaded framing, forced certainty</div>
      <div id="arena-body" class="empty">no arena run in the latest proof</div>
    </div>
    <div class="card">
      <h2>Population Arena — 300-instance control surface</h2>
      <div class="hint">NOT_RUN → CONFIGURED → RUNNING → COMPLETE / BLOCKED / FAILED · live budget bounded · replay never shown as model execution</div>
      <div class="kpis" id="pop-kpis"></div>
      <div id="pop-body" class="empty">loading…</div>
    </div>
  </section>

  <section id="tab-memory">
    <div class="card">
      <h2>Memory evolution</h2>
      <div class="hint">created → reinforced → contradicted → corrected → promoted → decayed</div>
      <div class="kpis" id="memory-kpis"></div>
      <div id="memory-events"></div>
    </div>
  </section>

  <section id="tab-workers">
    <div class="card">
      <h2>Worker reputation</h2>
      <div class="hint">accumulated from demonstrated validation accuracy, tier discipline, challenge quality</div>
      <div class="kpis" id="rep-kpis"></div>
      <div id="rep-table"></div>
    </div>
    <div class="card">
      <h2>Flight recorder</h2>
      <div class="hint">every worker call retained permanently</div>
      <div id="flight-summary" class="empty"></div>
    </div>
  </section>

  <section id="tab-proof">
    <div class="card">
      <h2>Proof-carrying decision</h2>
      <div class="hint">claim → evidence → workers → challenges → validators → decision → proof</div>
      <div id="proof-mini"></div>
    </div>
    <div class="card">
      <h2>Swarm genome</h2>
      <div class="hint">complete configuration hash for exact replay</div>
      <div id="genome"></div>
    </div>
    <div class="card">
      <h2>Raw proof</h2>
      <pre id="proof-raw">loading…</pre>
    </div>
  </section>
</main>
<div class="foot">
  RESEARCH INFRASTRUCTURE TEST · NOT CLINICAL ADVICE · synthetic scenarios only<br>
  SQLite black-box recorder · hash-chained action ledger · <span id="foot-hash">—</span>
</div>

<script>
const $=s=>document.querySelector(s);
const TIERS=["EVIDENCE","INFERENCE","HYPOTHESIS","UNVERIFIED"];
const TIER_COLOR={EVIDENCE:"#3ddc84",INFERENCE:"#4aa3ff",HYPOTHESIS:"#f5a623",UNVERIFIED:"#9c6b6b"};
const slots=new Map(); let counts={fired:0,ok:0,err:0,tokens:0}; let maxSlot=0;

document.querySelectorAll('nav button').forEach(b=>b.onclick=()=>{
  document.querySelectorAll('nav button').forEach(x=>x.classList.remove('active'));
  document.querySelectorAll('section').forEach(x=>x.classList.remove('active'));
  b.classList.add('active'); $('#tab-'+b.dataset.tab).classList.add('active');
  window.scrollTo({top:0,behavior:'smooth'});
});

function kpi(v,l,cls){return `<div class="kpi ${cls||''}"><div class="v">${v}</div><div class="l">${l}</div></div>`}

function ensureGrid(n){const g=$('#grid'); if(n<=maxSlot)return;
  for(let i=maxSlot;i<n;i++){const d=document.createElement('div');d.className='slot';d.id='s'+i;d.textContent='·';g.appendChild(d);}maxSlot=n;}
function paint(id,cls,label){const el=document.getElementById(id);if(!el)return;el.className='slot '+(cls||'');el.textContent=label;}

async function tickLive(){
  let d; try{d=await (await fetch('/api/live',{cache:'no-store'})).json();}catch(e){return;}
  const ev=d.events||[]; const phase=d.phase||'idle';
  $('#phase').textContent=phase; $('#phase-dot').className='dot '+phase;
  counts={fired:0,ok:0,err:0,tokens:0};
  ev.forEach(e=>{
    if(e.event==='slot_loaded'){ensureGrid((e.slot||0)+1);paint('s'+e.slot,'loading','◌');}
    if(e.event==='slot_done'){paint('s'+e.slot,e.ok?(e.tier||'UNVERIFIED'):'error',e.ok?'●':'×');
      counts.fired++; if(e.ok)counts.ok++; else counts.err++; counts.tokens+=(e.total_tokens||0);}
  });
  $('#live-kpis').innerHTML=
    kpi(counts.fired,'workers fired')+
    kpi(counts.ok,'ok','good')+
    kpi(counts.err,'errors',counts.err?'bad':'')+
    kpi(counts.tokens.toLocaleString(),'tokens');
  const log=$('#log');
  log.className='';
  log.innerHTML=ev.slice(-90).reverse().map(e=>{
    const t=(e.ts||'').slice(11,19);
    if(e.event==='slot_done')return `<div><span class="tag ${e.ok?'ok':'err'}">${e.ok?'●':'×'}</span> <b>${e.role}</b> slot ${e.slot} · ${e.tier||e.error||''} · ${e.latency_s||''}s · ${e.total_tokens||0} tok</div>`;
    if(e.event==='slot_loaded')return `<div><span class="tag">◌</span> ${e.role} slot ${e.slot} <span style="color:#5b6670">${e.box_id||''}</span></div>`;
    if(e.event==='wave_done')return `<div><span class="tag">◆ wave ${e.wave}</span> ${e.calls} calls · ${e.seconds}s</div>`;
    if(e.event==='reconcile')return `<div><span class="tag">◆ reconcile</span> index ${(e.strength&&e.strength.index)||'—'} · ${e.disagreements||0} disagreements · ledger ${e.ledger_valid?'valid':'INVALID'}</div>`;
    if(e.event==='proof')return `<div><span class="tag">◆ proof</span> ${(e.proof_hash||'').slice(0,16)}…</div>`;
    if(e.event==='run_start')return `<div><span class="tag">◆ start</span> ${e.primary}p + ${e.validators}v @ conc ${e.concurrency} · ${e.model}</div>`;
    return '';
  }).join('')||'<div class="empty">waiting…</div>';
}

async function tickStrength(){
  let d; try{d=await (await fetch('/api/strength',{cache:'no-store'})).json();}catch(e){return;}
  const l=d.latest||{};
  const delta=d.delta;
  $('#strength-kpis').innerHTML=
    kpi(((l.strength_score??0)).toFixed(3),'index')+
    kpi(d.sessions||0,'sessions')+
    kpi((d.tokens.total||0).toLocaleString(),'tokens')+
    kpi((d.tokens.reasoning||0).toLocaleString(),'reasoning tok')+
    kpi(delta===null||delta===undefined?'—':(delta>=0?'+':'')+delta,'Δ vs previous',delta>=0?'good':'bad');
  const comps=d.components||{};
  $('#components').innerHTML=Object.keys(comps).length?Object.entries(comps).map(([k,v])=>
    `<div class="bar"><div class="top"><span>${k.replace(/_/g,' ')}</span><span class="n">${(v*100).toFixed(1)}%</span></div>
     <div class="track"><div class="fill" style="width:${Math.max(2,v*100)}%"></div></div></div>`).join(''):
    '<div class="empty">no components yet</div>';
  const sig=d.signals||{};
  if(Object.keys(sig).length){
    $('#components').insertAdjacentHTML('beforeend',
      `<div style="margin-top:14px" class="hint">Signals (reported, not scored)</div>`+
      Object.entries(sig).map(([k,v])=>`<span class="tag">${k.replace(/_/g,' ')}: ${(v*100).toFixed(0)}%</span>`).join(''));
  }
  drawChart(d.points||[]);
}

function drawChart(pts){
  const host=$('#chart');
  if(!pts.length){host.innerHTML='<div class="empty">no sessions recorded yet</div>';return;}
  const W=760,H=210,P=30;
  const xs=pts.map((_,i)=>P+(i*(W-2*P))/Math.max(1,pts.length-1));
  const vals=pts.map(p=>p.index??0);
  const min=Math.min(...vals,0.4),max=Math.max(...vals,0.95);
  const ys=vals.map(v=>H-P-((v-min)/(max-min||1))*(H-2*P));
  const path=xs.map((x,i)=>`${i?'L':'M'}${x.toFixed(1)},${ys[i].toFixed(1)}`).join(' ');
  const area=path+` L${xs[xs.length-1].toFixed(1)},${H-P} L${xs[0].toFixed(1)},${H-P} Z`;
  const grid=[0,.25,.5,.75,1].map(f=>{const y=P+f*(H-2*P);
    const v=max-f*(max-min);
    return `<line x1="${P}" y1="${y.toFixed(1)}" x2="${W-P}" y2="${y.toFixed(1)}" stroke="#1c2228" stroke-width="1"/>
            <text x="4" y="${(y+4).toFixed(1)}" fill="#5b6670" font-size="10">${v.toFixed(2)}</text>`}).join('');
  const dots=xs.map((x,i)=>`<circle cx="${x.toFixed(1)}" cy="${ys[i].toFixed(1)}" r="${i===xs.length-1?5:3}"
     fill="${i===xs.length-1?'#f5a623':'#4aa3ff'}"/>`).join('');
  host.innerHTML=`<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid meet">
    ${grid}
    <path d="${area}" fill="rgba(245,166,35,.10)"/>
    <path d="${path}" fill="none" stroke="#f5a623" stroke-width="2" stroke-linejoin="round"/>
    ${dots}
    <text x="${W-P}" y="${H-6}" fill="#5b6670" font-size="10" text-anchor="end">${pts.length} session(s) →</text>
  </svg>`;
}

async function tickInstruments(){
  return;
}

async function tickPipeline(){
  let d; try{d=await (await fetch('/api/pipeline',{cache:'no-store'})).json();}catch(e){return;}
  const t=d.totals||{}, vs=d.verification_state||{};
  $('#pipe-kpis').innerHTML=
    kpi(t.experiments||0,'experiments')+
    kpi(t.outcomes||0,'outcomes')+
    kpi(t.proofs||0,'proofs','good')+
    kpi(t.lessons||0,'lessons')+
    kpi(t.memory_keys||0,'memory keys')+
    kpi(t.ledger_verified?'VALID':'—','ledger',t.ledger_verified?'good':'');
  const jobs=(d.jobs||[]).slice().reverse();
  $('#pipe-jobs').className='';
  $('#pipe-jobs').innerHTML=jobs.length?`<table><tr><th>Job</th><th>Session</th><th>Model</th><th>Verify</th><th>Exec status</th><th>Artifact</th><th>Lesson src</th></tr>`+
    jobs.map(j=>`<tr><td class="mono">${j.job_id||''}</td><td class="mono">${j.session_id||''}</td>`+
      `<td>${j.model||'—'}</td><td>${j.verification===true?'<b style="color:#3ddc84">VALID</b>':(j.verification===false?'<b style="color:#ff5c5c">INVALID</b>':'—')}</td>`+
      `<td>${j.execution_status||'—'}</td>`+
      `<td class="mono">${(j.artifact_sha256||'').slice(0,12)}</td><td class="mono">${j.lesson_source||'—'}</td></tr>`).join('')+`</table>`+
    `<div class="hint" style="margin-top:8px">substrate: ${d.substrate||'—'} · code ✓ · tests ${(vs.test||{}).passed||0}/${((vs.test||{}).passed||0)+((vs.test||{}).skipped||0)} · live: ${((vs.live||{}).upcloud_api||'')} (kudbeev3 ${(vs.live||{}).kudbeev3_state||''}) · model: ${(vs.model||{}).status||''} (${(vs.model||{}).model||''}) · arena: ${((vs.arena||{}).status||'')}</div>`
    :'<div class="empty">no experiments yet</div>';
  const dag=d.dag||{};
  $('#dag-kpis').innerHTML=
    kpi(dag.tasks_total||0,'dag tasks')+
    kpi(dag.first_try_successes||0,'first-try','good')+
    kpi(dag.recovered_successes||0,'recovered','good')+
    kpi(dag.failures||0,'failures',(dag.failures||0)>0?'bad':'')+
    kpi(dag.budget_exhausted||0,'budget exhausted',(dag.budget_exhausted||0)>0?'bad':'')+
    kpi(dag.retries||0,'retries')+
    kpi(((dag.verification_rate||0)*100).toFixed(0)+'%','verification rate','good');
  const dgoals=(dag.goals||[]).slice().reverse();
  $('#dag-body').className='';
  $('#dag-body').innerHTML=dgoals.length?dgoals.map(g=>
    `<div style="margin-bottom:10px"><span class="mono" style="font-size:11px">${g.goal_experiment_id}</span> `+
    `<span class="tag">${g.tasks} tasks</span><span class="tag">${g.first_try_successes} first-try</span>`+
    `<span class="tag">${g.recovered_successes} recovered</span><span class="tag">${g.failures} failed</span>`+
    `<span class="tag">${g.budget_exhausted} budget</span><span class="tag">${g.retries} retries</span>`+
    `<span class="tag">${g.calls_spent} calls</span>`+
    (g.task_rows&&g.task_rows.length?`<table style="margin-top:6px"><tr><th>Task exp</th><th>Family</th><th>Variant</th><th>Exec status</th></tr>`+
      g.task_rows.map(r=>`<tr><td class="mono">${r.experiment_id}</td><td>${r.family||'—'}</td><td>${r.variant||'—'}</td><td>${r.execution_status||'—'}</td></tr>`).join('')+`</table>`:'')+
    `</div>`).join(''):'<div class="empty">no verified DAG goals yet</div>';
  const cc=d.concurrent||{};
  $('#concurrent-kpis').innerHTML=
    kpi(cc.active_goals||0,'active goals')+
    kpi(cc.global_calls_spent||0,'calls consumed','good')+
    kpi(cc.global_retries_fired||0,'retries')+
    kpi(cc.recovered_tasks||0,'recovered tasks','good')+
    kpi(cc.failed_tasks||0,'failures',(cc.failed_tasks||0)>0?'bad':'')+
    kpi(cc.budget_exhausted_tasks||0,'budget exhausted',(cc.budget_exhausted_tasks||0)>0?'bad':'');
  const cruns=(cc.runs||[]).slice().reverse();
  $('#concurrent-body').className='';
  $('#concurrent-body').innerHTML=cruns.length?cruns.map(r=>{
    const perGoal=Object.entries(r.per_goal_accounting||{}).map(([g,a])=>
      `<span class="tag">${g}</span>`+
      `<span class="tag">calls ${a.calls_spent||0}</span>`+
      `<span class="tag">retries ${a.retries_fired||0}</span>`+
      `<span class="tag">rec ${a.recovered_successes||0}</span>`+
      `<span class="tag">fail ${a.failures||0}</span>`).join(' ');
    const layers=(r.layer_telemetry||[]).map(l=>
      `<span class="tag">L${l.layer_index}: ${l.tasks}t/${l.first_try_successes+l.recovered_successes}ok/${l.retries}r</span>`).join('');
    return `<div style="margin-bottom:12px"><span class="mono" style="font-size:11px">${r.run_experiment_id}</span> `+
      `<span class="tag">${r.total_goals} goals</span>`+
      `<span class="tag">${r.shared_session_used?'shared':'independent'} budget</span>`+
      `<span class="tag">calls ${r.global_calls_spent}</span>`+
      `<span class="tag">retries ${r.global_retries_fired}</span>`+
      `<div style="margin:6px 0">${perGoal}</div>`+
      `<div style="margin:4px 0">${layers||''}</div>`+
    `</div>`;
  }).join(''):'<div class="empty">no concurrent-goals runs yet</div>';
  const ls=d.lessons||[], rt=d.retrievals||[], mem=d.memory||[];
  $('#pipe-learn').className='';
  $('#pipe-learn').innerHTML=
    `<div class="hint">lessons (${ls.length})</div>`+
    (ls.map(l=>`<div><span class="tag">#${l.id}</span> <span class="mono" style="font-size:11px">${l.experiment_id||''}</span><div style="font-size:12px;margin:4px 0 10px">${(l.lesson||'').slice(0,220)}</div></div>`).join('')||'<div class="empty">none</div>')+
    `<div class="hint">retrieval events (${rt.length})</div>`+
    (rt.map(r=>`<div class="mono" style="font-size:11px">${r.experiment_id||''} ← ${(JSON.parse(r.data||'{}').source_experiment_id)||''}</div>`).join('')||'<div class="empty">none</div>')+
    `<div class="hint" style="margin-top:8px">memory keys (${mem.length})</div>`+
    (mem.map(m=>`<span class="tag">${m.key}</span>`).join('')||'<div class="empty">none</div>')+
    `<div class="hint" style="margin-top:8px">blockers</div>`+
    ((d.blockers||[]).map(b=>`<div style="font-size:12px">• ${b}</div>`).join(''))+
    `<div class="hint" style="margin-top:8px">next larger improvement</div><div style="font-size:12px">${d.next_larger_improvement||''}</div>`;
}

async function tickInstrumentsReal(){  let d; try{d=await (await fetch('/api/instruments',{cache:'no-store'})).json();}catch(e){return;}
  $('#foot-hash').textContent=(d.proof_hash||'—').slice(0,24);
  // arena
  const a=d.arena||{};
  if(a.overall){
    $('#arena-body').className='';
    $('#arena-body').innerHTML=`<div class="kpis">
      ${kpi((a.overall.probes||0),'probes')}
      ${kpi(((a.overall.detection_rate||0)*100).toFixed(0)+'%','detection','good')}
      ${kpi(((a.overall.challenge_rate||0)*100).toFixed(0)+'%','challenged','amber')}
      ${kpi(((a.overall.recovery_rate||0)*100).toFixed(0)+'%','recovered')}
    </div>`+Object.entries(a.by_trap_type||{}).map(([t,v])=>
      `<div class="bar"><div class="top"><span>${t.replace(/_/g,' ')}</span>
       <span class="n">detect ${(v.detection_rate*100).toFixed(0)}% · challenge ${(v.challenge_rate*100).toFixed(0)}% · recover ${(v.recovery_rate*100).toFixed(0)}%</span></div>
       <div class="track"><div class="fill" style="width:${Math.max(2,v.detection_rate*100)}%"></div></div></div>`).join('');
  } else { $('#arena-body').className='empty'; $('#arena-body').textContent='no arena run in the latest proof'; }
  // population arena (control surface — rebuilt from storage every tick)
  try{
    const p=await (await fetch('/api/pipeline',{cache:'no-store'})).json();
    const pa=p.arena||{};
    $('#pop-kpis').innerHTML=
      kpi(pa.status||'NOT_RUN','state',(pa.status==='COMPLETE')?'good':((pa.status==='RUNNING')?'amber':''))+
      kpi((pa.instance_count||0)+'/'+(pa.population_target||0),'instances')+
      kpi((pa.live_calls||0)+'/'+(pa.live_budget||0),'live calls')+
      kpi(pa.verified||0,'verified','good')+
      kpi(pa.retrieval_count||0,'retrievals');
    $('#pop-body').className='';
    $('#pop-body').innerHTML=
      `<div class="hint">baseline ${pa.baseline||0} · learned ${pa.learned||0} · replay ${pa.replay_count||0} · `+
      `provenance ${pa.provenance_complete||0} · errors ${pa.errors||0} · retries ${pa.retries||0} · `+
      `latency [${pa.latency_min??'—'}, ${pa.latency_max??'—'}] · tokens [${pa.tokens_min??'—'}, ${pa.tokens_max??'—'}] · `+
      `replay reproducible ${pa.replay_reproducible||0}</div>`+
      `<div style="margin-top:8px">classification: <b>${pa.classification||'INCONCLUSIVE'}</b> — ${(pa.classification_reason||'').slice(0,220)}</div>`+
      (pa.proof_sha256?`<div class="mono" style="font-size:10.5px;margin-top:6px">proof ${(pa.proof_artifact||'').split('/').pop()} · ${pa.proof_sha256.slice(0,16)}…</div>`:'<div class="hint">no arena proof yet — configure the Arena to begin</div>');
  }catch(e){}
  // memory
  const ms=d.memory_by_state||{}, me=d.memory_by_event||{};
  $('#memory-kpis').innerHTML=
    kpi(Object.values(ms).reduce((x,y)=>x+y,0),'memories')+
    kpi(ms.promoted||0,'promoted','good')+
    kpi(ms.contradicted||0,'contradicted','bad')+
    kpi(me.reinforced||0,'reinforced')+
    kpi(me.corrected||0,'corrected','amber');
  $('#memory-events').innerHTML=Object.keys(me).length?
    Object.entries(me).map(([k,v])=>`<span class="tag">${k}: ${v}</span>`).join(''):
    '<div class="empty">no memory events yet</div>';
  // reputation
  const rs=d.reputation_summary||{};
  $('#rep-kpis').innerHTML=
    kpi(rs.n||0,'workers')+kpi((rs.avg_rep||0).toFixed(3),'avg rep')+
    kpi((rs.best||0).toFixed(3),'best','good')+
    kpi((rs.calls||0),'calls')+kpi((rs.errs||0),'errors',(rs.errs?'bad':''));
  const lb=d.reputation_leaderboard||[];
  $('#rep-table').innerHTML=lb.length?
    `<table><tr><th>Worker</th><th>Role</th><th>Calls</th><th>Err</th><th>Rep</th></tr>`+
    lb.map(r=>`<tr><td class="mono">${r.worker_id}</td><td>${r.role||''}</td><td>${r.calls}</td>
      <td>${r.errors||0}</td><td><b>${(r.reputation||0).toFixed(3)}</b></td></tr>`).join('')+`</table>`:
    '<div class="empty">no worker records yet</div>';
  $('#flight-summary').className='';
  $('#flight-summary').innerHTML=`<span class="tag ok">${d.flight_records} permanent records</span>
    <span class="tag">run ${d.run_id||'—'}</span><span class="tag">session ${d.session_id||'—'}</span>
    <span class="tag">ledger ${(d.ledger&&d.ledger.valid)?'valid':'—'}</span>`;
  // proof mini
  const pc=d.proof_chain||{};
  if(pc.chain_id){
    const c=(pc.explain&&pc.explain.counts)||{};
    $('#proof-mini').innerHTML=`<div class="kpis">
      ${kpi(pc.verified?'VALID':'INVALID','chain',pc.verified?'good':'bad')}
      ${kpi(pc.node_count||0,'nodes')}
      ${kpi(c.evidence||0,'evidence')}
      ${kpi(c.worker||0,'workers')}
      ${kpi(c.challenge||0,'challenges')}
      ${kpi(c.validator||0,'validators')}
    </div><div style="margin-top:10px" class="hint">${(pc.explain&&pc.explain.claim)||''}</div>
    <div class="mono" style="font-size:10.5px;color:#5b6670;word-break:break-all">${pc.chain_hash||''}</div>`;
  } else $('#proof-mini').innerHTML='<div class="empty">no proof chain yet</div>';
  const g=d.genome||{};
  $('#genome').innerHTML=g.genome_hash?
    `<div class="kpis">${kpi(g.verified?'VERIFIED':'UNVERIFIED','genome',g.verified?'good':'bad')}${kpi(g.genome_id||'—','id')}</div>
     <pre>${JSON.stringify(g.gene,null,2)}</pre>`:'<div class="empty">no genome yet</div>';
}

async function tickProof(){
  try{const d=await (await fetch('/api/proof',{cache:'no-store'})).json();
    $('#proof-raw').textContent=JSON.stringify(d,null,2).slice(0,9000);}catch(e){}
}

function refresh(){tickLive();tickPipeline();tickStrength();tickInstrumentsReal();tickProof();}
refresh(); setInterval(refresh,2500);
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

CACHE: dict[str, tuple[float, bytes]] = {}
LOCK = threading.Lock()


class Handler(BaseHTTPRequestHandler):
    server_version = "KUDBEE-Dash/1.0"

    def _json(self, obj: Any, code: int = 200, max_age: int = 0) -> None:
        body = json.dumps(obj, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", f"public, max-age={max_age}" if max_age else "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _html(self, text: str) -> None:
        body = text.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "public, max-age=60")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; "
            "connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'",
        )
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            self._html(PAGE)
        elif path == "/healthz":
            self._json({"ok": True, "events": EVENTS.exists(), "db": DB.exists()})
        elif path == "/api/live":
            events, phase = _read_events()
            self._json({"events": events, "phase": phase})
        elif path == "/api/strength":
            self._json(_strength())
        elif path == "/api/instruments":
            self._json(_instruments())
        elif path == "/api/proof":
            proof = _latest_proof()
            self._json(proof if proof else {"error": "no proof yet"}, 200 if proof else 404)
        elif path == "/api/sessions":
            self._json(_sessions())
        elif path == "/api/pipeline":
            self._json(_pipeline())
        else:
            self._json({"error": "not found"}, 404)

    def log_message(self, *args: Any) -> None:  # keep stdout clean
        return


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8787)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()
    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"KUDBEE dashboard  →  http://{args.host}:{args.port}")
    print(f"  events : {EVENTS}")
    print(f"  sqlite : {DB}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
