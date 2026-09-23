"""Hermetic swarm instrumentation checks (shared by experiments verifier and KILO gate).

Each check is self-contained and uses ``:memory:`` SQLite where persistence is needed.
No network I/O. The optional live swarm check lives in ``experiments/verify_instrumentation``
only (``--live``); this module exposes exactly ten hermetic instrument checks; the eleventh live swarm check stays in experiments only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from thinkbox.arena import ChallengeArena
from thinkbox.experiments import (
    ExperimentStore,
    SelfImprovementLoop,
    Variant,
    VariantResult,
    efficiency,
    price_tokens,
)
from thinkbox.flightrecorder import FlightRecorder, WorkerRecord, canonical_hash
from thinkbox.memory_evolution import MemoryEvolution
from thinkbox.metrics import MetricsStore, compute_swarm_strength
from thinkbox.reputation import ReputationLedger

__all__ = (
    "HERMETIC_INSTRUMENTATION_CHECK_COUNT",
    "InstrumentationCheckResult",
    "hermetic_instrumentation_catalog",
    "run_hermetic_instrumentation_checks",
)

HERMETIC_INSTRUMENTATION_CHECK_COUNT = 10


@dataclass(frozen=True)
class InstrumentationCheckResult:
    """Outcome of one hermetic instrumentation check."""

    check_id: str
    name: str
    ok: bool
    detail: str = ""

    def to_dict(self) -> dict[str, str | bool]:
        return {
            "check_id": self.check_id,
            "name": self.name,
            "ok": self.ok,
            "detail": self.detail,
        }


def c1_flight_recorder() -> str:
    fr = FlightRecorder(":memory:")
    fr.record(
        WorkerRecord(
            session_id="s",
            worker_id="w1",
            role="PRIMARY",
            model="m",
            prompt_version="v1",
            decision="UNVERIFIED",
            outcome="ok",
            total_tokens=42,
            latency_s=0.3,
            evidence_refs=["claim:C1"],
            reasoning_tokens=10,
        )
    )
    rows = fr.session_records("s")
    assert len(rows) == 1, "record not retrievable"
    r = rows[0]
    for k in (
        "trace_id",
        "model",
        "prompt_version",
        "total_tokens",
        "latency_s",
        "decision",
        "challenge",
        "validator_result",
        "evidence_refs",
        "outcome",
    ):
        assert k in r, f"missing durable field: {k}"
    assert r["evidence_refs"] == ["claim:C1"], "evidence refs not preserved"
    return f"{len(r)} fields retained"


def c2_arena() -> str:
    arena = ChallengeArena()
    probes = arena.build_probes(n_per_type=2)
    types = {p.trap_type for p in probes}
    assert types == {
        "hallucination_trap",
        "tier_inflation_bait",
        "contradiction",
        "competing_answers",
    }, types
    probe = next(p for p in probes if p.trap_type == "hallucination_trap")
    bad = arena.score(probe, "w1", "EVIDENCE", validator_tier="UNVERIFIED")
    assert not bad.detected, "over-claim wrongly counted as detected"
    assert bad.recovered, "over-claim + corrective validator should be a recovery"
    good = arena.score(probe, "w2", "UNVERIFIED")
    assert good.detected and not good.recovered
    rep = arena.report()
    assert rep["overall"]["probes"] == 2
    return f"{len(types)} trap types, detection={rep['overall']['detection_rate']}"


def c3_strength_index() -> str:
    prev_dist = {"EVIDENCE": 4, "INFERENCE": 4, "HYPOTHESIS": 2, "UNVERIFIED": 0}
    idx = compute_swarm_strength(
        total=10,
        ok=10,
        traces=10,
        grounded=10,
        validators=4,
        disagreements=4,
        validator_downgrades=4,
        tier_inflation=0,
        tier_distribution=prev_dist,
        previous_distribution=prev_dist,
        previous_index=0.70,
    )
    assert 0.0 <= idx.score <= 1.0, "index out of range"
    assert abs(idx.reliability - 1.0) < 1e-9
    assert abs(idx.grounding - 1.0) < 1e-9
    assert abs(idx.reproducibility - 1.0) < 1e-9
    assert idx.learning_delta is not None

    quiet = compute_swarm_strength(
        total=4,
        ok=4,
        traces=4,
        grounded=4,
        validators=4,
        disagreements=0,
        validator_downgrades=0,
        tier_inflation=0,
        tier_distribution={"UNVERIFIED": 4},
    )
    loud = compute_swarm_strength(
        total=4,
        ok=4,
        traces=4,
        grounded=4,
        validators=4,
        disagreements=4,
        validator_downgrades=4,
        tier_inflation=0,
        tier_distribution={"UNVERIFIED": 4},
    )
    assert loud.score > quiet.score, "productive challenges must help, not hurt"

    ms = MetricsStore(":memory:")
    ms.start_session("s1", "big_swarm", "m", 8)
    ms.finish_session("s1", 4, 4, 0, 1.0, 4.0, 5, True, "h", idx)
    trend = ms.trend("big_swarm")
    assert len(trend["points"]) == 1, "learning curve point missing"
    return f"index={idx.score:.3f} delta={idx.learning_delta}"


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


def c5_proof_chain() -> str:
    fr = FlightRecorder(":memory:")
    chain = fr.build_proof_chain(
        session_id="s",
        claim_id="C1",
        claim="synthetic claim",
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
    fr._conn.execute(
        "UPDATE proof_nodes SET payload=? WHERE chain_id=? AND ordinal=0",
        ('{"claim":"TAMPERED"}', chain["chain_id"]),
    )
    fr._conn.commit()
    assert not fr.verify_proof_chain(chain["chain_id"]), "tampering must be detected"
    return "verifies, and detects tampering"


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


def c7_ab_experiments() -> str:
    store = ExperimentStore(":memory:")
    eid = store.start_experiment("ab", "tier batch")
    a = VariantResult(
        Variant("A", workers=32),
        index=0.60,
        validated_insights=16,
        total_tokens=1000,
        cost_usd=0.001,
    )
    b = VariantResult(
        Variant("B", workers=64),
        index=0.75,
        validated_insights=40,
        total_tokens=3000,
        cost_usd=0.003,
    )
    store.record_variant(eid, a)
    store.record_variant(eid, b)
    cmp = store.compare(eid)
    assert cmp["best"] == "B", cmp["best"]
    assert cmp["worst"] == "A"
    assert cmp["index_spread"] > 0
    return f"best={cmp['best']} spread={cmp['index_spread']}"


def c8_self_improvement() -> str:
    store = ExperimentStore(":memory:")
    eid = store.start_experiment("imp", "tier batch")
    loop = SelfImprovementLoop(store)
    comps = {
        "reliability": 1.0,
        "grounding": 1.0,
        "evidence_quality": 0.25,
        "challenge_resolution": 0.9,
        "validator_calibration": 1.0,
        "reproducibility": 0.8,
    }
    assert loop.identify_weakness(comps) == "evidence_quality"
    rec = loop.run(
        eid,
        0.60,
        comps,
        retest=lambda p: VariantResult(Variant("imp"), index=0.82),
    )
    assert rec["applied"] and rec["accepted"] and rec["delta"] > 0, rec
    rec2 = loop.run(
        eid,
        0.80,
        comps,
        retest=lambda p: VariantResult(Variant("imp"), index=0.78),
    )
    assert rec2["accepted"] is False, "regression wrongly accepted"
    return f"accepted={rec['delta']:+.3f}, regression rejected"


def c9_efficiency() -> str:
    small = VariantResult(
        Variant("small", workers=32),
        index=0.60,
        validated_insights=10,
        total_tokens=1000,
        cost_usd=0.001,
    )
    big = VariantResult(
        Variant("big", workers=64),
        index=0.62,
        validated_insights=12,
        total_tokens=4000,
        cost_usd=0.004,
    )
    eff = efficiency([big, small])
    series = eff["series"]
    assert series[0]["workers"] == 32, "series not sorted by workers"
    assert series[1]["marginal_workers"] == 32
    assert series[1]["marginal_insights"] == 2
    assert series[1]["marginal_cost_per_insight_usd"] is not None
    assert abs(price_tokens("mercury-2", 1_000_000, 0) - 0.25) < 1e-9
    return f"marginal cost/insight=${series[1]['marginal_cost_per_insight_usd']}"


def c10_genome() -> str:
    fr = FlightRecorder(":memory:")
    gene = {
        "model": "mercury-2",
        "workers": 64,
        "validators": 16,
        "concurrency": 32,
        "prompt_version": "v2",
        "arena": True,
    }
    saved = fr.save_genome("s1", gene)
    assert fr.verify_genome("s1"), "genome hash mismatch"
    loaded = fr.load_genome("s1")
    assert loaded["gene"] == gene, "genome roundtrip changed content"
    assert saved["genome_hash"] == canonical_hash(gene)
    return f"hash={saved['genome_hash'][:16]}…"


_HERMETIC_CHECKS: tuple[tuple[str, str, Callable[[], str]], ...] = (
    ("inst-01", "1. flight recorder", c1_flight_recorder),
    ("inst-02", "2. challenge arena", c2_arena),
    ("inst-03", "3. strength index + curve", c3_strength_index),
    ("inst-04", "4. memory evolution", c4_memory_evolution),
    ("inst-05", "5. proof-carrying decisions", c5_proof_chain),
    ("inst-06", "6. worker reputation", c6_reputation),
    ("inst-07", "7. A/B experiments", c7_ab_experiments),
    ("inst-08", "8. self-improvement loop", c8_self_improvement),
    ("inst-09", "9. cost/intelligence efficiency", c9_efficiency),
    ("inst-10", "10. swarm genome / replay", c10_genome),
)


def hermetic_instrumentation_catalog() -> tuple[dict[str, str], ...]:
    """Stable catalog entries for the ten hermetic instrumentation checks."""
    return tuple(
        {"check_id": cid, "name": name, "hermetic": "true", "live_swarm": "false"}
        for cid, name, _fn in _HERMETIC_CHECKS
    )


def run_hermetic_instrumentation_checks() -> list[InstrumentationCheckResult]:
    """Run all hermetic instrumentation checks (no network)."""
    results: list[InstrumentationCheckResult] = []
    for check_id, name, fn in _HERMETIC_CHECKS:
        try:
            detail = fn() or ""
            results.append(
                InstrumentationCheckResult(
                    check_id=check_id,
                    name=name,
                    ok=True,
                    detail=str(detail),
                )
            )
        except AssertionError as exc:
            results.append(
                InstrumentationCheckResult(
                    check_id=check_id,
                    name=name,
                    ok=False,
                    detail=str(exc),
                )
            )
        except Exception as exc:  # noqa: BLE001 — surface instrument failures
            results.append(
                InstrumentationCheckResult(
                    check_id=check_id,
                    name=name,
                    ok=False,
                    detail=f"{type(exc).__name__}: {exc}",
                )
            )
    return results


def hermetic_checks_tuple_for_experiments() -> list[tuple[str, Callable[[], str]]]:
    """Compatibility shim for ``experiments/verify_instrumentation.py``."""
    return [(name, fn) for _cid, name, fn in _HERMETIC_CHECKS]
