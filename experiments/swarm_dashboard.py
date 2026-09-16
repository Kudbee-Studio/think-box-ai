#!/usr/bin/env python3
"""KUDBEE — THINK BOX COMMAND CENTER v2.

An evolution of the instrumentation dashboard: the same single stdlib process,
the same read-only SQLite sources, the same "files over servers" rule — with the
instrumentation made observable across ten surfaces.

Preserved routes (payload shape unchanged, additive only):
    /healthz  /api/live  /api/strength  /api/instruments  /api/proof  /api/sessions

Added routes:
    /api/trace        causal trace for one claim (intent→…→outcome)
    /api/proofs       proof-chain explorer (verify each chain, list tamper state)
    /api/learning     strength curve + derived experiments + improvements
    /api/arena        challenge-arena replay from persisted outcomes
    /api/memory       memory-evolution timeline per concept
    /api/reputation   worker reputation with calibration + history
    /api/efficiency   cost x intelligence series
    /api/genome       recorded genomes with hash verification
    /api/replay       replay comparisons (source vs replay index)
    /api/mission      capability readiness, blockers, human intervention

Every displayed value has a traceable source: the UI renders these endpoints; the
endpoints read SQLite written by a run. Nothing is computed in the browser except
percentages and formatting.

Run:
    python3 experiments/swarm_dashboard.py --port 8787
Expose:
    cloudflared tunnel --url http://127.0.0.1:8787
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

OUT = ROOT / "data" / "thinkboxmd"
DB = OUT / "db"
EVENTS = OUT / "swarm_events.jsonl"

TIERS = ["EVIDENCE", "INFERENCE", "HYPOTHESIS", "UNVERIFIED"]


# -- CNC/G-code API ------------------------------------------------------

def api_cnc_machines() -> list[dict[str, Any]]:
    """Return list of configured CNC machines."""
    return _q(DB / "cnc.db",
              "SELECT machine_id, controller_type, profile_name, status, last_job_at, created_at "
              "FROM machines ORDER BY created_at DESC")


def api_cnc_machine(machine_id: str) -> dict[str, Any]:
    """Return detailed machine profile."""
    machine = _q(DB / "cnc.db",
                 "SELECT * FROM machines WHERE machine_id=?",
                 (machine_id,))
    if not machine:
        return {"error": "machine not found"}
    m = machine[0]
    
    # Get recent jobs
    jobs = _q(DB / "cnc.db",
              "SELECT job_id, gcode_file, status, started_at, completed_at, duration_s, "
              "material, tool_id, result FROM jobs WHERE machine_id=? ORDER BY started_at DESC LIMIT 20",
              (machine_id,))
    
    # Get tooling
    tools = _q(DB / "cnc.db",
               "SELECT tool_id, tool_type, diameter_mm, flutes, material, wear_mm, status, last_inspected_at "
               "FROM tools WHERE machine_id=? ORDER BY tool_id",
               (machine_id,))
    
    # Get work offsets
    offsets = _q(DB / "cnc.db",
                 "SELECT offset_id, name, x_mm, y_mm, z_mm, a_deg, b_deg, c_deg, active "
                 "FROM work_offsets WHERE machine_id=? ORDER BY offset_id",
                 (machine_id,))
    
    return {**m, "jobs": jobs, "tools": tools, "work_offsets": offsets}


def api_cnc_gcode(job_id: str) -> dict[str, Any]:
    """Return G-code content with validation results."""
    job = _q(DB / "cnc.db",
             "SELECT job_id, machine_id, gcode_file, status, validation_result, simulation_result, "
             "created_at FROM jobs WHERE job_id=?",
             (job_id,))
    if not job:
        return {"error": "job not found"}
    j = job[0]
    
    # Read G-code file
    gcode_path = Path(j["gcode_file"]) if j["gcode_file"] else None
    gcode_content = ""
    if gcode_path and gcode_path.exists():
        try:
            gcode_content = gcode_path.read_text()
        except OSError:
            gcode_content = "(error reading file)"
    
    return {**j, "gcode_content": gcode_content}


def api_cnc_validate_gcode(gcode: str, machine_id: str) -> dict[str, Any]:
    """Validate G-code against machine profile."""
    # Get machine limits
    machine = _q(DB / "cnc.db",
                 "SELECT max_feed_mm_min, max_spindle_rpm, travel_x_mm, travel_y_mm, travel_z_mm "
                 "FROM machines WHERE machine_id=?",
                 (machine_id,))
    if not machine:
        return {"valid": False, "errors": ["Machine not found"]}
    
    m = machine[0]
    errors = []
    warnings = []
    
    lines = gcode.splitlines()
    for i, line in enumerate(lines, 1):
        line_upper = line.strip().upper()
        
        # Check for feed rates exceeding machine limits
        if 'F' in line_upper and not line_upper.startswith('('):
            try:
                f_val = float(line_upper.split('F')[1].split()[0])
                if f_val > (m["max_feed_mm_min"] or 999999):
                    warnings.append(f"Line {i}: Feed rate {f_val} exceeds machine max {m['max_feed_mm_min']}")
            except (ValueError, IndexError):
                pass
        
        # Check for spindle speed exceeding limits
        if 'S' in line_upper and 'M3' in line_upper:
            try:
                s_val = float(line_upper.split('S')[1].split()[0])
                if s_val > (m["max_spindle_rpm"] or 999999):
                    errors.append(f"Line {i}: Spindle speed {s_val} exceeds machine max {m['max_spindle_rpm']}")
            except (ValueError, IndexError):
                pass
        
        # Check for coordinate overflow
        for axis in ['X', 'Y', 'Z']:
            if axis in line_upper:
                try:
                    coord = float(line_upper.split(axis)[1].split()[0])
                    max_travel = m[f"travel_{axis.lower()}_mm"]
                    if max_travel and abs(coord) > max_travel:
                        errors.append(f"Line {i}: {axis} coordinate {coord} exceeds travel {max_travel}")
                except (ValueError, IndexError):
                    pass
    
    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "line_count": len(lines)
    }


def api_cnc_simulate(job_id: str) -> dict[str, Any]:
    """Run G-code simulation (placeholder - would integrate with actual simulator)."""
    job = _q(DB / "cnc.db",
             "SELECT job_id, gcode_file, machine_id FROM jobs WHERE job_id=?",
             (job_id,))
    if not job:
        return {"error": "job not found"}
    
    # This would integrate with a real simulator like CNCjs, G-code Simulator, etc.
    return {
        "job_id": job_id,
        "status": "simulated",
        "estimated_time_s": 0,
        "toolpath_bounds": {"x": [0, 0], "y": [0, 0], "z": [0, 0]},
        "collisions": [],
        "note": "Simulation backend not yet implemented - integrate with CNCjs, G-code Simulator, or similar"
    }


# ---------------------------------------------------------------------------
# Readers
# ---------------------------------------------------------------------------

def _q(db: Path, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    """Read-only query. Returns [] if the store or table does not exist yet."""
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


def _latest_proof() -> dict[str, Any]:
    files = sorted(OUT.glob("big_swarm_*.json"))
    if not files:
        return {}
    try:
        return json.loads(files[-1].read_text())
    except (json.JSONDecodeError, OSError):
        return {}


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
            "arena_done": "running", "reconcile": "reconciled", "proof": "complete",
        }.get(events[-1].get("event", ""), events[-1].get("event", "idle"))
    return events[-limit:], phase


# -- 1. Swarm command --------------------------------------------------------

def api_live() -> dict[str, Any]:
    events, phase = _read_events()
    return {"events": events, "phase": phase}


# -- 2. Causal trace ---------------------------------------------------------

def api_trace(session_id: str, claim_id: str) -> dict[str, Any]:
    """Intent → capability → worker → action → evidence → validator → outcome."""
    if not session_id:
        sessions = _q(DB / "metrics.db",
                      "SELECT session_id FROM sessions ORDER BY started_at DESC LIMIT 1")
        session_id = sessions[0]["session_id"] if sessions else ""
    if not session_id:
        return {"error": "no session recorded yet", "trace": []}

    records = _q(
        DB / "flight_recorder.db",
        "SELECT worker_id, role, capability, claim_id, decision, validator_result, "
        "evidence_refs, outcome, error, latency_s, total_tokens, prompt_version, model, trace_id "
        "FROM worker_records WHERE session_id=?" + (" AND claim_id=?" if claim_id else "") +
        " ORDER BY role, worker_id",
        (session_id, claim_id) if claim_id else (session_id,),
    )
    if not records:
        return {"session_id": session_id, "claim_id": claim_id, "trace": [],
                "note": "no flight-recorder records for this session/claim"}

    stages: list[dict[str, Any]] = [{"stage": "intent", "detail": f"session {session_id}"}]
    for r in records:
        stages.append({
            "stage": "capability",
            "worker": r["worker_id"],
            "detail": r["capability"] or r["role"],
        })
        stages.append({
            "stage": "action",
            "worker": r["worker_id"],
            "detail": f"model={r['model']} prompt={r['prompt_version']} "
                      f"latency={r['latency_s']}s tokens={r['total_tokens']}",
        })
        refs = []
        if r["evidence_refs"]:
            try:
                refs = json.loads(r["evidence_refs"])
            except (json.JSONDecodeError, TypeError):
                refs = []
        stages.append({
            "stage": "evidence",
            "worker": r["worker_id"],
            "detail": ", ".join(refs) if refs else "(none)",
        })
        if r["role"] and "VALIDATOR" in r["role"].upper():
            stages.append({
                "stage": "validator",
                "worker": r["worker_id"],
                "detail": f"verdict={r['validator_result'] or r['decision']}",
            })
        stages.append({
            "stage": "outcome",
            "worker": r["worker_id"],
            "detail": f"{r['outcome']} · tier={r['decision']}"
                      + (f" · error={r['error']}" if r["error"] else ""),
        })
    return {"session_id": session_id, "claim_id": claim_id, "trace": stages}


# -- 3. Proof explorer -------------------------------------------------------

def api_proofs(session_id: str = "") -> dict[str, Any]:
    chains = _q(
        DB / "flight_recorder.db",
        "SELECT chain_id, session_id, claim_id, claim, decision, node_count, chain_hash, created_at "
        "FROM proof_chains" + (" WHERE session_id=?" if session_id else "") +
        " ORDER BY created_at DESC LIMIT 100",
        (session_id,) if session_id else (),
    )
    # verify each chain from its nodes (same algorithm as FlightRecorder)
    sys.path.insert(0, str(ROOT))
    from thinkbox.flightrecorder import FlightRecorder, canonical_hash
    fr = FlightRecorder(DB / "flight_recorder.db") if (DB / "flight_recorder.db").exists() else None
    verified = 0
    for c in chains:
        c["verified"] = bool(fr and fr.verify_proof_chain(c["chain_id"]))
        if c["verified"]:
            verified += 1
    return {
        "chains": chains,
        "total": len(chains),
        "verified": verified,
        "invalid": len(chains) - verified,
        "ledger": _ledger_state(),
    }


def _ledger_state() -> dict[str, Any]:
    path = DB / "action_ledger.db"
    if not path.exists():
        return {"present": False}
    try:
        from thinkbox.ledger import ActionLedger
        led = ActionLedger(str(path))
        valid = led.verify()
        entries = len(led.entries(limit=1_000_000))
        head = (led.entries(limit=1) or [{}])[0].get("entry_hash", "")
        led.close()
        return {"present": True, "valid": valid, "entries": entries, "head": head}
    except Exception as e:  # noqa: BLE001
        return {"present": True, "valid": False, "error": f"{type(e).__name__}: {str(e)[:80]}"}


def api_proof() -> dict[str, Any]:
    proof = _latest_proof()
    return proof if proof else {}


# -- 4. Learning -------------------------------------------------------------

def api_learning() -> dict[str, Any]:
    rows = _q(
        DB / "metrics.db",
        "SELECT s.session_id, s.ended_at, s.workers_total, s.workers_ok, s.effective_rps, "
        "s.strength_score, s.ledger_valid, h.grounded_ratio, h.evidence_ratio, h.challenge_rate, "
        "h.error_rate, h.tier_inflation_rate, h.learning_delta "
        "FROM sessions s LEFT JOIN strength_history h ON h.session_id=s.session_id "
        "WHERE s.kind='big_swarm' AND s.strength_score IS NOT NULL "
        "ORDER BY s.ended_at DESC LIMIT 40",
    )
    points = [{"session_id": r["session_id"], "ended_at": r["ended_at"],
               "index": r["strength_score"]} for r in reversed(rows)]
    delta = None
    if len(rows) >= 2 and rows[0]["strength_score"] is not None and rows[1]["strength_score"] is not None:
        delta = round(rows[0]["strength_score"] - rows[1]["strength_score"], 4)
    proof = _latest_proof()
    comps = (proof.get("reconciliation", {}) or {}).get("strength", {}).get("components", {})
    signals = (proof.get("reconciliation", {}) or {}).get("strength", {}).get("signals", {})
    tok = _q(DB / "metrics.db", "SELECT SUM(total_tokens) t, SUM(reasoning_tokens) rt, COUNT(*) n FROM token_usage")
    improvements = _q(
        DB / "experiments.db",
        "SELECT experiment_id, baseline_index, weakness, proposed_change, applied, retest_index, "
        "delta, accepted, created_at FROM improvements ORDER BY created_at DESC LIMIT 20",
    )
    for imp in improvements:
        try:
            imp["proposed_change"] = json.loads(imp["proposed_change"]) if imp["proposed_change"] else {}
        except (json.JSONDecodeError, TypeError):
            imp["proposed_change"] = {}
    return {
        "points": points,
        "latest": rows[0] if rows else None,
        "delta": delta,
        "components": comps,
        "signals": signals,
        "sessions": len(rows),
        "tokens": {"total": (tok[0]["t"] if tok else 0) or 0,
                   "reasoning": (tok[0]["rt"] if tok else 0) or 0,
                   "calls": (tok[0]["n"] if tok else 0) or 0},
        "improvements": improvements,
    }


# -- 5. Arena replay ---------------------------------------------------------

def api_arena(session_id: str = "") -> dict[str, Any]:
    where, params = ("WHERE session_id=?", (session_id,)) if session_id else ("", ())
    outcomes = _q(
        DB / "flight_recorder.db",
        "SELECT session_id, probe_id, trap_type, worker_id, tier, validator_tier, detected, "
        f"challenged, recovered, created_at FROM arena_outcomes {where} ORDER BY created_at DESC LIMIT 200",
        params,
    )
    by_type: dict[str, dict[str, int]] = {}
    for o in outcomes:
        b = by_type.setdefault(o["trap_type"], {"n": 0, "detected": 0, "challenged": 0, "recovered": 0})
        b["n"] += 1
        b["detected"] += o["detected"]
        b["challenged"] += o["challenged"]
        b["recovered"] += o["recovered"]

    def rate(b: dict[str, int], k: str) -> float:
        return round(b[k] / b["n"], 4) if b["n"] else 0.0

    summary = {t: {**b, "detection_rate": rate(b, "detected"),
                   "challenge_rate": rate(b, "challenged"),
                   "recovery_rate": rate(b, "recovered")}
               for t, b in by_type.items()}
    n = len(outcomes)
    return {
        "session_id": session_id or "all",
        "probes": n,
        "by_trap_type": summary,
        "overall": {
            "probes": n,
            "detection_rate": round(sum(o["detected"] for o in outcomes) / n, 4) if n else 0.0,
            "challenge_rate": round(sum(o["challenged"] for o in outcomes) / n, 4) if n else 0.0,
            "recovery_rate": round(sum(o["recovered"] for o in outcomes) / n, 4) if n else 0.0,
        },
        "outcomes": outcomes,
    }


# -- 6. Memory evolution -----------------------------------------------------

def api_memory(limit: int = 60) -> dict[str, Any]:
    by_state = _q(DB / "memory_evolution.db",
                  "SELECT state, COUNT(*) n FROM memories GROUP BY state")
    by_event = _q(DB / "memory_evolution.db",
                  "SELECT event, COUNT(*) n FROM memory_events GROUP BY event")
    recent = _q(
        DB / "memory_evolution.db",
        "SELECT e.memory_key, e.event, e.from_state, e.to_state, e.session_id, e.reason, e.created_at, "
        "m.content, m.confidence, m.tier, m.reinforce_count, m.contradict_count, m.useful_count "
        "FROM memory_events e LEFT JOIN memories m ON m.memory_key = e.memory_key "
        f"ORDER BY e.id DESC LIMIT {int(limit)}",
    )
    return {
        "by_state": {r["state"]: r["n"] for r in by_state},
        "by_event": {r["event"]: r["n"] for r in by_event},
        "recent": recent,
    }


# -- 7. Worker reputation ----------------------------------------------------

def api_reputation(limit: int = 40) -> dict[str, Any]:
    rows = _q(
        DB / "reputation.db",
        "SELECT worker_id, role, runs, calls, errors, tier_credit_sum, tier_credit_n, "
        "validation_hits, validation_n, successful_challenges, false_challenges, "
        "calib_sum, calib_n, trap_detect, trap_n, reputation, updated_at "
        "FROM worker_reputation WHERE calls>0 ORDER BY reputation DESC LIMIT ?",
        (int(limit),),
    )
    out = []
    for r in rows:
        ch_total = r["successful_challenges"] + r["false_challenges"]
        out.append({
            **r,
            "evidence_discipline": round(r["tier_credit_sum"] / r["tier_credit_n"], 4) if r["tier_credit_n"] else 0.0,
            "validation_accuracy": round(r["validation_hits"] / r["validation_n"], 4) if r["validation_n"] else 0.5,
            "challenge_quality": round(r["successful_challenges"] / ch_total, 4) if ch_total else 0.5,
            "calibration": round(r["calib_sum"] / r["calib_n"], 4) if r["calib_n"] else 0.5,
            "trap_detection": round(r["trap_detect"] / r["trap_n"], 4) if r["trap_n"] else 0.5,
        })
    summary = _q(
        DB / "reputation.db",
        "SELECT COUNT(*) n, AVG(reputation) avg_rep, MAX(reputation) best, SUM(calls) calls, "
        "SUM(errors) errs FROM worker_reputation WHERE calls>0",
    )
    return {"leaderboard": out, "summary": summary[0] if summary else {}}


# -- 8. Cost x intelligence --------------------------------------------------

def api_efficiency() -> dict[str, Any]:
    rows = _q(
        DB / "experiments.db",
        "SELECT experiment_id, variant, config, index_score, validated_insights, total_tokens, "
        "cost_usd, wall_seconds, created_at FROM variant_results ORDER BY created_at DESC, id ASC LIMIT 200",
    )
    series: list[dict[str, Any]] = []
    for r in rows:
        try:
            cfg = json.loads(r["config"]) if r["config"] else {}
        except (json.JSONDecodeError, TypeError):
            cfg = {}
        ins = r["validated_insights"] or 0
        series.append({
            "experiment_id": r["experiment_id"],
            "variant": r["variant"],
            "workers": cfg.get("workers", 0),
            "index": r["index_score"],
            "validated_insights": ins,
            "total_tokens": r["total_tokens"],
            "cost_usd": round(r["cost_usd"] or 0.0, 6),
            "wall_seconds": round(r["wall_seconds"] or 0.0, 3),
            "tokens_per_insight": round(r["total_tokens"] / ins, 2) if ins else None,
            "cost_per_insight_usd": round((r["cost_usd"] or 0.0) / ins, 6) if ins else None,
            "index_per_1k_tokens": round((r["index_score"] or 0.0) / ((r["total_tokens"] or 1) / 1000), 6),
        })
    tok = _q(DB / "metrics.db",
             "SELECT SUM(total_tokens) t, SUM(prompt_tokens) p, SUM(completion_tokens) c, "
             "SUM(reasoning_tokens) r, COUNT(*) n, AVG(latency_s) l FROM token_usage")
    return {
        "series": series,
        "totals": tok[0] if tok else {},
        "price_note": "Mercury 2 list price used: $0.25/M input, $0.75/M output",
    }


# -- 9. Genome / replay ------------------------------------------------------

def api_genome() -> dict[str, Any]:
    from thinkbox.flightrecorder import canonical_hash
    rows = _q(
        DB / "flight_recorder.db",
        "SELECT genome_id, session_id, gene, genome_hash, created_at FROM genomes "
        "ORDER BY created_at DESC LIMIT 50",
    )
    out = []
    for r in rows:
        try:
            gene = json.loads(r["gene"]) if r["gene"] else {}
        except (json.JSONDecodeError, TypeError):
            gene = {}
        out.append({**r, "gene": gene, "verified": canonical_hash(gene) == r["genome_hash"]})
    return {"genomes": out, "total": len(out), "verified": sum(1 for g in out if g["verified"])}


def api_replay() -> dict[str, Any]:
    rows = _q(
        DB / "flight_recorder.db",
        "SELECT source_session_id, replay_session_id, genome_hash, source_index, replay_index, "
        "index_delta, config_match, notes, created_at FROM replays ORDER BY created_at DESC LIMIT 50",
    )
    return {"replays": rows, "total": len(rows),
            "config_matched": sum(1 for r in rows if r["config_match"])}


# -- 10. Mission control -----------------------------------------------------

def api_mission() -> dict[str, Any]:
    from thinkbox.mission_control import MissionControl
    return MissionControl(OUT, DB).run()


# -- sessions ----------------------------------------------------------------

def api_sessions() -> list[dict[str, Any]]:
    return _q(
        DB / "metrics.db",
        "SELECT session_id, kind, model, started_at, ended_at, workers_total, workers_ok, "
        "workers_failed, effective_rps, ledger_valid, strength_score FROM sessions "
        "ORDER BY started_at DESC LIMIT 30",
    )


def api_instruments() -> dict[str, Any]:
    """Preserved from v1: flight/memory/reputation/proof/genome/arena summary."""
    proof = _latest_proof()
    mem = _q(DB / "memory_evolution.db", "SELECT state, COUNT(*) n FROM memories GROUP BY state")
    ev = _q(DB / "memory_evolution.db", "SELECT event, COUNT(*) n FROM memory_events GROUP BY event")
    rep = _q(DB / "reputation.db",
             "SELECT worker_id, role, calls, errors, reputation FROM worker_reputation "
             "WHERE calls>0 ORDER BY reputation DESC LIMIT 12")
    rep_sum = _q(DB / "reputation.db",
                 "SELECT COUNT(*) n, AVG(reputation) avg_rep, MAX(reputation) best, SUM(calls) calls, "
                 "SUM(errors) errs FROM worker_reputation WHERE calls>0")
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


def api_strength() -> dict[str, Any]:
    """Preserved from v1 (alias of the learning curve payload)."""
    return api_learning()


# ---------------------------------------------------------------------------
# HTML shell
# ---------------------------------------------------------------------------

PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#08090b">
<meta name="apple-mobile-web-app-capable" content="yes">
<title>THINK BOX · Command Center</title>
<style>
:root{--bg:#08090b;--panel:#101216;--panel2:#14181d;--line:#22282e;--amber:#f5a623;
--ok:#3ddc84;--err:#ff5c5c;--blue:#4aa3ff;--muted:#8b949e;--fg:#e9eef4;--r:14px}
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
html,body{margin:0;background:var(--bg);color:var(--fg)}
body{font:14px/1.5 -apple-system,BlinkMacSystemFont,"SF Pro Text","Segoe UI",Roboto,ui-monospace,monospace;
padding-bottom:env(safe-area-inset-bottom)}
header{position:sticky;top:0;z-index:20;background:rgba(8,9,11,.88);backdrop-filter:blur(14px);
border-bottom:1px solid var(--line);padding:12px 14px calc(8px + env(safe-area-inset-top))}
.brand{display:flex;align-items:center;gap:10px}
.logo{width:28px;height:28px;border-radius:8px;background:linear-gradient(135deg,#f5a623,#d97b06);
display:grid;place-items:center;font-weight:700;color:#1a1206;font-size:13px}
h1{font-size:14.5px;margin:0;letter-spacing:.02em}
.sub{color:var(--muted);font-size:10.5px;margin-top:1px}
.pill{display:inline-flex;align-items:center;gap:6px;border:1px solid var(--line);background:var(--panel);
border-radius:999px;padding:3px 10px;font-size:10.5px;color:var(--muted);white-space:nowrap}
.dot{width:7px;height:7px;border-radius:50%;background:var(--muted)}
.dot.running{background:var(--amber);animation:p 1.6s infinite}
.dot.complete{background:var(--ok)}.dot.reconciled{background:var(--blue)}
.dot.unavailable{background:var(--err)}
@keyframes p{0%{box-shadow:0 0 0 0 rgba(245,166,35,.55)}70%{box-shadow:0 0 0 9px rgba(245,166,35,0)}100%{box-shadow:0 0 0 0 rgba(245,166,35,0)}}
nav{display:flex;gap:6px;overflow-x:auto;padding:9px 14px 0;-webkit-overflow-scrolling:touch;scrollbar-width:none}
nav::-webkit-scrollbar{display:none}
nav button{flex:0 0 auto;border:1px solid var(--line);background:var(--panel);color:var(--muted);
padding:7px 12px;border-radius:999px;font-size:11.5px;font-family:inherit;cursor:pointer;min-height:34px}
nav button.active{background:var(--amber);color:#1a1206;border-color:var(--amber);font-weight:600}
main{padding:13px 14px 44px;max-width:1180px;margin:0 auto}
section{display:none}section.active{display:block;animation:f .18s ease}
@keyframes f{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:none}}
.card{background:var(--panel);border:1px solid var(--line);border-radius:var(--r);padding:13px;margin-bottom:11px}
.card h2{margin:0 0 3px;font-size:11.5px;letter-spacing:.08em;text-transform:uppercase;color:var(--amber);font-weight:600}
.hint{color:var(--muted);font-size:10.5px;margin-bottom:10px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(104px,1fr));gap:8px}
.kpi{background:var(--panel2);border:1px solid var(--line);border-radius:11px;padding:10px 11px}
.kpi .v{font-size:19px;font-weight:650;letter-spacing:-.02em;line-height:1.15;word-break:break-word}
.kpi .l{color:var(--muted);font-size:10px;text-transform:uppercase;letter-spacing:.06em;margin-top:3px}
.kpi.good .v{color:var(--ok)}.kpi.bad .v{color:var(--err)}.kpi.amber .v{color:var(--amber)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(42px,1fr));gap:5px;margin-top:9px}
.slot{aspect-ratio:1;border:1px solid var(--line);border-radius:8px;background:var(--panel2);
display:grid;place-items:center;font-size:18px;color:#3a4249}
.slot.loading{border-color:var(--amber);color:var(--amber)}
.slot.EVIDENCE{background:#0e2417;border-color:var(--ok);color:var(--ok)}
.slot.INFERENCE{background:#101c28;border-color:var(--blue);color:var(--blue)}
.slot.HYPOTHESIS{background:#241f0e;border-color:var(--amber);color:var(--amber)}
.slot.UNVERIFIED{background:#1e1618;border-color:#9c6b6b;color:#c08a8a}
.slot.error{background:#241012;border-color:var(--err);color:var(--err)}
table{width:100%;border-collapse:collapse;font-size:11.5px}
th,td{text-align:left;padding:6px 7px;border-bottom:1px solid var(--line)}
th{color:var(--muted);font-weight:600;font-size:10px;text-transform:uppercase;letter-spacing:.05em}
.mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:10.5px;word-break:break-all}
.bar{margin:8px 0}
.bar .top{display:flex;justify-content:space-between;font-size:11px;margin-bottom:4px}
.track{height:8px;background:var(--panel2);border:1px solid var(--line);border-radius:5px;overflow:hidden}
.fill{height:100%;background:var(--amber);transition:width .4s}
.tag{display:inline-block;padding:2px 7px;border-radius:999px;border:1px solid var(--line);
font-size:10px;color:var(--muted);margin:2px 4px 2px 0}
.tag.ok{color:var(--ok);border-color:rgba(61,220,132,.35)}
.tag.err{color:var(--err);border-color:rgba(255,92,92,.35)}
.tag.amber{color:var(--amber);border-color:rgba(245,166,35,.35)}
.tag.blue{color:var(--blue);border-color:rgba(74,163,255,.35)}
pre{background:#0a0c0e;border:1px solid var(--line);border-radius:10px;padding:10px;overflow:auto;
font-size:10.5px;color:#c6d0d8;max-height:320px}
.empty{color:var(--muted);font-size:11.5px;padding:8px 0}
.trace{display:grid;gap:3px}
.trace .row{display:grid;grid-template-columns:88px 1fr;gap:8px;padding:5px 0;border-bottom:1px solid var(--line)}
.trace .st{font-size:10px;text-transform:uppercase;letter-spacing:.05em;color:var(--amber)}
.foot{color:var(--muted);font-size:10px;text-align:center;padding:20px 14px 30px;line-height:1.7}
svg{width:100%;height:auto;display:block}
.legend{display:flex;flex-wrap:wrap;gap:9px;color:var(--muted);font-size:10.5px;margin-top:7px}
.legend i{display:inline-block;width:9px;height:9px;border-radius:3px;margin-right:5px;vertical-align:-1px}
</style>
</head>
<body>
<header>
  <div class="brand">
    <div class="logo">K</div>
    <div style="flex:1">
      <h1>THINK BOX · Command Center</h1>
      <div class="sub" id="sub">instrumented view of a swarm run · every value traceable to a store</div>
    </div>
    <span class="pill"><span class="dot" id="phase-dot"></span><span id="phase">…</span></span>
  </div>
  <nav id="nav"></nav>
</header>
<main id="main"></main>
<div class="foot">
  RESEARCH INFRASTRUCTURE TEST · NOT CLINICAL ADVICE · synthetic scenarios only<br>
  read-only SQLite · hash-chained ledger · <span id="foot-hash">—</span>
</div>
<script>
const TABS=[["command","Command"],["trace","Trace"],["proof","Proof"],["learning","Learning"],
["arena","Arena"],["memory","Memory"],["workers","Workers"],["cost","Cost×Intel"],
["replay","Replay"],["mission","Mission"],["cnc","CNC"]];
const TIERS=["EVIDENCE","INFERENCE","HYPOTHESIS","UNVERIFIED"];
const COLOR={EVIDENCE:"#3ddc84",INFERENCE:"#4aa3ff",HYPOTHESIS:"#f5a623",UNVERIFIED:"#9c6b6b"};
const $=s=>document.querySelector(s);
const esc=s=>String(s==null?"":s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
function kpi(v,l,c){return `<div class="kpi ${c||''}"><div class="v">${v}</div><div class="l">${l}</div></div>`}
function card(title,hint,body){return `<div class="card"><h2>${title}</h2><div class="hint">${hint}</div>${body}</div>`}
function bar(label,frac,color,note){
  const pct=Math.max(0,Math.min(100,Math.round((frac||0)*100)));
  return `<div class="bar"><div class="top"><span>${esc(label)}</span><span style="color:#8b949e">${note||pct+"%"}</span></div>
  <div class="track"><div class="fill" style="width:${pct}%;${color?`background:${color}`:''}"></div></div></div>`;
}
let tab="command";
function buildNav(){
  $("#nav").innerHTML=TABS.map(([id,label])=>
    `<button data-tab="${id}" class="${id===tab?'active':''}">${label}</button>`).join("");
  document.querySelectorAll("#nav button").forEach(b=>b.onclick=()=>{
    tab=b.dataset.tab; buildNav(); render();
  });
}
async function get(p){try{const r=await fetch(p,{cache:"no-store"});return await r.json()}catch(e){return {__err:String(e)}}}
function errBox(d){return d&&d.__err?`<div class="empty">unavailable: ${esc(d.__err)}</div>`:""}

async function render(){
  const m=$("#main");
  m.innerHTML=`<div class="empty">loading…</div>`;
  if(tab==="command") return renderCommand(m);
  if(tab==="trace") return renderTrace(m);
  if(tab==="proof") return renderProof(m);
  if(tab==="learning") return renderLearning(m);
  if(tab==="arena") return renderArena(m);
  if(tab==="memory") return renderMemory(m);
  if(tab==="workers") return renderWorkers(m);
  if(tab==="cost") return renderCost(m);
  if(tab==="replay") return renderReplay(m);
  if(tab==="mission") return renderMission(m);
  if(tab==="cnc") return renderCNC(m);
}

async function renderCommand(m){
  const d=await get("/api/live");
  if(d.__err) return m.innerHTML=errBox(d);
  const ev=d.events||[]; const slots=new Map(); let fired=0,ok=0,errs=0,tokens=0,maxSlot=0;
  ev.forEach(e=>{
    if(e.event==="slot_loaded"){slots.set(e.slot,e);maxSlot=Math.max(maxSlot,(e.slot||0)+1);}
    if(e.event==="slot_done"){slots.set(e.slot,e);maxSlot=Math.max(maxSlot,(e.slot||0)+1);
      fired++; e.ok?ok++:errs++; tokens+=(e.total_tokens||0);}
  });
  $("#phase").textContent=d.phase||"idle";
  $("#phase-dot").className="dot "+(d.phase||"idle");
  let grid="";
  for(let i=0;i<maxSlot;i++){
    const e=slots.get(i);
    const cls=!e?"":(e.event==="slot_loaded"?"loading":(e.ok?(e.tier||"UNVERIFIED"):"error"));
    grid+=`<div class="slot ${cls}">${!e?"·":(e.event==="slot_loaded"?"◌":(e.ok?"●":"×"))}</div>`;
  }
  const log=ev.slice(-70).reverse().map(e=>{
    const t=(e.ts||"").slice(11,19);
    if(e.event==="slot_done")return `<div><span class="tag ${e.ok?'ok':'err'}">${e.ok?'●':'×'}</span> <b>${esc(e.role)}</b> ${e.slot} · ${esc(e.tier||e.error||"")} · ${e.latency_s||""}s · ${e.total_tokens||0} tok</div>`;
    if(e.event==="slot_loaded")return `<div><span class="tag">◌</span> ${esc(e.role)} ${e.slot} · ${esc(e.capability||"")}</div>`;
    if(e.event==="wave_done")return `<div><span class="tag blue">◆ ${esc(e.wave)}</span> ${e.calls} calls · ${e.seconds}s</div>`;
    if(e.event==="arena_done")return `<div><span class="tag amber">◆ arena</span> ${e.probes} probes · detection ${(e.detection_rate||0).toFixed(2)}</div>`;
    if(e.event==="proof")return `<div><span class="tag ok">◆ proof</span> ${esc((e.proof_hash||"").slice(0,20))}…</div>`;
    if(e.event==="run_start")return `<div><span class="tag">◆ start</span> ${e.primary}p+${e.validators}v @ ${e.concurrency} · ${esc(e.model)}</div>`;
    return "";
  }).join("")||`<div class="empty">no events yet — run a swarm</div>`;
  m.innerHTML=card("Swarm command","live compartments · colour = tier decided",
    `<div class="kpis">${kpi(fired,"workers fired")}${kpi(ok,"ok","good")}${kpi(errs,"errors",errs?"bad":"")}${kpi(tokens.toLocaleString(),"tokens")}</div>`
    +`<div class="grid">${grid||"<div class='empty'>—</div>"}</div>`
    +`<div class="legend">${TIERS.map(t=>`<span><i style="background:${COLOR[t]}"></i>${t}</span>`).join("")}<span><i style="background:#ff5c5c"></i>error</span></div>`)
  +card("Event stream","append-only JSONL (durable)",`<div style="max-height:300px;overflow:auto">${log}</div>`);
}

async function renderTrace(m){
  const d=await get("/api/trace");
  if(d.__err) return m.innerHTML=errBox(d);
  const rows=(d.trace||[]).map(s=>`<div class="row"><div class="st">${esc(s.stage)}</div>
    <div>${esc(s.detail)}${s.worker?` <span class="tag">${esc(s.worker)}</span>`:""}</div></div>`).join("");
  m.innerHTML=card("Causal trace","intent → capability → worker → action → evidence → validator → outcome",
    `<div class="hint">session <span class="mono">${esc(d.session_id||"—")}</span>${d.claim_id?` · claim <span class="mono">${esc(d.claim_id)}</span>`:""}</div>`
    +(rows?`<div class="trace">${rows}</div>`:`<div class="empty">${esc(d.note||"no trace available")}</div>`));
}

async function renderProof(m){
  const d=await get("/api/proofs");
  if(d.__err) return m.innerHTML=errBox(d);
  const lg=d.ledger||{};
  const chains=(d.chains||[]).map(c=>`<tr><td class="mono">${esc(c.claim_id)}</td><td>${esc(c.decision)}</td>
    <td>${c.node_count}</td><td><span class="tag ${c.verified?'ok':'err'}">${c.verified?"VALID":"INVALID"}</span></td>
    <td class="mono">${esc((c.chain_hash||"").slice(0,18))}…</td></tr>`).join("");
  m.innerHTML=card("Ledger &amp; chains","hash-chained, tamper-evident",
    `<div class="kpis">${kpi(lg.entries??"—","ledger entries")}${kpi(lg.valid?"VALID":"—","chain",lg.valid?"good":"bad")}
     ${kpi(d.total??0,"proof chains")}${kpi(d.verified??0,"verified","good")}${kpi(d.invalid??0,"invalid",d.invalid?"bad":"")}</div>`
    +`<div class="hint" style="margin-top:8px">ledger head <span class="mono">${esc((lg.head||"—").slice(0,32))}</span></div>`)
  +card("Proof explorer","claim → evidence → workers → challenges → validators → decision",
    chains?`<table><tr><th>Claim</th><th>Decision</th><th>Nodes</th><th>Verify</th><th>Hash</th></tr>${chains}</table>`
    :`<div class="empty">no proof chains recorded yet</div>`);
}

async function renderLearning(m){
  const d=await get("/api/learning");
  if(d.__err) return m.innerHTML=errBox(d);
  const comps=d.components||{};
  const sig=d.signals||{};
  const imps=(d.improvements||[]).map(i=>`<tr><td>${esc(i.weakness)}</td>
    <td>${esc((i.proposed_change||{}).detail||"")}</td><td>${i.applied?"yes":"no"}</td>
    <td>${i.delta==null?"—":(i.delta>=0?"+":"")+i.delta}</td>
    <td>${i.accepted==null?"—":(i.accepted?'<span class="tag ok">accepted</span>':'<span class="tag err">rejected</span>')}</td></tr>`).join("");
  m.innerHTML=card("THINK Swarm Strength Index","composite of measured ratios · signals are not penalties",
    `<div class="kpis">${kpi(((d.latest||{}).strength_score??0).toFixed(3),"index")}${kpi(d.sessions||0,"sessions")}
     ${kpi((d.tokens.total||0).toLocaleString(),"tokens")}${kpi(d.delta==null?"—":((d.delta>=0?"+":"")+d.delta),"Δ previous",d.delta>=0?"good":"bad")}</div>`)
  +card("Learning curve","index across successive sessions",`<div id="chart"></div>`)
  +card("Components","weights: reliability .18 · grounding .20 · evidence .16 · resolution .16 · calibration .14 · reproducibility .16",
    Object.keys(comps).length?Object.entries(comps).map(([k,v])=>bar(k.replace(/_/g," "),v)).join("")
    +(Object.keys(sig).length?`<div class="hint" style="margin-top:10px">Signals (reported, not scored)</div>`
      +Object.entries(sig).map(([k,v])=>`<span class="tag amber">${esc(k.replace(/_/g," "))}: ${(v*100).toFixed(0)}%</span>`).join(""):"")
    :`<div class="empty">no components yet</div>`)
  +card("Experiments","derived from real sessions by experiments/run_experiment.py",
    imps?`<table><tr><th>Weakness</th><th>Proposed change</th><th>Applied</th><th>Δ</th><th>Result</th></tr>${imps}</table>`
    :`<div class="empty">no experiments recorded — run experiments/run_experiment.py</div>`);
  drawChart(d.points||[]);
}

function drawChart(pts){
  const host=$("#chart"); if(!host) return;
  if(!pts.length){host.innerHTML=`<div class="empty">no sessions recorded yet</div>`;return;}
  const W=760,H=200,P=30;
  const xs=pts.map((_,i)=>P+(i*(W-2*P))/Math.max(1,pts.length-1));
  const vals=pts.map(p=>p.index??0);
  const min=Math.min(...vals,0.4),max=Math.max(...vals,0.95);
  const ys=vals.map(v=>H-P-((v-min)/((max-min)||1))*(H-2*P));
  const path=xs.map((x,i)=>`${i?"L":"M"}${x.toFixed(1)},${ys[i].toFixed(1)}`).join(" ");
  const grid=[0,.25,.5,.75,1].map(f=>{const y=P+f*(H-2*P),v=max-f*(max-min);
    return `<line x1="${P}" y1="${y.toFixed(1)}" x2="${W-P}" y2="${y.toFixed(1)}" stroke="#1c2228"/>
    <text x="4" y="${(y+4).toFixed(1)}" fill="#5b6670" font-size="10">${v.toFixed(2)}</text>`}).join("");
  const dots=xs.map((x,i)=>`<circle cx="${x.toFixed(1)}" cy="${ys[i].toFixed(1)}" r="${i===xs.length-1?5:3}"
    fill="${i===xs.length-1?'#f5a623':'#4aa3ff'}"/>`).join("");
  host.innerHTML=`<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid meet">${grid}
    <path d="${path} L${xs[xs.length-1].toFixed(1)},${H-P} L${xs[0].toFixed(1)},${H-P} Z" fill="rgba(245,166,35,.10)"/>
    <path d="${path}" fill="none" stroke="#f5a623" stroke-width="2"/>${dots}
    <text x="${W-P}" y="${H-6}" fill="#5b6670" font-size="10" text-anchor="end">${pts.length} session(s) →</text></svg>`;
}

async function renderArena(m){
  const d=await get("/api/arena");
  if(d.__err) return m.innerHTML=errBox(d);
  const o=d.overall||{};
  const rows=(d.outcomes||[]).map(x=>`<tr><td class="mono">${esc(x.probe_id)}</td><td>${esc(x.trap_type)}</td>
    <td>${esc(x.tier)}</td><td>${esc(x.validator_tier||"—")}</td>
    <td>${x.detected?'<span class="tag ok">yes</span>':'<span class="tag err">no</span>'}</td>
    <td>${x.recovered?'<span class="tag amber">yes</span>':'—'}</td></tr>`).join("");
  m.innerHTML=card("Challenge arena","fabricated citations · loaded framing · forced certainty",
    `<div class="kpis">${kpi(o.probes||0,"probes")}${kpi(((o.detection_rate||0)*100).toFixed(0)+"%","detection","good")}
     ${kpi(((o.challenge_rate||0)*100).toFixed(0)+"%","challenged","amber")}${kpi(((o.recovery_rate||0)*100).toFixed(0)+"%","recovered")}</div>`)
  +card("By trap type","detection / challenge / recovery per adversarial class",
    Object.keys(d.by_trap_type||{}).length?Object.entries(d.by_trap_type).map(([t,v])=>
      bar(t.replace(/_/g," "),v.detection_rate,null,
        `n=${v.n} · detect ${(v.detection_rate*100).toFixed(0)}% · challenge ${(v.challenge_rate*100).toFixed(0)}% · recover ${(v.recovery_rate*100).toFixed(0)}%`)).join("")
    :`<div class="empty">no arena outcomes recorded</div>`)
  +card("Replay log","each probe, tier chosen, and whether a validator corrected it",
    rows?`<table><tr><th>Probe</th><th>Trap</th><th>Tier</th><th>Validator</th><th>Detected</th><th>Recovered</th></tr>${rows}</table>`
    :`<div class="empty">run with --arena to populate</div>`);
}

async function renderMemory(m){
  const d=await get("/api/memory");
  if(d.__err) return m.innerHTML=errBox(d);
  const st=d.by_state||{},ev=d.by_event||{};
  const rows=(d.recent||[]).map(x=>`<tr><td>${esc(x.event)}</td>
    <td>${esc(x.from_state||"")}→${esc(x.to_state||"")}</td>
    <td style="max-width:230px">${esc((x.content||"").slice(0,90))}</td>
    <td class="mono">${(x.confidence==null?"":Number(x.confidence).toFixed(2))}</td>
    <td class="mono">${esc((x.session_id||"").slice(-8))}</td></tr>`).join("");
  m.innerHTML=card("Memory evolution","created → reinforced → promoted → contradicted → corrected → decayed",
    `<div class="kpis">${kpi(Object.values(st).reduce((a,b)=>a+b,0),"memories")}
     ${kpi(st.promoted||0,"promoted","good")}${kpi(st.contradicted||0,"contradicted","bad")}
     ${kpi(ev.reinforced||0,"reinforced")}${kpi(ev.corrected||0,"corrected","amber")}</div>`
    +`<div class="hint" style="margin-top:8px">${Object.entries(ev).map(([k,v])=>`<span class="tag">${esc(k)}: ${v}</span>`).join("")||"no events"}</div>`)
  +card("Lifecycle events","append-only, newest first",
    rows?`<table><tr><th>Event</th><th>Transition</th><th>Concept</th><th>Conf</th><th>Session</th></tr>${rows}</table>`
    :`<div class="empty">no memory events yet</div>`);
}

async function renderWorkers(m){
  const d=await get("/api/reputation");
  if(d.__err) return m.innerHTML=errBox(d);
  const s=d.summary||{};
  const rows=(d.leaderboard||[]).map(w=>`<tr><td class="mono">${esc(w.worker_id)}</td><td>${esc(w.role||"")}</td>
    <td>${w.calls}</td><td>${(w.evidence_discipline||0).toFixed(2)}</td><td>${(w.validation_accuracy||0).toFixed(2)}</td>
    <td>${(w.calibration||0).toFixed(2)}</td><td>${(w.trap_detection||0).toFixed(2)}</td>
    <td><b>${(w.reputation||0).toFixed(3)}</b></td></tr>`).join("");
  m.innerHTML=card("Worker reputation","accumulated from demonstrated behaviour, not seniority",
    `<div class="kpis">${kpi(s.n||0,"workers")}${kpi((s.avg_rep||0).toFixed(3),"avg rep")}
     ${kpi((s.best||0).toFixed(3),"best","good")}${kpi(s.calls||0,"calls")}${kpi(s.errs||0,"errors",s.errs?"bad":"")}</div>`)
  +card("Leaderboard","evidence discipline · validation accuracy · calibration · trap detection",
    rows?`<table><tr><th>Worker</th><th>Role</th><th>Calls</th><th>Evid</th><th>Valid</th><th>Calib</th><th>Trap</th><th>Rep</th></tr>${rows}</table>`
    :`<div class="empty">no worker records yet</div>`);
}

async function renderCost(m){
  const d=await get("/api/efficiency");
  if(d.__err) return m.innerHTML=errBox(d);
  const t=d.totals||{};
  const series=(d.series||[]).map(r=>`<tr><td class="mono">${esc((r.variant||"").slice(-12))}</td><td>${r.workers}</td>
    <td>${(r.index||0).toFixed(3)}</td><td>${r.validated_insights}</td>
    <td>${(r.total_tokens||0).toLocaleString()}</td><td>$${(r.cost_usd||0).toFixed(4)}</td>
    <td>${r.tokens_per_insight==null?"—":r.tokens_per_insight}</td>
    <td>${r.cost_per_insight_usd==null?"—":"$"+r.cost_per_insight_usd}</td></tr>`).join("");
  m.innerHTML=card("Cost × intelligence","tokens, dollars and latency per validated insight",
    `<div class="kpis">${kpi((t.t||0).toLocaleString(),"total tokens")}${kpi((t.n||0),"calls")}
     ${kpi((t.l||0).toFixed(2)+"s","avg latency")}${kpi((t.r||0).toLocaleString(),"reasoning tok")}</div>`
    +`<div class="hint" style="margin-top:8px">${esc(d.price_note||"")}</div>`)
  +card("Variant series","derived from persisted sessions and experiments",
    series?`<table><tr><th>Variant</th><th>Workers</th><th>Index</th><th>Insights</th><th>Tokens</th><th>Cost</th><th>Tok/ins</th><th>$/ins</th></tr>${series}</table>`
    :`<div class="empty">no experiment series yet — run experiments/run_experiment.py</div>`);
}

async function renderReplay(m){
  const g=await get("/api/genome"); const r=await get("/api/replay");
  if(g.__err||r.__err) return m.innerHTML=errBox(g.__err?g:r);
  const grows=(g.genomes||[]).map(x=>`<tr><td class="mono">${esc(x.session_id)}</td>
    <td>${esc((x.gene||{}).model||"")}</td><td>${(x.gene||{}).primary_workers??"—"}</td>
    <td>${(x.gene||{}).concurrency??"—"}</td>
    <td><span class="tag ${x.verified?'ok':'err'}">${x.verified?"VERIFIED":"MISMATCH"}</span></td>
    <td class="mono">${esc((x.genome_hash||"").slice(0,16))}…</td></tr>`).join("");
  const rrows=(r.replays||[]).map(x=>`<tr><td class="mono">${esc((x.source_session_id||"").slice(-12))}</td>
    <td class="mono">${esc((x.replay_session_id||"").slice(-12))}</td>
    <td>${x.source_index==null?"—":Number(x.source_index).toFixed(3)}</td>
    <td>${x.replay_index==null?"—":Number(x.replay_index).toFixed(3)}</td>
    <td>${x.index_delta==null?"—":(x.index_delta>=0?"+":"")+Number(x.index_delta).toFixed(3)}</td>
    <td>${x.config_match?'<span class="tag ok">match</span>':'<span class="tag err">differs</span>'}</td></tr>`).join("");
  m.innerHTML=card("Swarm genomes","configuration hash for exact reproduction",
    `<div class="kpis">${kpi(g.total||0,"genomes")}${kpi(g.verified||0,"verified","good")}
     ${kpi(r.total||0,"replays")}${kpi(r.config_matched||0,"config matched","good")}</div>`)
  +card("Genomes","",grows?`<table><tr><th>Session</th><th>Model</th><th>Workers</th><th>Conc</th><th>Hash check</th><th>Hash</th></tr>${grows}</table>`
    :`<div class="empty">no genomes recorded</div>`)
  +card("Replays","reproduce a recorded run: <span class='mono'>python3 experiments/big_swarm.py --replay &lt;session_id&gt;</span>",
    rrows?`<table><tr><th>Source</th><th>Replay</th><th>Src idx</th><th>Replay idx</th><th>Δ</th><th>Config</th></tr>${rrows}</table>`
    :`<div class="empty">no replays recorded yet</div>`);
}

async function renderMission(m){
  const d=await get("/api/mission");
  if(d.__err) return m.innerHTML=errBox(d);
  const c=d.counts||{};
  const statusTag=s=>({ready:'ok',degraded:'amber',unavailable:'err',missing:'err',unknown:''}[s]||'');
  const caps=(d.capabilities||[]).map(x=>`<tr><td>${esc(x.label)}</td><td>${esc(x.layer)}</td>
    <td><span class="tag ${statusTag(x.status)}">${esc(x.status)}</span></td>
    <td style="max-width:320px">${esc(x.detail)}</td></tr>`).join("");
  const human=(d.human_intervention_required||[]).map(h=>`<li><b>${esc(h.label)}</b> — ${esc(h.action)}</li>`).join("");
  $("#phase").textContent=d.overall||"—";
  $("#phase-dot").className="dot "+(d.overall==="ready"?"complete":(d.overall==="degraded"?"reconciled":"unavailable"));
  m.innerHTML=card("Mission control","local non-destructive probes · read-only SQLite · no network calls",
    `<div class="kpis">${kpi((d.overall||"—").toUpperCase(),"overall",d.overall==="ready"?"good":(d.overall==="degraded"?"amber":"bad"))}
     ${kpi(((d.core_readiness||0)*100).toFixed(0)+"%","core readiness",(d.core_readiness>0.9?"good":"amber"))}
     ${kpi(((d.external_readiness||0)*100).toFixed(0)+"%","external readiness","amber")}
     ${kpi(c.ready||0,"ready","good")}${kpi(c.degraded||0,"degraded","amber")}
     ${kpi((c.unavailable||0)+(c.missing||0),"blocked","bad")}</div>`
    +`<div class="hint" style="margin-top:8px">${esc(d.note||"")}</div>`
    +`<div class="hint">external blockers: ${(d.external_blockers||[]).map(x=>`<span class="tag ${x.status==='degraded'?'amber':'err'}">${esc(x.key)}: ${esc(x.status)}</span>`).join("")||"none"}</div>`)
  +card("Capabilities","every row is a real probe",
    caps?`<table><tr><th>Capability</th><th>Layer</th><th>Status</th><th>Detail</th></tr>${caps}</table>`
    :`<div class="empty">no capability data</div>`)
  +card("Human intervention required","",human?`<ul style="margin:0;padding-left:18px;font-size:11.5px">${human}</ul>`
    :`<div class="empty">nothing requires a human right now</div>`);
}

async function renderCNC(m){
  const machines=await get("/api/cnc/machines");
  if(machines.__err) return m.innerHTML=errBox(machines);
  
  const rows=(machines||[]).map(mc=>`<tr>
    <td class="mono">${esc(mc.machine_id)}</td><td>${esc(mc.controller_type)}</td>
    <td>${esc(mc.profile_name)}</td><td><span class="tag ${mc.status==='ready'?'ok':mc.status==='busy'?'amber':'err'}">${esc(mc.status)}</span></td>
    <td class="mono">${esc((mc.last_job_at||"").slice(0,19).replace("T"," "))}</td>
    <td><button onclick="loadMachine('${esc(mc.machine_id)}')" class="pill" style="padding:4px 8px;font-size:10px">Open</button></td>
  </tr>`).join("");
  
  m.innerHTML=card("CNC Machines","configured machine profiles · controller types · persistent state",
    `<div class="kpis">${kpi(machines?.length||0,"machines")}${kpi(machines?.filter(m=>m.status==="ready").length||0,"ready","good")}${kpi(machines?.filter(m=>m.status==="busy").length||0,"busy","amber")}</div>`
    +(rows?`<table><tr><th>Machine ID</th><th>Controller</th><th>Profile</th><th>Status</th><th>Last Job</th><th></th></tr>${rows}</table>`
    :`<div class="empty">no machines configured — add to cnc.db</div>`)
    +`<div id="cnc-detail" style="margin-top:16px"></div>`);
}

window.loadMachine = async function(machine_id){
  const detail=$("#cnc-detail");
  detail.innerHTML=`<div class="empty">loading machine ${esc(machine_id)}…</div>`;
  const m=await get(`/api/cnc/machine/${machine_id}`);
  if(m.__err) return detail.innerHTML=errBox(m);
  
  const jobRows=(m.jobs||[]).map(j=>`<tr>
    <td class="mono">${esc(j.job_id)}</td><td>${esc((j.gcode_file||"").split("/").pop())}</td>
    <td><span class="tag ${j.status==='completed'?'ok':j.status==='running'?'amber':j.status==='failed'?'err':''}">${esc(j.status)}</span></td>
    <td class="mono">${esc((j.started_at||"").slice(0,19).replace("T"," "))}</td>
    <td>${esc(j.material||"")}</td><td>${esc(j.tool_id||"")}</td>
    <td>${j.duration_s?Number(j.duration_s).toFixed(1)+"s":"—"}</td>
    <td><button onclick="loadGcode('${esc(j.job_id)}')" class="pill" style="padding:2px 6px;font-size:10px">View</button></td>
  </tr>`).join("");
  
  const toolRows=(m.tools||[]).map(t=>`<tr>
    <td>${esc(t.tool_id)}</td><td>${esc(t.tool_type)}</td><td>${t.diameter_mm?Number(t.diameter_mm).toFixed(2):"?"}</td>
    <td>${t.flutes||"?"}</td><td>${esc(t.material||"")}</td>
    <td>${t.wear_mm?Number(t.wear_mm).toFixed(3):"?"}</td><td>${esc(t.status||"")}</td>
    <td class="mono">${esc((t.last_inspected_at||"").slice(0,10))}</td>
  </tr>`).join("");
  
  const offsetRows=(m.work_offsets||[]).map(o=>`<tr>
    <td>${esc(o.offset_id)}</td><td>${esc(o.name)}</td>
    <td>${o.x_mm?Number(o.x_mm).toFixed(3):"0"}</td><td>${o.y_mm?Number(o.y_mm).toFixed(3):"0"}</td>
    <td>${o.z_mm?Number(o.z_mm).toFixed(3):"0"}</td>
    <td>${o.a_deg?Number(o.a_deg).toFixed(2):"0"}</td><td>${o.b_deg?Number(o.b_deg).toFixed(2):"0"}</td>
    <td>${o.c_deg?Number(o.c_deg).toFixed(2):"0"}</td>
    <td>${o.active?'<span class="tag ok">active</span>':''}</td>
  </tr>`).join("");
  
  detail.innerHTML=card(`Machine: ${esc(m.machine_id)}`,`${esc(m.controller_type)} · ${esc(m.profile_name)}`,
    `<div class="kpis">${kpi(m.jobs?.length||0,"jobs")}${kpi(m.tools?.length||0,"tools")}${kpi(m.work_offsets?.length||0,"offsets")}</div>`
    +card("Jobs",`recent jobs on ${esc(m.machine_id)}`,
      jobRows?`<table><tr><th>Job ID</th><th>G-code File</th><th>Status</th><th>Started</th><th>Material</th><th>Tool</th><th>Duration</th><th></th></tr>${jobRows}</table>`
      :`<div class="empty">no jobs yet</div>`)
    +card("Tooling","persistent tool library with wear tracking",
      toolRows?`<table><tr><th>Tool ID</th><th>Type</th><th>Ø mm</th><th>Flutes</th><th>Material</th><th>Wear mm</th><th>Status</th><th>Inspected</th></tr>${toolRows}</table>`
      :`<div class="empty">no tools configured</div>`)
    +card("Work Offsets","G54-G59 persistent coordinate systems",
      offsetRows?`<table><tr><th>ID</th><th>Name</th><th>X</th><th>Y</th><th>Z</th><th>A</th><th>B</th><th>C</th><th>Active</th></tr>${offsetRows}</table>`
      :`<div class="empty">no work offsets configured</div>`)
    +card("Validate G-code","paste G-code to validate against this machine's limits",
      `<textarea id="gcode-input" placeholder="Paste G-code here..." style="width:100%;height:150px;font-family:monospace;font-size:11px;background:#0a0c0e;border:1px solid var(--line);border-radius:8px;padding:8px;color:var(--fg)"></textarea>
      <div style="margin-top:8px"><button onclick="validateGcode('${esc(machine_id)}')" class="pill" style="padding:6px 12px">Validate</button></div>
      <div id="validation-result" style="margin-top:8px"></div>`));
}

window.loadGcode = async function(job_id){
  const d=await get(`/api/cnc/gcode/${job_id}`);
  if(d.__err) return alert("Error: "+d.__err);
  const content=d.gcode_content||"(empty)";
  const val=d.validation_result?JSON.parse(d.validation_result):null;
  const sim=d.simulation_result?JSON.parse(d.simulation_result):null;
  
  // Open in new window/tab for better viewing
  const win=window.open("","G-code Viewer","width=900,height=700");
  win.document.write(`<!doctype html><html><head><title>G-code: ${esc(job_id)}</title>
  <style>body{font-family:monospace;padding:20px;background:#0a0c0e;color:#e9eef4}
  pre{background:#101216;padding:15px;border-radius:8px;overflow:auto}
  .err{color:#ff5c5c}.warn{color:#f5a623}.ok{color:#3ddc84}
  .panel{margin-bottom:20px;padding:15px;background:#101216;border-radius:8px;border:1px solid #22282e}
  </style></head><body>
  <h2>G-code: ${esc(job_id)}</h2>
  <div class="panel"><strong>Status:</strong> ${esc(d.status)} | <strong>Machine:</strong> ${esc(d.machine_id)} | <strong>File:</strong> ${esc(d.gcode_file||"")}</div>
  <div class="panel"><strong>Validation:</strong> ${val?`<span class="${val.valid?'ok':'err'}">${val.valid?"VALID":"INVALID"}</span>`:"not run"}
    ${val&&val.errors.length?`<br><strong>Errors:</strong><ul>${val.errors.map(e=>`<li class="err">${esc(e)}</li>`).join("")}</ul>`:""}
    ${val&&val.warnings.length?`<br><strong>Warnings:</strong><ul>${val.warnings.map(w=>`<li class="warn">${esc(w)}</li>`).join("")}</ul>`:""}
    ${val?`<br><strong>Lines:</strong> ${val.line_count}`:""}</div>
  <div class="panel"><strong>Simulation:</strong> ${sim?sim.status:"not run"} ${sim?`<br>Est. time: ${sim.estimated_time_s}s`:""}</div>
  <pre>${esc(content)}</pre></body></html>`);
}

window.validateGcode = async function(machine_id){
  const textarea=document.getElementById("gcode-input");
  const gcode=textarea.value;
  if(!gcode.trim()) return alert("Paste G-code first");
  
  const res=await fetch("/api/cnc/validate",{
    method:"POST",headers:{"Content-Type":"application/json"},
    body:JSON.stringify({gcode,machine_id})
  });
  const d=await res.json();
  if(d.__err) return document.getElementById("validation-result").innerHTML=`<div class="empty">Error: ${esc(d.__err)}</div>`;
  
  const el=document.getElementById("validation-result");
  if(d.valid){
    el.innerHTML=`<div class="kpis">${kpi("VALID","validation","good")}${kpi(d.line_count,"lines")}${kpi(d.warnings?.length||0,"warnings","amber")}</div>`
    +(d.warnings?.length?`<div class="hint"><strong>Warnings:</strong><ul>${d.warnings.map(w=>`<li class="tag amber">${esc(w)}</li>`).join("")}</ul></div>`:"");
  }else{
    el.innerHTML=`<div class="kpis">${kpi("INVALID","validation","bad")}${kpi(d.line_count,"lines")}${kpi(d.errors?.length||0,"errors","bad")}</div>`
    +`<div class="hint"><strong>Errors:</strong><ul>${d.errors.map(e=>`<li class="tag err">${esc(e)}</li>`).join("")}</ul></div>`
    +(d.warnings?.length?`<div class="hint"><strong>Warnings:</strong><ul>${d.warnings.map(w=>`<li class="tag amber">${esc(w)}</li>`).join("")}</ul></div>`:"");
  }
}

async function tick(){
  const d=await get("/api/instruments");
  if(!d.__err) $("#foot-hash").textContent=(d.proof_hash||"—").slice(0,24);
}
buildNav(); render(); tick(); setInterval(()=>{ if(tab==="command"||tab==="mission") render(); tick(); },5000);
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    server_version = "KUDBEE-CommandCenter/2.0"

    def _json(self, obj: Any, code: int = 200) -> None:
        body = json.dumps(obj, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
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
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)
        session_id = (qs.get("session_id") or [""])[0]
        claim_id = (qs.get("claim_id") or [""])[0]

        try:
            if path in ("/", "/index.html"):
                self._html(PAGE)
            elif path == "/healthz":
                self._json({"ok": True, "events": EVENTS.exists(), "db": DB.exists(),
                            "version": "command-center/2.0"})
            # preserved v1 routes
            elif path == "/api/live":
                self._json(api_live())
            elif path == "/api/strength":
                self._json(api_strength())
            elif path == "/api/instruments":
                self._json(api_instruments())
            elif path == "/api/proof":
                proof = api_proof()
                self._json(proof if proof else {"error": "no proof yet"}, 200 if proof else 404)
            elif path == "/api/sessions":
                self._json(api_sessions())
            # v2 routes
            elif path == "/api/trace":
                self._json(api_trace(session_id, claim_id))
            elif path == "/api/proofs":
                self._json(api_proofs(session_id))
            elif path == "/api/learning":
                self._json(api_learning())
            elif path == "/api/arena":
                self._json(api_arena(session_id))
            elif path == "/api/memory":
                self._json(api_memory())
            elif path == "/api/reputation":
                self._json(api_reputation())
            elif path == "/api/efficiency":
                self._json(api_efficiency())
            elif path == "/api/genome":
                self._json(api_genome())
            elif path == "/api/replay":
                self._json(api_replay())
            elif path == "/api/mission":
                self._json(api_mission())
            # CNC/G-code routes
            elif path == "/api/cnc/machines":
                self._json(api_cnc_machines())
            elif path.startswith("/api/cnc/machine/"):
                machine_id = path.split("/api/cnc/machine/")[1]
                self._json(api_cnc_machine(machine_id))
            elif path.startswith("/api/cnc/gcode/"):
                job_id = path.split("/api/cnc/gcode/")[1]
                self._json(api_cnc_gcode(job_id))
            elif path == "/api/cnc/validate":
                # POST only - handle in do_POST
                self._json({"error": "use POST"}, 405)
            elif path.startswith("/api/cnc/simulate/"):
                job_id = path.split("/api/cnc/simulate/")[1]
                self._json(api_cnc_simulate(job_id))
            else:
                self._json({"error": "not found", "path": path}, 404)
        except Exception as e:  # never leak a stack trace to the client
            self._json({"error": type(e).__name__, "detail": str(e)[:200]}, 500)

    def log_message(self, *args: Any) -> None:
        return

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8') if content_length > 0 else "{}"
        
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self._json({"error": "invalid JSON"}, 400)
            return
        
        try:
            if path == "/api/cnc/validate":
                gcode = data.get("gcode", "")
                machine_id = data.get("machine_id", "")
                if not gcode or not machine_id:
                    self._json({"error": "gcode and machine_id required"}, 400)
                    return
                self._json(api_cnc_validate_gcode(gcode, machine_id))
            else:
                self._json({"error": "not found", "path": path}, 404)
        except Exception as e:
            self._json({"error": type(e).__name__, "detail": str(e)[:200]}, 500)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8787)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()
    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"THINK BOX Command Center  →  http://{args.host}:{args.port}")
    print(f"  events : {EVENTS}")
    print(f"  sqlite : {DB}  (read-only)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
