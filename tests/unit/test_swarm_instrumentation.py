"""Unit tests for the swarm instrumentation layer (stdlib unittest)."""

from __future__ import annotations

import unittest

from thinkbox.arena import ChallengeArena, AdversarialProbe
from thinkbox.flightrecorder import FlightRecorder, WorkerRecord, canonical_hash
from thinkbox.memory_evolution import MemoryEvolution, topic_hash
from thinkbox.metrics import MetricsStore, compute_swarm_strength, TIER_CREDIT
from thinkbox.reputation import ReputationLedger
from thinkbox.experiments import (
    ExperimentStore, SelfImprovementLoop, Variant, VariantResult,
    efficiency, price_tokens,
)


class TestFlightRecorder(unittest.TestCase):
    def setUp(self) -> None:
        self.fr = FlightRecorder(":memory:")

    def test_record_and_retrieve(self) -> None:
        rec = WorkerRecord(
            session_id="s1", worker_id="w1", role="PRIMARY", model="mercury-2",
            prompt_version="v1", decision="UNVERIFIED", outcome="ok",
            total_tokens=100, latency_s=0.5, evidence_refs=["claim:X"],
        )
        self.fr.record(rec)
        rows = self.fr.session_records("s1")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["decision"], "UNVERIFIED")
        self.assertEqual(rows[0]["evidence_refs"], ["claim:X"])

    def test_record_is_idempotent(self) -> None:
        rec = WorkerRecord(session_id="s1", worker_id="w1", role="P", model="m", prompt_version="v1")
        self.fr.record(rec)
        self.fr.record(rec)
        self.assertEqual(self.fr.count("s1"), 1)

    def test_proof_chain_verifies_and_detects_tampering(self) -> None:
        chain = self.fr.build_proof_chain(
            session_id="s1", claim_id="C1", claim="synthetic claim",
            evidence_nodes=[{"ref": "claim:C1"}],
            worker_nodes=[{"worker": "w1", "tier": "UNVERIFIED"}],
            challenge_nodes=[{"validator": "v1", "disagreed": True}],
            validator_nodes=[{"validator": "v1", "tier": "UNVERIFIED"}],
            decision="UNVERIFIED",
        )
        self.assertTrue(self.fr.verify_proof_chain(chain["chain_id"]))
        self.assertEqual(chain["node_count"], 6)
        explain = self.fr.explain(chain["chain_id"])
        self.assertTrue(explain["verified"])
        self.assertEqual(explain["counts"]["evidence"], 1)
        # tamper with a stored node
        self.fr._conn.execute(
            "UPDATE proof_nodes SET payload=? WHERE chain_id=? AND ordinal=0",
            ('{"claim":"TAMPERED"}', chain["chain_id"]),
        )
        self.fr._conn.commit()
        self.assertFalse(self.fr.verify_proof_chain(chain["chain_id"]))

    def test_genome_roundtrip(self) -> None:
        gene = {"model": "mercury-2", "workers": 32, "prompt_version": "v1"}
        saved = self.fr.save_genome("s1", gene)
        self.assertTrue(self.fr.verify_genome("s1"))
        loaded = self.fr.load_genome("s1")
        self.assertEqual(loaded["gene"]["workers"], 32)
        self.assertEqual(saved["genome_hash"], canonical_hash(gene))

    def test_canonical_hash_is_order_independent(self) -> None:
        self.assertEqual(canonical_hash({"a": 1, "b": 2}), canonical_hash({"b": 2, "a": 1}))


class TestChallengeArena(unittest.TestCase):
    def test_builds_all_trap_types(self) -> None:
        arena = ChallengeArena()
        probes = arena.build_probes(n_per_type=2)
        types = {p.trap_type for p in probes}
        self.assertEqual(types, {"hallucination_trap", "tier_inflation_bait",
                                 "contradiction", "competing_answers"})
        self.assertEqual(len(probes), 8)

    def test_detection_scoring(self) -> None:
        arena = ChallengeArena()
        probe = AdversarialProbe("P1", "hallucination_trap", "fake citation",
                                 ["INFERENCE", "HYPOTHESIS", "UNVERIFIED"])
        # worker over-claims EVIDENCE -> not detected, validator corrects -> recovered
        o = arena.score(probe, "w1", "EVIDENCE", validator_tier="UNVERIFIED")
        self.assertFalse(o.detected)
        self.assertTrue(o.challenged)
        self.assertTrue(o.recovered)
        # worker downgrades -> detected
        o2 = arena.score(probe, "w2", "UNVERIFIED")
        self.assertTrue(o2.detected)
        self.assertFalse(o2.recovered)

    def test_report_rates(self) -> None:
        arena = ChallengeArena()
        probe = AdversarialProbe("P1", "tier_inflation_bait", "c",
                                 ["HYPOTHESIS", "UNVERIFIED"])
        arena.score(probe, "w1", "HYPOTHESIS")
        arena.score(probe, "w2", "EVIDENCE")
        rep = arena.report()
        self.assertEqual(rep["overall"]["probes"], 2)
        self.assertAlmostEqual(rep["overall"]["detection_rate"], 0.5)


class TestSwarmStrengthIndex(unittest.TestCase):
    def test_perfect_run(self) -> None:
        idx = compute_swarm_strength(
            total=10, ok=10, traces=10, grounded=10, validators=4,
            disagreements=2, validator_downgrades=2, tier_inflation=0,
            tier_distribution={"EVIDENCE": 4, "INFERENCE": 4, "HYPOTHESIS": 2,
                               "UNVERIFIED": 0},
            previous_distribution={"EVIDENCE": 4, "INFERENCE": 4, "HYPOTHESIS": 2,
                                   "UNVERIFIED": 0},
            previous_index=0.8,
        )
        self.assertGreater(idx.score, 0.8)
        self.assertAlmostEqual(idx.reliability, 1.0)
        self.assertAlmostEqual(idx.grounding, 1.0)
        self.assertAlmostEqual(idx.reproducibility, 1.0)
        self.assertAlmostEqual(idx.learning_delta, round(idx.score - 0.8, 4))

    def test_disagreement_is_activity_not_failure(self) -> None:
        """Challenging a lot must not zero the index."""
        low_challenge = compute_swarm_strength(
            total=10, ok=10, traces=10, grounded=10, validators=10,
            disagreements=0, validator_downgrades=0, tier_inflation=0,
            tier_distribution={"UNVERIFIED": 10},
        )
        high_challenge = compute_swarm_strength(
            total=10, ok=10, traces=10, grounded=10, validators=10,
            disagreements=10, validator_downgrades=10, tier_inflation=0,
            tier_distribution={"UNVERIFIED": 10},
        )
        # productive challenges should be *better*, never treated as failure
        self.assertGreater(high_challenge.score, low_challenge.score)
        self.assertAlmostEqual(high_challenge.challenge_activity, 1.0)

    def test_unknown_history_is_neutral(self) -> None:
        idx = compute_swarm_strength(
            total=4, ok=4, traces=4, grounded=4, validators=1, disagreements=0,
            validator_downgrades=0, tier_inflation=0, tier_distribution={"UNVERIFIED": 4},
            previous_distribution=None,
        )
        self.assertAlmostEqual(idx.reproducibility, 0.5)

    def test_honest_unverified_gets_credit(self) -> None:
        self.assertGreater(TIER_CREDIT["UNVERIFIED"], 0.0)
        self.assertGreater(TIER_CREDIT["EVIDENCE"], TIER_CREDIT["UNVERIFIED"])


class TestMetricsStore(unittest.TestCase):
    def test_session_token_challenge_strength_roundtrip(self) -> None:
        ms = MetricsStore(":memory:")
        ms.start_session("sess1", kind="big_swarm", model="mercury-2", concurrency=8)
        ms.record_tokens("sess1", "w1", "PRIMARY", "mercury-2",
                         {"prompt_tokens": 10, "completion_tokens": 20,
                          "total_tokens": 30,
                          "completion_tokens_details": {"reasoning_tokens": 12}},
                         0.4, True)
        ms.record_challenge("sess1", "C1", "EVIDENCE", "UNVERIFIED",
                            {"EVIDENCE": 0, "INFERENCE": 1, "HYPOTHESIS": 2, "UNVERIFIED": 3})
        idx = compute_swarm_strength(total=1, ok=1, traces=1, grounded=1, validators=1,
                                     disagreements=1, validator_downgrades=1, tier_inflation=0,
                                     tier_distribution={"UNVERIFIED": 1})
        ms.finish_session("sess1", 1, 1, 0, 1.0, 1.0, 5, True, "hash", idx)
        totals = ms.session_totals("sess1")
        self.assertEqual(totals["total_tokens"], 30)
        self.assertEqual(totals["reasoning_tokens"], 12)
        self.assertEqual(totals["challenged"], 1)
        trend = ms.trend("big_swarm")
        self.assertEqual(len(trend["runs"]), 1)
        prev = ms.previous_run("big_swarm")
        self.assertEqual(prev["session_id"], "sess1")


class TestMemoryEvolution(unittest.TestCase):
    def test_create_reinforce_contradict_promote(self) -> None:
        me = MemoryEvolution(":memory:")
        content = "Agent-A plus Agent-B has a documented interaction"
        me.observe("s1", "C1", content, "INFERENCE", evidence_refs=["ref1"])
        first = me.observe("s2", "C1", content, "INFERENCE", evidence_refs=["ref1"])
        self.assertGreaterEqual(first["reinforce_count"], 1)
        # second reinforcement with evidence crosses the promotion gate
        a = me.observe("s3", "C1", content, "INFERENCE", evidence_refs=["ref1"])
        self.assertGreaterEqual(a["reinforce_count"], 2)
        self.assertEqual(a["state"], "promoted")
        b = me.observe("s4", "C1", content, "UNVERIFIED")
        self.assertGreaterEqual(b["contradict_count"], 1)
        stats = me.stats()
        self.assertGreaterEqual(stats["by_event"].get("created", 0), 1)
        self.assertGreaterEqual(stats["by_event"].get("reinforced", 0), 1)
        self.assertGreaterEqual(stats["by_event"].get("promoted", 0), 1)
        self.assertGreaterEqual(stats["by_event"].get("contradicted", 0), 1)

    def test_same_concept_same_key(self) -> None:
        self.assertEqual(topic_hash("A  B"), topic_hash("a b"))

    def test_mark_useful(self) -> None:
        me = MemoryEvolution(":memory:")
        row = me.observe("s1", "C1", "some claim", "HYPOTHESIS")
        self.assertTrue(me.mark_useful(row["memory_key"], "s2", "retrieved"))
        self.assertEqual(me.get(row["memory_key"])["useful_count"], 1)


class TestReputation(unittest.TestCase):
    def test_reputation_accumulates(self) -> None:
        rl = ReputationLedger(":memory:")
        rl.start_run(["w1"], role="PRIMARY")
        for _ in range(4):
            rl.observe_call("w1", "PRIMARY", "INFERENCE", True, confidence=0.6)
        rl.observe_validation("w1", agreed=True)
        rl.observe_validation("w1", agreed=True)
        rl.observe_challenge("w1", upheld=True)
        rl.observe_trap("w1", detected=True)
        rep = rl.get("w1")
        self.assertEqual(rep["calls"], 4)
        self.assertAlmostEqual(rep["validation_accuracy"], 1.0)
        self.assertGreater(rep["reputation"], 0.8)

    def test_leaderboard_and_weights(self) -> None:
        rl = ReputationLedger(":memory:")
        for w in ("good", "bad"):
            rl.start_run([w])
        for _ in range(3):
            rl.observe_call("good", "P", "EVIDENCE", True, 0.9)
            rl.observe_call("bad", "P", "UNVERIFIED", False, 0.1)
        board = rl.leaderboard()
        self.assertEqual(board[0]["worker_id"], "good")
        weights = rl.weights(["good", "bad"])
        self.assertGreater(weights["good"], weights["bad"])
        self.assertAlmostEqual(sum(weights.values()), 1.0, places=4)


class TestExperiments(unittest.TestCase):
    def test_price_tokens(self) -> None:
        cost = price_tokens("mercury-2", 1_000_000, 0)
        self.assertAlmostEqual(cost, 0.25)
        self.assertEqual(price_tokens("unknown-model", 1000, 1000), 0.0)

    def test_ab_compare(self) -> None:
        store = ExperimentStore(":memory:")
        eid = store.start_experiment("abl", "tier batch")
        a = VariantResult(Variant("A", workers=32), index=0.6, workers_ok=32,
                          validated_insights=16, total_tokens=1000, cost_usd=0.001, wall_seconds=2.0)
        b = VariantResult(Variant("B", workers=64), index=0.75, workers_ok=64,
                          validated_insights=40, total_tokens=3000, cost_usd=0.003, wall_seconds=4.0)
        store.record_variant(eid, a)
        store.record_variant(eid, b)
        cmp = store.compare(eid)
        self.assertEqual(cmp["best"], "B")
        self.assertEqual(cmp["n_variants"], 2)
        self.assertGreater(cmp["index_spread"], 0)

    def test_self_improvement_loop(self) -> None:
        store = ExperimentStore(":memory:")
        eid = store.start_experiment("imp", "tier batch")
        loop = SelfImprovementLoop(store)
        comps = {"reliability": 1.0, "grounding": 1.0, "evidence_quality": 0.3,
                 "challenge_resolution": 0.9, "validator_calibration": 1.0,
                 "reproducibility": 0.8}
        self.assertEqual(loop.identify_weakness(comps), "evidence_quality")

        def retest(proposal):
            return VariantResult(Variant("improved"), index=0.8)

        rec = loop.run(eid, baseline_index=0.6, baseline_components=comps, retest=retest)
        self.assertTrue(rec["applied"])
        self.assertTrue(rec["accepted"])
        self.assertGreater(rec["delta"], 0)

    def test_efficiency_marginal(self) -> None:
        small = VariantResult(Variant("small", workers=32), index=0.6,
                              validated_insights=10, total_tokens=1000, cost_usd=0.001)
        big = VariantResult(Variant("big", workers=64), index=0.62,
                            validated_insights=12, total_tokens=4000, cost_usd=0.004)
        eff = efficiency([big, small])
        series = eff["series"]
        self.assertEqual(series[0]["workers"], 32)   # sorted ascending
        self.assertEqual(series[1]["marginal_workers"], 32)
        self.assertEqual(series[1]["marginal_insights"], 2)
        self.assertIsNotNone(series[1]["marginal_cost_per_insight_usd"])
        self.assertIsNotNone(eff["cheapest_insight"])


class TestEconomyRegression(unittest.TestCase):
    """Regression: transfer() must not deadlock on a brand-new recipient.

    It previously called create_account() while already holding the same
    non-reentrant lock, hanging the caller forever.
    """

    def test_transfer_to_new_recipient_does_not_deadlock(self) -> None:
        from thinkbox.economy import AgentTokenEconomy
        import threading

        economy = AgentTokenEconomy()
        economy.create_account("alice", 100)
        done: list[bool] = []

        def run() -> None:
            done.append(economy.transfer("alice", "brand_new", 10))

        t = threading.Thread(target=run, daemon=True)
        t.start()
        t.join(timeout=5)
        self.assertFalse(t.is_alive(), "transfer() deadlocked on a new recipient")
        self.assertEqual(done, [True])
        self.assertEqual(economy.get_balance("brand_new"), 10)


class TestPipelineDashboard(unittest.TestCase):
    """Pipeline tab: rebuilt entirely from persistent storage, no singletons."""

    @staticmethod
    def _load_dashboard():
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "swarm_dashboard", "experiments/swarm_dashboard.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_pipeline_endpoint_rebuilds_from_storage(self) -> None:
        dash = self._load_dashboard()
        pipe = dash._pipeline()
        self.assertIn("jobs", pipe)
        self.assertIn("totals", pipe)
        self.assertIn("lessons", pipe)
        self.assertIn("retrievals", pipe)
        self.assertIn("memory", pipe)
        self.assertIn("verification_state", pipe)
        self.assertIn("blockers", pipe)
        self.assertIn("next_larger_improvement", pipe)
        self.assertGreaterEqual(pipe["totals"]["experiments"], 1)
        self.assertGreaterEqual(pipe["totals"]["outcomes"], 1)

    def test_pipeline_recovers_after_singleton_reset(self) -> None:
        from thinkbox.dashboard_state import get_dashboard_state
        st = get_dashboard_state()
        saved_jobs = dict(st.think_jobs)
        saved_events = list(st.events)
        try:
            st.think_jobs.clear()
            st.events.clear()
            self.assertEqual(len(get_dashboard_state().get_state()["think_jobs"]), 0)
            pipe = self._load_dashboard()._pipeline()
            self.assertGreaterEqual(pipe["totals"]["experiments"], 1)
            job_ids = {j["job_id"] for j in pipe["jobs"]}
            self.assertTrue(any(j.startswith("tb_exp_") for j in job_ids))
        finally:
            st.think_jobs.update(saved_jobs)
            st.events.extend(saved_events)

    def test_pipeline_exposes_learning_provenance(self) -> None:
        pipe = self._load_dashboard()._pipeline()
        jobs_by_id = {j["job_id"]: j for j in pipe["jobs"]}
        self.assertIn("tb_exp_20260917170533_fbb1ec84", jobs_by_id)
        self.assertIn("tb_exp_20260917170605_a1ae355e", jobs_by_id)
        learned = jobs_by_id["tb_exp_20260917170605_a1ae355e"]
        self.assertEqual(learned["lesson_source"], "tb_exp_20260917170533_fbb1ec84")
        mem_keys = {m["key"] for m in pipe["memory"]}
        self.assertIn("learn:exact-json:directive", mem_keys)
        model_jobs = pipe["verification_state"]["model"]["verified_jobs"]
        self.assertIn("tb_exp_20260917170605_a1ae355e", model_jobs)

    def test_pipeline_contains_no_secrets(self) -> None:
        import json
        import re
        raw = json.dumps(self._load_dashboard()._pipeline())
        self.assertEqual(re.findall(r"(?i)(api[_-]?key|bearer|authorization)", raw), [])
        self.assertNotIn("ucat_", raw)


class TestPopulationArena(unittest.TestCase):
    """300-instance Arena control surface: deterministic, no live calls."""

    def test_population_is_300_with_stable_ids(self) -> None:
        from thinkbox.pop_arena import build_population, POPULATION_SIZE
        tasks = build_population()
        self.assertEqual(len(tasks), POPULATION_SIZE)
        self.assertEqual(len({t.task_id for t in tasks}), POPULATION_SIZE)
        self.assertEqual(build_population()[0].task_id, tasks[0].task_id)

    def test_baseline_learned_separation(self) -> None:
        from thinkbox.pop_arena import build_population
        tasks = build_population()
        base = [t for t in tasks if t.strategy == "baseline"]
        learned = [t for t in tasks if t.strategy == "learned"]
        self.assertEqual(len(base), 150)
        self.assertEqual(len(learned), 150)

    def test_live_replay_separation(self) -> None:
        from thinkbox.pop_arena import build_population
        tasks = build_population()
        live = [t for t in tasks if t.origin == "live"]
        replay = [t for t in tasks if t.origin == "replay"]
        self.assertEqual(len(live), 12)
        self.assertEqual(len(replay), 288)

    def test_replay_emission_verifies(self) -> None:
        from thinkbox.pop_arena import (
            build_population, deterministic_emission, extract_json, verify_property,
        )
        for t in build_population():
            self.assertTrue(verify_property(extract_json(deterministic_emission(t.variant, t.expected)), t.expected))

    def test_ceiling_effect_classification(self) -> None:
        from thinkbox.pop_arena import classify_arena
        cls, _ = classify_arena(150, 150, 150, 150, 6, 6)
        self.assertEqual(cls, "NO_MEASURABLE_IMPROVEMENT")
        cls2, _ = classify_arena(3, 6, 6, 6, 6, 6)
        self.assertEqual(cls2, "IMPROVED")
        cls3, _ = classify_arena(0, 0, 0, 0, 0, 0)
        self.assertEqual(cls3, "INCONCLUSIVE")

    def test_arena_lifecycle_transitions(self) -> None:
        import shutil
        import tempfile
        from thinkbox.pop_arena import ArenaConfig, ArenaRun
        tmp = tempfile.mktemp(suffix=".db")
        art = tempfile.mkdtemp()
        try:
            run = ArenaRun(ArenaConfig(), db_path=tmp, artifacts_dir=art)
            self.assertEqual(run.state()["state"], "NOT_RUN")
            eid = run.configure(agent_id="test")
            self.assertEqual(run.state()["state"], "CONFIGURED")
            run.transition(eid, "arena_started", {"live_budget": 12})
            self.assertEqual(run.state()["state"], "RUNNING")
            run.transition(eid, "arena_completed", {"classification": "INCONCLUSIVE"})
            self.assertEqual(run.state()["state"], "COMPLETE")
        finally:
            import os
            if os.path.exists(tmp):
                os.unlink(tmp)
            shutil.rmtree(art, ignore_errors=True)

    def test_arena_aggregate_rebuilds_from_storage(self) -> None:
        import shutil
        import tempfile
        from thinkbox.experiment import ExperimentManager
        from thinkbox.pop_arena import ArenaConfig, ArenaRun, build_population
        tmp = tempfile.mktemp(suffix=".db")
        art = tempfile.mkdtemp()
        try:
            run = ArenaRun(ArenaConfig(), db_path=tmp, artifacts_dir=art)
            run.configure(agent_id="test")
            mgr = ExperimentManager(db_path=tmp, artifacts_dir=art)
            mgr.create_session(agent_id="test")
            for t in build_population()[:6]:
                e = mgr.create_experiment(intent="arena-inst", hypothesis="h", parameters={}, agent_id="test", execution_mode="upstash-box")
                run.record_instance(t, e.experiment_id, True, latency_s=0.1, tokens=10, artifact_sha256="abc")
            agg = run.aggregate()
            self.assertEqual(agg.total, 6)
            self.assertEqual(agg.verified, 6)
        finally:
            import os
            if os.path.exists(tmp):
                os.unlink(tmp)
            shutil.rmtree(art, ignore_errors=True)

    def test_arena_proof_secrets_clean(self) -> None:
        from thinkbox.pop_arena import secrets_clean
        self.assertTrue(secrets_clean({"classification": "NO_MEASURABLE_IMPROVEMENT", "live": 12}))
        self.assertFalse(secrets_clean({"api_key": "x" * 25}))

    def test_v2_task_ids_stable_and_namespaced(self) -> None:
        from thinkbox.pop_arena import task_id_for_v2, FAMILY_V2, V2_VARIANTS
        ids = set()
        for fam in FAMILY_V2:
            for var in V2_VARIANTS[fam]:
                tid = task_id_for_v2(fam, var, 0)
                self.assertTrue(tid.startswith("arena2_"))
                self.assertEqual(tid, task_id_for_v2(fam, var, 0))
                ids.add(tid)
        self.assertEqual(len(ids), 18)

    def test_v2_replay_emission_verifies(self) -> None:
        from thinkbox.pop_arena import (
            system_prompt_for_v2, verify_v2, deterministic_emission_v2,
            extract_json, FAMILY_V2, V2_VARIANTS,
        )
        for fam in FAMILY_V2:
            for var in V2_VARIANTS[fam]:
                _, spec = system_prompt_for_v2(fam, var)
                ok, tax = verify_v2(fam, extract_json(deterministic_emission_v2(fam, var, spec)), spec)
                self.assertTrue(ok, f"{fam}/{var}")
                self.assertEqual(tax, "valid")

    def test_v2_taxonomy_reachable(self) -> None:
        from thinkbox.pop_arena import verify_v2
        self.assertEqual(verify_v2("compute", {"answer": 999}, {"expected": 13})[1], "arithmetic")
        self.assertEqual(verify_v2("compute", {"result": 13}, {"expected": 13})[1], "wrong-key")
        self.assertEqual(verify_v2("compute", "no json here", {"expected": 13})[1], "parse-fail")
        self.assertEqual(verify_v2("distractor", {"result": 37}, {"expected": 37})[1], "distractor-compliance")
        self.assertEqual(
            verify_v2("multifield", {"answer": 8, "parity": "odd", "double": 16},
                      {"expected": 8, "parity": "even", "double": 16})[1], "inconsistency")

    def test_v2_no_answer_leak_beyond_demand(self) -> None:
        from thinkbox.pop_arena import system_prompt_for_v2, FAMILY_V2, V2_VARIANTS
        for fam in FAMILY_V2:
            for var in V2_VARIANTS[fam]:
                prompt, spec = system_prompt_for_v2(fam, var)
                if fam == "compute":
                    self.assertNotIn(str(spec["expected"]), prompt)


if __name__ == "__main__":
    unittest.main()
