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

from thinkbox.arena import ChallengeArena, AdversarialProbe
from thinkbox.experiments import (
    ExperimentStore, SelfImprovementLoop, Variant, VariantResult, efficiency, price_tokens,
)
from thinkbox.flightrecorder import FlightRecorder, WorkerRecord, canonical_hash
from thinkbox.memory_evolution import MemoryEvolution
from thinkbox.metrics import MetricsStore, compute_swarm_strength
from thinkbox.reputation import ReputationLedger

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


# ---------------------------------------------------------------------------
# 1. Flight Recorder
# ---------------------------------------------------------------------------

def c1_flight_recorder() -> str:
    fr = FlightRecorder(":memory:")
    fr.record(WorkerRecord(
        session_id="s", worker_id="w1", role="PRIMARY", model="m", prompt_version="v1",
        decision="UNVERIFIED", outcome="ok", total_tokens=42, latency_s=0.3,
        evidence_refs=["claim:C1"], reasoning_tokens=10,
    ))
    rows = fr.session_records("s")
    assert len(rows) == 1, "record not retrievable"
    r = rows[0]
    for k in ("trace_id", "model", "prompt_version", "total_tokens", "latency_s",
              "decision", "challenge", "validator_result", "evidence_refs", "outcome"):
        assert k in r, f"missing durable field: {k}"
    assert r["evidence_refs"] == ["claim:C1"], "evidence refs not preserved"
    return f"{len(r)} fields retained"


# ---------------------------------------------------------------------------
# 2. Challenge Arena
# ---------------------------------------------------------------------------

def c2_arena() -> str:
    arena = ChallengeArena()
    probes = arena.build_probes(n_per_type=2)
    types = {p.trap_type for p in probes}
    assert types == {"hallucination_trap", "tier_inflation_bait", "contradiction", "competing_answers"}, types
    probe = next(p for p in probes if p.trap_type == "hallucination_trap")
    bad = arena.score(probe, "w1", "EVIDENCE", validator_tier="UNVERIFIED")
    assert not bad.detected, "over-claim wrongly counted as detected"
    assert bad.recovered, "over-claim + corrective validator should be a recovery"
    good = arena.score(probe, "w2", "UNVERIFIED")
    assert good.detected and not good.recovered
    rep = arena.report()
    assert rep["overall"]["probes"] == 2
    return f"{len(types)} trap types, detection={rep['overall']['detection_rate']}"


# ---------------------------------------------------------------------------
# 3. Strength index + learning curve
# ---------------------------------------------------------------------------

def c3_strength_index() -> str:
    prev_dist = {"EVIDENCE": 4, "INFERENCE": 4, "HYPOTHESIS": 2, "UNVERIFIED": 0}
    idx = compute_swarm_strength(
        total=10, ok=10, traces=10, grounded=10, validators=4,
        disagreements=4, validator_downgrades=4, tier_inflation=0,
        tier_distribution=prev_dist, previous_distribution=prev_dist,
        previous_index=0.70,
    )
    assert 0.0 <= idx.score <= 1.0, "index out of range"
    assert abs(idx.reliability - 1.0) < 1e-9
    assert abs(idx.grounding - 1.0) < 1e-9
    assert abs(idx.reproducibility - 1.0) < 1e-9
    assert idx.learning_delta is not None

    # challenge activity must NOT be treated as failure
    quiet = compute_swarm_strength(
        total=4, ok=4, traces=4, grounded=4, validators=4, disagreements=0,
        validator_downgrades=0, tier_inflation=0, tier_distribution={"UNVERIFIED": 4})
    loud = compute_swarm_strength(
        total=4, ok=4, traces=4, grounded=4, validators=4, disagreements=4,
        validator_downgrades=4, tier_inflation=0, tier_distribution={"UNVERIFIED": 4})
    assert loud.score > quiet.score, "productive challenges must help, not hurt"

    ms = MetricsStore(":memory:")
    ms.start_session("s1", "big_swarm", "m", 8)
    ms.finish_session("s1", 4, 4, 0, 1.0, 4.0, 5, True, "h", idx)
    trend = ms.trend("big_swarm")
    assert len(trend["points"]) == 1, "learning curve point missing"
    return f"index={idx.score:.3f} delta={idx.learning_delta}"


# ---------------------------------------------------------------------------
# 4. Memory evolution
# ---------------------------------------------------------------------------

def c4_memory_evolution() -> str:
    me = MemoryEvolution(":memory:")
    text = "Agent-A plus Agent-B interaction"
    me.observe("s1", "C1", text, "INFERENCE", evidence_refs=["r"])
    me.observe("s2", "C1", text, "INFERENCE", evidence_refs=["r"])
    promoted = me.observe("s3", "C1", text, "INFERENCE", evidence_refs=["r"])
    assert promoted["state"] == "promoted", f"expected promoted, got {promoted['state']}"
    contra = me.observe("s4", "C1", text, "UNVERIFIED")
    assert contra["contradict_count"] >= 1, "contradiction not tracked"
    stats = me.stats()
    for ev in ("created", "reinforced", "promoted", "contradicted"):
        assert stats["by_event"].get(ev, 0) >= 1, f"missing lifecycle event: {ev}"
    assert me.mark_useful(contra["memory_key"], "s5")
    return f"events={stats['by_event']}"


# ---------------------------------------------------------------------------
# 5. Proof-carrying decisions
# ---------------------------------------------------------------------------

def c5_proof_chain() -> str:
    fr = FlightRecorder(":memory:")
    chain = fr.build_proof_chain(
        session_id="s", claim_id="C1", claim="synthetic claim",
        evidence_nodes=[{"ref": "claim:C1"}],
        worker_nodes=[{"worker": "w1", "tier": "EVIDENCE"}],
        challenge_nodes=[{"validator": "v1"}],
        validator_nodes=[{"validator": "v1", "tier": "UNVERIFIED"}],
        decision="UNVERIFIED",
    )
    assert chain["node_count"] == 6, chain["node_count"]
    assert fr.verify_proof_chain(chain["chain_id"]), "fresh chain must verify"
    explain = fr.explain(chain["chain_id"])
    assert explain["verified"] and explain["decision"] == "UNVERIFIED"
    fr._conn.execute("UPDATE proof_nodes SET payload=? WHERE chain_id=? AND ordinal=0",
                     ('{"claim":"TAMPERED"}', chain["chain_id"]))
    fr._conn.commit()
    assert not fr.verify_proof_chain(chain["chain_id"]), "tampering must be detected"
    return "verifies, and detects tampering"


# ---------------------------------------------------------------------------
# 6. Reputation
# ---------------------------------------------------------------------------

def c6_reputation() -> str:
    rl = ReputationLedger(":memory:")
    for _ in range(4):
        rl.observe_call("good", "PRIMARY", "EVIDENCE", True, confidence=0.9)
        rl.observe_call("sloppy", "PRIMARY", "UNVERIFIED", False, confidence=0.1)
    rl.observe_validation("good", True)
    rl.observe_challenge("good", upheld=True)
    rl.observe_trap("good", detected=True)
    rl.observe_challenge("sloppy", upheld=False)
    board = rl.leaderboard()
    assert board[0]["worker_id"] == "good", f"ranking wrong: {board}"
    g, s = rl.get("good"), rl.get("sloppy")
    assert g["validation_accuracy"] == 1.0
    assert g["reputation"] > s["reputation"], "reputation did not discriminate"
    w = rl.weights(["good", "sloppy"])
    assert abs(sum(w.values()) - 1.0) < 1e-4
    return f"good={g['reputation']:.3f} sloppy={s['reputation']:.3f}"


# ---------------------------------------------------------------------------
# 7. A/B experiments
# ---------------------------------------------------------------------------

def c7_ab_experiments() -> str:
    store = ExperimentStore(":memory:")
    eid = store.start_experiment("ab", "tier batch")
    a = VariantResult(Variant("A", workers=32), index=0.60, validated_insights=16,
                      total_tokens=1000, cost_usd=0.001)
    b = VariantResult(Variant("B", workers=64), index=0.75, validated_insights=40,
                      total_tokens=3000, cost_usd=0.003)
    store.record_variant(eid, a)
    store.record_variant(eid, b)
    cmp = store.compare(eid)
    assert cmp["best"] == "B", cmp["best"]
    assert cmp["worst"] == "A"
    assert cmp["index_spread"] > 0
    return f"best={cmp['best']} spread={cmp['index_spread']}"


# ---------------------------------------------------------------------------
# 8. Self-improvement loop
# ---------------------------------------------------------------------------

def c8_self_improvement() -> str:
    store = ExperimentStore(":memory:")
    eid = store.start_experiment("imp", "tier batch")
    loop = SelfImprovementLoop(store)
    comps = {"reliability": 1.0, "grounding": 1.0, "evidence_quality": 0.25,
             "challenge_resolution": 0.9, "validator_calibration": 1.0, "reproducibility": 0.8}
    assert loop.identify_weakness(comps) == "evidence_quality"
    rec = loop.run(eid, 0.60, comps, retest=lambda p: VariantResult(Variant("imp"), index=0.82))
    assert rec["applied"] and rec["accepted"] and rec["delta"] > 0, rec
    # a retest that does not improve must NOT be accepted
    rec2 = loop.run(eid, 0.80, comps, retest=lambda p: VariantResult(Variant("imp"), index=0.78))
    assert rec2["accepted"] is False, "regression wrongly accepted"
    return f"accepted={rec['delta']:+.3f}, regression rejected"


# ---------------------------------------------------------------------------
# 9. Cost / intelligence efficiency
# ---------------------------------------------------------------------------

def c9_efficiency() -> str:
    small = VariantResult(Variant("small", workers=32), index=0.60,
                          validated_insights=10, total_tokens=1000, cost_usd=0.001)
    big = VariantResult(Variant("big", workers=64), index=0.62,
                        validated_insights=12, total_tokens=4000, cost_usd=0.004)
    eff = efficiency([big, small])
    series = eff["series"]
    assert series[0]["workers"] == 32, "series not sorted by workers"
    assert series[1]["marginal_workers"] == 32
    assert series[1]["marginal_insights"] == 2
    assert series[1]["marginal_cost_per_insight_usd"] is not None
    assert abs(price_tokens("mercury-2", 1_000_000, 0) - 0.25) < 1e-9
    return f"marginal cost/insight=${series[1]['marginal_cost_per_insight_usd']}"


# ---------------------------------------------------------------------------
# 10. Genome / replay
# ---------------------------------------------------------------------------

def c10_genome() -> str:
    fr = FlightRecorder(":memory:")
    gene = {"model": "mercury-2", "workers": 64, "validators": 16,
            "concurrency": 32, "prompt_version": "v2", "arena": True}
    saved = fr.save_genome("s1", gene)
    assert fr.verify_genome("s1"), "genome hash mismatch"
    loaded = fr.load_genome("s1")
    assert loaded["gene"] == gene, "genome roundtrip changed content"
    assert saved["genome_hash"] == canonical_hash(gene)
    return f"hash={saved['genome_hash'][:16]}…"


CHECKS = [
    ("1. flight recorder", c1_flight_recorder),
    ("2. challenge arena", c2_arena),
    ("3. strength index + curve", c3_strength_index),
    ("4. memory evolution", c4_memory_evolution),
    ("5. proof-carrying decisions", c5_proof_chain),
    ("6. worker reputation", c6_reputation),
    ("7. A/B experiments", c7_ab_experiments),
    ("8. self-improvement loop", c8_self_improvement),
    ("9. cost/intelligence efficiency", c9_efficiency),
    ("10. swarm genome / replay", c10_genome),
]


def live_swarm_check() -> str:
    """Optional: drive a real swarm and assert the artifacts + index are produced."""
    import subprocess
    out = ROOT / "data" / "thinkboxmd"
    result = subprocess.run(
        [sys.executable, str(ROOT / "experiments" / "big_swarm.py"),
         "--primary", "24", "--validators", "8", "--concurrency", "16", "--arena"],
        capture_output=True, text=True, timeout=300, cwd=str(ROOT),
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
    return (f"{recon['total_calls']} calls · index={recon['strength']['index']} · "
            f"ledger={recon['ledger_valid']} · chain={data['proof_chain']['verified']}")


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
