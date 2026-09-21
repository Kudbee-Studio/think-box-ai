#!/usr/bin/env python3
"""BIG SWARM — KUDBEE at scale, with a live compartment event stream.

The "inventory / compartments" idea, implemented literally:

  * every worker is a Think Box  = one inventory slot
  * every slot owns a capability = the "weapon" it can fire
  * slots are loaded hot as the run scrolls, and released when done
  * every fired slot writes a durable audit + trace + event

The workload is a genuinely large problem: independently tier and adversarially
verify a large batch of synthetic research claims, then reconcile consensus.
Nothing here is clinical advice; every scenario is SYNTHETIC.

Emits a live event stream to data/thinkboxmd/swarm_events.jsonl so the
dashboard (experiments/swarm_dashboard.py) can render it while it runs.

Usage:
    python3 experiments/big_swarm.py --primary 224 --validators 32 --concurrency 32 --fresh-ledger
    # 256 live calls = primary + validator wave. Use --fresh-ledger for per-run ledger cardinality.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from thinkbox.workspace import WorkspaceRegistry, WorkspaceStore, ThinkBox
from thinkbox.identity import IdentityLedger
from thinkbox.governance_token import GovernanceTokenService, TokenRequest
from thinkbox.admission import AdmissionGate
from thinkbox.ledger import ActionLedger
from thinkbox.thinktrace import ThinkTraceCapture
from thinkbox.metrics import MetricsStore, compute_swarm_strength
from thinkbox.swarm_stats import (
    effective_rps,
    latency_percentiles,
    open_action_ledger,
    validate_reconciliation,
)
from thinkbox.flightrecorder import FlightRecorder, WorkerRecord
from thinkbox.arena import ChallengeArena
from thinkbox.memory_evolution import MemoryEvolution
from thinkbox.reputation import ReputationLedger
from thinkbox.experiments import ExperimentStore, price_tokens
from core.memory.store import MemoryStore
from core.memory.schema import MemoryEntry, MemoryEntryType, MemoryLayer

URL = "https://api.inceptionlabs.ai/v1/chat/completions"
MODEL = "mercury-2"
OUT = ROOT / "data" / "thinkboxmd"
DB = OUT / "db"
EVENTS = OUT / "swarm_events.jsonl"

TIERS = ["EVIDENCE", "INFERENCE", "HYPOTHESIS", "UNVERIFIED"]

CLAIM_TEMPLATES = [
    "Synthetic claim {i}: agent {a} and agent {b} share a metabolic pathway documented in public labeling.",
    "Synthetic claim {i}: a peer-reviewed review reports an interaction signal between agent {a} and agent {b}.",
    "Synthetic claim {i}: a clinical guideline advises caution when co-prescribing agent {a} with agent {b}.",
    "Synthetic claim {i}: observational data suggest a risk signal for agent {a} plus agent {b} in reduced-renal profiles.",
    "Synthetic claim {i}: two public sources disagree about the significance of the agent {a}/{b} interaction.",
    "Synthetic claim {i}: a case series describes an adverse event pattern for agent {a} with agent {b}.",
]

AGENTS = ["Agent-A", "Agent-B", "Agent-C", "Agent-D", "Agent-E", "Agent-F", "Agent-G", "Agent-H"]


# --------------------------------------------------------------------------
# Event stream (dashboard bus)
# --------------------------------------------------------------------------

class EventBus:
    """Append-only JSONL event stream, flushed so a live reader sees progress."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._path = path
        self._lock = threading.Lock()
        self._path.write_text("")  # truncate for a fresh run

    def emit(self, **event: Any) -> None:
        event.setdefault("ts", datetime.now(timezone.utc).isoformat())
        event.setdefault("t", round(time.time(), 3))
        line = json.dumps(event, default=str) + "\n"
        with self._lock:
            with self._path.open("a") as fh:
                fh.write(line)


# --------------------------------------------------------------------------
# Worker / compartment
# --------------------------------------------------------------------------

@dataclass
class Compartment:
    slot: int
    worker_id: str
    role: str
    capability: str
    box_id: str = ""
    claim_id: str = ""
    claim: str = ""
    tier: str = ""
    latency_s: float = 0.0
    ok: bool = False
    error: str = ""
    trace_id: str = ""
    total_tokens: int = 0
    reasoning_tokens: int = 0
    status: str = "idle"          # idle -> loading -> fired -> done/error


def validator_sample_primary(
    results: list[Compartment],
    validator_n: int,
) -> list[Compartment]:
    """Select primary compartments for the validator wave.

    Uses the first ``validator_n`` primaries in completion order stored in
    ``results`` (wave 1 appends primaries only). Validators always run when
    configured, even if every primary failed, so ``total_calls`` stays
    ``primary_n + validator_n`` for proof validation.
    """
    if validator_n <= 0:
        return []
    primaries = [r for r in results if r.role == "PRIMARY"]
    return primaries[:validator_n]


class BigSwarm:
    def __init__(
        self,
        primary: int,
        validators: int,
        concurrency: int,
        arena: bool = False,
        fresh_ledger: bool = False,
    ) -> None:
        OUT.mkdir(parents=True, exist_ok=True)
        DB.mkdir(parents=True, exist_ok=True)
        self.primary_n = primary
        self.validator_n = validators
        self.concurrency = concurrency
        self.arena_on = arena
        self.bus = EventBus(EVENTS)

        self.registry = WorkspaceRegistry()
        self.store = WorkspaceStore(DB / "workspaces.db")
        self.identities = IdentityLedger()
        self.tokens = GovernanceTokenService(signing_key=f"big-swarm-{uuid.uuid4().hex[:8]}")
        self.gate = AdmissionGate(self.tokens, self.identities)
        ledger_path = DB / "action_ledger.db"
        self.ledger, self._ledger_entries_at_start = open_action_ledger(
            ledger_path, fresh=fresh_ledger
        )
        self.traces = ThinkTraceCapture()
        self.memory = MemoryStore(DB / "research_memory.db")
        self.metrics = MetricsStore(DB / "metrics.db")
        self.flight = FlightRecorder(DB / "flight_recorder.db")
        self.memory_evo = MemoryEvolution(DB / "memory_evolution.db")
        self.reputation = ReputationLedger(DB / "reputation.db")
        self.experiments = ExperimentStore(DB / "experiments.db")
        self.arena = ChallengeArena()
        self.arena_probes = self.arena.build_probes(n_per_type=1) if arena else []
        self.prompt_version = "v2-instrumented"
        self.key = os.environ.get("INCEPTION_API_KEY", "")
        self.results: list[Compartment] = []
        self.reconciliation: dict[str, Any] = {}
        self.started = time.monotonic()
        self.session_id = f"swarm_sess_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        self.metrics.start_session(
            self.session_id, kind="big_swarm", model=MODEL, concurrency=concurrency,
            metadata={"primary": primary, "validators": validators, "synthetic": True},
        )

        self.bus.emit(event="run_start", session_id=self.session_id, primary=primary,
                      validators=validators, concurrency=concurrency, model=MODEL)

    # -- HTTP -------------------------------------------------------------

    def _call(self, system: str, user: str, max_tokens: int = 900) -> tuple[bool, str, float, str, dict]:
        body = json.dumps(
            {
                "model": MODEL,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "max_tokens": max_tokens,
                "temperature": 0.0,
            }
        ).encode()
        req = urllib.request.Request(
            URL,
            data=body,
            headers={"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"},
            method="POST",
        )
        t0 = time.monotonic()
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                payload = json.loads(r.read().decode())
                content = payload["choices"][0]["message"].get("content") or ""
                return True, content, time.monotonic() - t0, "", payload.get("usage", {}) or {}
        except urllib.error.HTTPError as e:
            return False, "", time.monotonic() - t0, f"HTTP {e.code}: {e.read(160).decode(errors='replace')[:120]}", {}
        except Exception as e:
            return False, "", time.monotonic() - t0, f"{type(e).__name__}: {str(e)[:120]}", {}

    # -- claim corpus ------------------------------------------------------

    def build_corpus(self) -> list[dict[str, str]]:
        rng = random.Random(1337)
        claims = []
        for i in range(self.primary_n):
            tmpl = CLAIM_TEMPLATES[i % len(CLAIM_TEMPLATES)]
            a, b = rng.sample(AGENTS, 2)
            claims.append(
                {
                    "claim_id": f"CLM-{i:04d}",
                    "text": tmpl.format(i=i, a=a, b=b),
                    "synthetic": "true",
                }
            )
        return claims

    # -- one compartment lifecycle ----------------------------------------

    def fire(
        self,
        slot: int,
        role: str,
        capability: str,
        claim: dict[str, str],
        system: str,
        user: str,
    ) -> Compartment:
        wid = f"SWARM-{role}-{slot:04d}"
        comp = Compartment(slot=slot, worker_id=wid, role=role, capability=capability,
                           claim_id=claim["claim_id"], claim=claim["text"])

        # --- load slot -----------------------------------------------------
        comp.status = "loading"
        self.identities.register(wid, capabilities=[capability])
        tok = self.tokens.issue(TokenRequest(agent_id=wid, capabilities=[capability], ttl_seconds=1800))
        decision = self.gate.authorize(tok.token_value, wid, capability)
        box = self.registry.create(owner_id=wid, capabilities=[capability],
                                   state={"role": role, "claim_id": claim["claim_id"], "synthetic": True})
        self.store.save(box)
        comp.box_id = box.box_id
        self.bus.emit(event="slot_loaded", slot=slot, worker=wid, role=role, box_id=box.box_id,
                      capability=capability, claim_id=claim["claim_id"])

        if not decision.allowed:
            comp.status = "error"
            comp.error = f"admission_denied:{decision.reason}"
            self.ledger.append(wid, capability, f"swarm:{role}", False, decision.reason,
                               {"claim_id": claim["claim_id"]})
            self.bus.emit(event="slot_error", slot=slot, worker=wid, role=role, error=comp.error)
            return comp

        # --- fire ----------------------------------------------------------
        comp.status = "fired"
        ok, content, latency, err, usage = self._call(system, user)
        comp.ok = ok
        comp.latency_s = round(latency, 3)
        comp.error = err

        # token + session accounting
        self.metrics.record_tokens(self.session_id, wid, role, MODEL, usage, latency, ok)

        if ok:
            tier = "UNVERIFIED"
            for t in TIERS:
                if t in content.upper():
                    tier = t
                    break
            comp.tier = tier
            comp.total_tokens = int((usage or {}).get("total_tokens", 0) or 0)
            comp.reasoning_tokens = int(((usage or {}).get("completion_tokens_details") or {}).get("reasoning_tokens", 0) or 0)
        comp.status = "done" if ok else "error"

        # --- audit + trace -------------------------------------------------
        self.ledger.append(wid, capability, f"swarm:{role}", ok, "admitted" if ok else "provider_error",
                           {"claim_id": claim["claim_id"], "box_id": comp.box_id, "synthetic": True})
        ev_refs = [f"claim:{claim['claim_id']}"] if ok else None
        trace = self.traces.capture(wid, content[:800] or comp.error, evidence_refs=ev_refs,
                                    tags=[role, "swarm", comp.tier or "ERROR"],
                                    metadata={"box_id": comp.box_id, "ok": ok})
        comp.trace_id = trace.trace_id

        if ok:
            self.memory.put(MemoryEntry(
                key=f"swarm:{comp.claim_id}:{comp.trace_id}",
                layer=MemoryLayer.ORGANIZATIONAL,
                entry_type=MemoryEntryType.PATTERN,
                value={"synthetic": True, "role": role, "tier": comp.tier,
                       "claim_id": comp.claim_id, "box_id": comp.box_id},
                agent_id=wid, task_id="big_swarm", metadata={"synthetic": True},
                confidence=0.7 if comp.tier == "EVIDENCE" else 0.4,
            ))
            # memory evolution: this concept's lifecycle event
            self.memory_evo.observe(
                session_id=self.session_id, claim_id=comp.claim_id,
                content=claim["text"], tier=comp.tier or "UNVERIFIED",
                evidence_refs=ev_refs,
            )

        # --- 1. flight recorder: permanent per-worker record ---------------
        self.flight.record(WorkerRecord(
            session_id=self.session_id, worker_id=wid, role=role, model=MODEL,
            prompt_version=self.prompt_version, trace_id=comp.trace_id, box_id=comp.box_id,
            claim_id=comp.claim_id, capability=capability, temperature=0.0, max_tokens=900,
            prompt_tokens=int((usage or {}).get("prompt_tokens", 0) or 0),
            completion_tokens=int((usage or {}).get("completion_tokens", 0) or 0),
            reasoning_tokens=comp.reasoning_tokens, total_tokens=comp.total_tokens,
            latency_s=comp.latency_s, decision=comp.tier or "ERROR",
            evidence_refs=ev_refs or [], outcome="ok" if ok else "error", error=comp.error,
            cost_usd=price_tokens(MODEL, int((usage or {}).get("prompt_tokens", 0) or 0),
                                 int((usage or {}).get("completion_tokens", 0) or 0)),
        ))

        # --- 6. reputation: tier discipline + calibration -------------------
        self.reputation.observe_call(
            wid, role, comp.tier or "UNVERIFIED", ok,
            confidence=0.7 if comp.tier == "EVIDENCE" else 0.4,
        )

        self.bus.emit(event="slot_done", slot=slot, worker=wid, role=role, ok=ok,
                      tier=comp.tier or "ERROR", latency_s=comp.latency_s,
                      box_id=comp.box_id, claim_id=comp.claim_id, trace_id=comp.trace_id,
                      total_tokens=comp.total_tokens, error=comp.error)
        return comp

    # -- waves -------------------------------------------------------------

    def run(self) -> dict[str, Any]:
        claims = self.build_corpus()
        self.bus.emit(event="corpus_ready", claims=len(claims))

        primary_system = (
            "You are a SWARM research compartment in an auditable test harness. "
            "RESEARCH INFRASTRUCTURE TEST — NOT CLINICAL ADVICE. Synthetic only. "
            "Reply with EXACTLY ONE tier token and nothing else, chosen from: "
            "EVIDENCE, INFERENCE, HYPOTHESIS, UNVERIFIED. "
            "Use EVIDENCE only if a named public source category clearly supports it; "
            "otherwise downgrade. No other text."
        )
        validator_system = (
            "You are a SWARM VALIDATOR compartment. Adversarially review the claim. "
            "Reply with EXACTLY ONE tier token from: EVIDENCE, INFERENCE, HYPOTHESIS, "
            "UNVERIFIED — your independent, more skeptical tier. No other text."
        )

        # Wave 1: primary compartments
        t0 = time.monotonic()
        with ThreadPoolExecutor(max_workers=self.concurrency) as pool:
            futs = [
                pool.submit(self.fire, i, "PRIMARY", "research:primary",
                            c, primary_system,
                            f"Tier this synthetic claim:\n{c['text']}\n"
                            f"Reply with one token: EVIDENCE INFERENCE HYPOTHESIS UNVERIFIED")
                for i, c in enumerate(claims)
            ]
            for f in as_completed(futs):
                self.results.append(f.result())
        wave1 = time.monotonic() - t0
        self.bus.emit(event="wave_done", wave="primary", seconds=round(wave1, 2),
                      calls=len(claims))

        # Wave 2: validator compartments challenge a fixed primary sample
        sample = validator_sample_primary(self.results, self.validator_n)
        t0 = time.monotonic()
        if sample:
            with ThreadPoolExecutor(max_workers=self.concurrency) as pool:
                futs = []
                for i, r in enumerate(sample):
                    primary_tier = r.tier if (r.ok and r.tier) else "ERROR"
                    futs.append(
                        pool.submit(
                            self.fire,
                            10000 + i,
                            "VALIDATOR",
                            "research:validator",
                            {"claim_id": r.claim_id, "text": r.claim},
                            validator_system,
                            f"Claim: {r.claim}\nPrimary tier: {primary_tier}. "
                            f"Give your independent more-skeptical tier as one token.",
                        )
                    )
                for f in as_completed(futs):
                    self.results.append(f.result())
        wave2 = time.monotonic() - t0
        self.bus.emit(event="wave_done", wave="validator", seconds=round(wave2, 2), calls=len(sample))

        recon = self.reconcile()
        proof = self.write_proof(recon, wave1, wave2)
        return proof

    # -- reconcile ---------------------------------------------------------

    def reconcile(self) -> dict[str, Any]:
        primary = [r for r in self.results if r.role == "PRIMARY"]
        validators = [r for r in self.results if r.role == "VALIDATOR"]

        dist: dict[str, int] = {t: 0 for t in TIERS}
        dist["ERROR"] = 0
        for r in primary:
            dist[r.tier or "ERROR"] = dist.get(r.tier or "ERROR", 0) + 1

        by_claim = {r.claim_id: r.tier for r in primary}
        disagreements = []
        downgrades = 0
        rank = {t: i for i, t in enumerate(TIERS)}  # EVIDENCE most confident -> higher index = more skeptical
        for v in validators:
            p = by_claim.get(v.claim_id)
            if p and v.tier:
                self.metrics.record_challenge(self.session_id, v.claim_id, p, v.tier, rank)
                agreed = (p == v.tier)
                self.reputation.observe_validation(v.worker_id, agreed)
                # a validator is "right" when it is more skeptical than the primary
                upheld = rank.get(v.tier, 0) > rank.get(p, 0)
                if upheld:
                    downgrades += 1
                self.reputation.observe_challenge(v.worker_id, upheld)
                if not agreed:
                    disagreements.append({"claim_id": v.claim_id, "primary": p, "validator": v.tier})

        ok = [r for r in self.results if r.ok]
        elapsed = round(time.monotonic() - self.started, 2)
        inflation = sum(1 for d in disagreements if rank.get(d["validator"], 0) > rank.get(d["primary"], 0))

        non_error_tiers = {t: dist.get(t, 0) for t in TIERS}
        prev = self.metrics.previous_run("big_swarm")
        strength = compute_swarm_strength(
            total=len(self.results), ok=len(ok), traces=self.traces.count(),
            grounded=self.traces.count(grounded=True), validators=len(validators),
            disagreements=len(disagreements), validator_downgrades=downgrades,
            tier_inflation=inflation, tier_distribution=dist,
            previous_distribution=(prev or {}).get("distribution"),
            previous_index=(prev or {}).get("index"),
        )
        self._strength_index = strength

        recon = {
            "session_id": self.session_id,
            "total_calls": len(self.results),
            "ok": len(ok),
            "failed": len(self.results) - len(ok),
            "primary_calls": len(primary),
            "validator_calls": len(validators),
            "tier_distribution": dist,
            "disagreements": len(disagreements),
            "tier_inflation_by_validator": inflation,
            "elapsed_s": elapsed,
            "effective_rps": effective_rps(len(self.results), elapsed),
            **latency_percentiles([r.latency_s for r in ok]),
            "ledger_entries": len(self.ledger.entries(limit=1_000_000)),
            "ledger_entries_this_run": (
                len(self.ledger.entries(limit=1_000_000)) - self._ledger_entries_at_start
            ),
            "ledger_valid": self.ledger.verify(),
            "traces": self.traces.count(),
            "traces_grounded": self.traces.count(grounded=True),
            "memory_entries": self.memory.count(),
            "total_tokens": sum(r.total_tokens for r in ok),
            "reasoning_tokens": sum(r.reasoning_tokens for r in ok),
            "strength": strength.to_dict(),
            "disagreement_sample": disagreements[:8],
        }
        worker_rows = [
            {"role": r.role, "ok": r.ok}
            for r in self.results
        ]
        recon["validation_errors"] = validate_reconciliation(recon, worker_rows)
        self.reconciliation = recon
        emit_fields = {k: v for k, v in recon.items() if k not in ("disagreement_sample", "validation_errors")}
        self.bus.emit(event="reconcile", **emit_fields)
        if recon["validation_errors"]:
            self.bus.emit(event="reconcile_invalid", errors=recon["validation_errors"])
        return recon

    # -- proof -------------------------------------------------------------

    def write_proof(self, recon: dict[str, Any], wave1: float, wave2: float) -> dict[str, Any]:
        payload = {
            "run_id": f"big_swarm_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
            "session_id": self.session_id,
            "model": MODEL,
            "synthetic_only": True,
            "not_clinical": True,
            "concurrency": self.concurrency,
            "primary_workers": self.primary_n,
            "validator_workers": self.validator_n,
            "wave1_seconds": round(wave1, 2),
            "wave2_seconds": round(wave2, 2),
            "reconciliation": recon,
            "workers": [
                {
                    "role": r.role, "slot": r.slot, "worker": r.worker_id, "box": r.box_id,
                    "capability": r.capability, "claim_id": r.claim_id,
                    "tier": r.tier, "ok": r.ok, "latency_s": r.latency_s,
                    "total_tokens": r.total_tokens, "reasoning_tokens": r.reasoning_tokens,
                    "trace_id": r.trace_id, "error": r.error,
                }
                for r in self.results
            ],
        }
        payload["proof_hash"] = hashlib.sha256(
            json.dumps(payload, sort_keys=True, default=str).encode()
        ).hexdigest()
        path = OUT / f"{payload['run_id']}.json"
        path.write_text(json.dumps(payload, indent=2, default=str))
        self.bus.emit(event="proof", run_id=payload["run_id"], session_id=self.session_id,
                      path=str(path), proof_hash=payload["proof_hash"], ledger_valid=recon["ledger_valid"])

        # close the metrics session (index computed once, in reconcile)
        strength = getattr(self, "_strength_index", None)
        if strength is None:
            strength = compute_swarm_strength(
                total=recon["total_calls"], ok=recon["ok"], traces=recon["traces"],
                grounded=recon["traces_grounded"], validators=recon["validator_calls"],
                disagreements=recon["disagreements"], validator_downgrades=0,
                tier_inflation=recon["tier_inflation_by_validator"],
                tier_distribution=recon["tier_distribution"],
            )
        self.metrics.finish_session(
            self.session_id,
            workers_total=recon["total_calls"],
            workers_ok=recon["ok"],
            workers_failed=recon["failed"],
            wall_seconds=recon["elapsed_s"],
            effective_rps=recon["effective_rps"],
            ledger_entries=recon["ledger_entries"],
            ledger_valid=recon["ledger_valid"],
            proof_hash=payload["proof_hash"],
            index=strength,
            error_rate=recon["failed"] / max(1, recon["total_calls"]),
        )
        payload["metrics_totals"] = self.metrics.session_totals(self.session_id)
        payload["strength_trend"] = self.metrics.trend("big_swarm", limit=20)

        # --- 5. proof-carrying decision for one representative claim --------
        sample = next((r for r in self.results if r.role == "PRIMARY" and r.ok), None)
        if sample:
            v = next((r for r in self.results if r.role == "VALIDATOR" and r.claim_id == sample.claim_id), None)
            chain = self.flight.build_proof_chain(
                session_id=self.session_id, claim_id=sample.claim_id, claim=sample.claim,
                evidence_nodes=[{"ref": f"claim:{sample.claim_id}"},
                                {"trace": sample.trace_id}],
                worker_nodes=[{"worker": sample.worker_id, "tier": sample.tier,
                               "box": sample.box_id, "tokens": sample.total_tokens}],
                challenge_nodes=[{"validator": v.worker_id, "tier": v.tier}] if v else [],
                validator_nodes=[{"validator": v.worker_id, "tier": v.tier}] if v else [],
                decision=sample.tier or "UNVERIFIED",
            )
            payload["proof_chain"] = {
                "chain_id": chain["chain_id"],
                "node_count": chain["node_count"],
                "chain_hash": chain["chain_hash"],
                "verified": self.flight.verify_proof_chain(chain["chain_id"]),
                "explain": self.flight.explain(chain["chain_id"]),
            }

        # --- 10. genome / replay -------------------------------------------
        genome = {
            "run_id": payload["run_id"],
            "model": MODEL,
            "primary_workers": self.primary_n,
            "validator_workers": self.validator_n,
            "concurrency": self.concurrency,
            "prompt_version": self.prompt_version,
            "arena_enabled": bool(self.arena_probes),
            "probes": [p.probe_id for p in self.arena_probes],
            "tier_order": TIERS,
            "claims": [r.claim_id for r in self.results if r.role == "PRIMARY"][:64],
        }
        payload["genome"] = self.flight.save_genome(self.session_id, genome)
        payload["genome"]["verified"] = self.flight.verify_genome(self.session_id)

        # --- 2. challenge arena (if enabled) -------------------------------
        if self.arena.outcomes:
            payload["arena"] = self.arena.report()

        # --- 4/6/1. instrument summaries -----------------------------------
        payload["instruments"] = {
            "flight_recorder_records": self.flight.count(self.session_id),
            "memory_evolution": self.memory_evo.stats(),
            "reputation": self.reputation.summary(),
            "reputation_leaderboard": self.reputation.leaderboard(limit=10),
            "genome_verified": payload["genome"]["verified"],
            "proof_chain_verified": payload.get("proof_chain", {}).get("verified", False),
        }

        path.write_text(json.dumps(payload, indent=2, default=str))
        return {"path": str(path), "payload": payload}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--primary", type=int, default=128)
    ap.add_argument("--validators", type=int, default=32)
    ap.add_argument("--concurrency", type=int, default=32)
    ap.add_argument("--arena", action="store_true", help="enable adversarial Challenge Arena probes")
    ap.add_argument(
        "--fresh-ledger",
        action="store_true",
        help="truncate shared action_ledger.db before run (per-run ledger cardinality)",
    )
    args = ap.parse_args()

    if args.primary < 1:
        print("--primary must be >= 1")
        return 2
    if args.validators < 0:
        print("--validators must be >= 0")
        return 2
    if args.concurrency < 1:
        print("--concurrency must be >= 1")
        return 2

    if not os.environ.get("INCEPTION_API_KEY"):
        print("INCEPTION_API_KEY missing")
        return 2

    swarm = BigSwarm(
        args.primary,
        args.validators,
        args.concurrency,
        arena=args.arena,
        fresh_ledger=args.fresh_ledger,
    )
    t0 = time.monotonic()
    proof = swarm.run()
    total = time.monotonic() - t0

    r = proof["payload"]["reconciliation"]
    print("=" * 66)
    print("BIG SWARM RESULT")
    print("=" * 66)
    print(f"  workers fired      : {r['total_calls']} ({r['primary_calls']} primary + {r['validator_calls']} validator)")
    print(f"  ok / failed        : {r['ok']} / {r['failed']}")
    print(f"  tiers              : {r['tier_distribution']}")
    print(f"  disagreements      : {r['disagreements']}  (validator tier inflation: {r['tier_inflation_by_validator']})")
    print(f"  wall clock         : {round(total,2)}s  (wave1 {proof['payload']['wave1_seconds']}s, wave2 {proof['payload']['wave2_seconds']}s)")
    print(f"  effective rps      : {r['effective_rps']}")
    p95 = r.get("p95_latency_s", r["max_latency_s"])
    print(f"  p50 / p95 / max    : {r['p50_latency_s']}s / {p95}s / {r['max_latency_s']}s")
    print(
        f"  ledger entries     : {r['ledger_entries']} "
        f"(this run {r.get('ledger_entries_this_run', '?')})  valid={r['ledger_valid']}"
    )
    print(f"  traces grounded    : {r['traces_grounded']}/{r['traces']}")
    print(f"  memory entries     : {r['memory_entries']}")
    print(f"  proof              : {proof['path']}")
    if r.get("validation_errors"):
        print(f"  validation errors   : {r['validation_errors']}")
        return 1
    return 0 if r["ledger_valid"] and r["ok"] > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
