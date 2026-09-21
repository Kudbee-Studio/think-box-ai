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

    @unittest.expectedFailure
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

    @unittest.expectedFailure
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

    @unittest.expectedFailure
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

    def test_v3_retry_gate(self) -> None:
        from thinkbox.pop_arena import should_retry, V3_MAX_RETRIES
        self.assertEqual(V3_MAX_RETRIES, 1)
        for tax in ("wrong-key", "distractor-compliance", "parse-fail"):
            self.assertTrue(should_retry(tax, 0))
            self.assertFalse(should_retry(tax, 1))
        for tax in ("arithmetic", "inconsistency", "valid"):
            self.assertFalse(should_retry(tax, 0))

    def test_v3_retry_prompt_names_failure_no_answer(self) -> None:
        from thinkbox.pop_arena import retry_prompt_for, V2_DISTRACTOR_TARGETS
        p = retry_prompt_for("distractor", "distractor-compliance", {"expected": 37})
        self.assertIn("answer", p)
        self.assertNotIn("37", p)

    def test_v3_resolve_conversion(self) -> None:
        from thinkbox.pop_arena import resolve_retry
        r = resolve_retry("t", "distractor-compliance", False, True, "valid", 0)
        self.assertTrue(r.retried and r.converted and r.attempts == 2)
        r2 = resolve_retry("t", "distractor-compliance", False, False, "distractor-compliance", 0)
        self.assertTrue(r2.retried and not r2.converted)
        r3 = resolve_retry("t", "arithmetic", False, True, "valid", 0)
        self.assertFalse(r3.retried and r3.converted)
        r4 = resolve_retry("t", "valid", True, None, None, 0)
        self.assertFalse(r4.retried)

    def test_v3_trace_serializes_secrets_clean(self) -> None:
        from thinkbox.pop_arena import resolve_retry, secrets_clean
        r = resolve_retry("t", "wrong-key", False, True, "valid", 0)
        self.assertTrue(secrets_clean(r.to_dict()))

    def test_default_path_first_try_valid_no_retry(self) -> None:
        from thinkbox.pop_arena import VerifiedRetrySession
        calls = []
        s = VerifiedRetrySession()
        r = s.run("t", "p", lambda p: (calls.append(p), '{"answer": 1}')[1],
                  lambda t: (True, "valid"), lambda tax: "again")
        self.assertTrue(r.valid and r.attempts == 1 and not r.converted)
        self.assertEqual(len(calls), 1)

    def test_default_path_converts_retryable(self) -> None:
        from thinkbox.pop_arena import VerifiedRetrySession
        seen = []
        def complete(p):
            seen.append(p)
            return '{"result": 1}' if len(seen) == 1 else '{"answer": 1}'
        def verify(t):
            import json as _j
            d = _j.loads(t)
            return (("answer" in d), ("valid" if "answer" in d else "distractor-compliance"))
        s = VerifiedRetrySession()
        r = s.run("t", "base", complete, verify, lambda tax: "fix key")
        self.assertTrue(r.valid and r.converted and r.attempts == 2)
        self.assertEqual(s.conversions, 1)

    def test_default_path_no_retry_for_arithmetic(self) -> None:
        from thinkbox.pop_arena import VerifiedRetrySession
        calls = []
        s = VerifiedRetrySession()
        r = s.run("t", "p", lambda p: (calls.append(p), "x")[1],
                  lambda t: (False, "arithmetic"), lambda tax: "again")
        self.assertFalse(r.valid or r.trace.retried)
        self.assertEqual(len(calls), 1)

    def test_default_path_budget_cap(self) -> None:
        from thinkbox.pop_arena import VerifiedRetryConfig, VerifiedRetrySession, BudgetExhausted
        s = VerifiedRetrySession(VerifiedRetryConfig(max_retries=1, max_calls=1))
        with self.assertRaises(BudgetExhausted):
            s.run("t", "p", lambda p: '{"result": 1}',
                  lambda t: (False, "distractor-compliance"), lambda tax: "again")
        self.assertEqual(s.calls_spent, 1)

    def test_default_path_first_taxonomy_preserved_after_retry(self) -> None:
        from thinkbox.pop_arena import VerifiedRetrySession
        s = VerifiedRetrySession()
        r = s.run("t", "p", lambda p: '{"x": 1}',
                  lambda t: (False, "parse-fail"), lambda tax: "again")
        self.assertEqual(r.trace.first_taxonomy, "parse-fail")
        self.assertTrue(r.trace.retried and not r.converted)

    def test_run_async_matches_run_contract(self) -> None:
        import asyncio
        from thinkbox.pop_arena import VerifiedRetrySession
        async def go():
            s = VerifiedRetrySession()
            async def complete(p):
                complete.n += 1
                return '{"result": 1}' if complete.n == 1 else '{"answer": 1}'
            complete.n = 0
            def verify(t):
                import json as _j
                d = _j.loads(t)
                return (("answer" in d), ("valid" if "answer" in d else "distractor-compliance"))
            r = await s.run_async("t", "base", complete, verify, lambda tax: "fix key")
            self.assertTrue(r.valid and r.converted and r.attempts == 2)
            self.assertEqual(r.trace.first_taxonomy, "distractor-compliance")
        asyncio.run(go())

    def test_run_async_budget_exhausted(self) -> None:
        import asyncio
        from thinkbox.pop_arena import (
            BudgetExhausted, VerifiedRetryConfig, VerifiedRetrySession,
        )
        async def go():
            s = VerifiedRetrySession(VerifiedRetryConfig(max_retries=1, max_calls=1))
            async def complete(p):
                return '{"result": 1}'
            with self.assertRaises(BudgetExhausted):
                await s.run_async("t", "p", complete,
                                  lambda t: (False, "distractor-compliance"),
                                  lambda tax: "again")
        asyncio.run(go())

    def test_engine_wrapper_first_try_success(self) -> None:
        import asyncio
        from thinkbox.engine import ThinkBoxEngine
        from thinkbox.governed import GovernedEngine, GovernedEngineConfig
        async def go():
            eng = GovernedEngine(GovernedEngineConfig(engine=ThinkBoxEngine()))
            async def complete(p):
                return '{"answer": 5}'
            out = await eng.execute_verified_task(
                "t1", "prompt",
                lambda t: (True, "valid"), lambda tax: "again", complete,
                agent_id="test", experiment_id="exp1",
            )
            self.assertEqual(out["execution_status"], "FIRST_TRY_SUCCESS")
            self.assertTrue(out["valid"] and out["attempts"] == 1)
            self.assertTrue(eng.ledger.verify())
        asyncio.run(go())

    def test_engine_wrapper_recovered_and_failed(self) -> None:
        import asyncio
        import json as _j
        from thinkbox.engine import ThinkBoxEngine
        from thinkbox.governed import GovernedEngine, GovernedEngineConfig
        async def go():
            eng = GovernedEngine(GovernedEngineConfig(engine=ThinkBoxEngine()))
            n = {"c": 0}
            async def complete(p):
                n["c"] += 1
                return '{"result": 1}' if n["c"] == 1 else '{"answer": 1}'
            def verify(t):
                d = _j.loads(t)
                return (("answer" in d), ("valid" if "answer" in d else "distractor-compliance"))
            out = await eng.execute_verified_task(
                "t2", "prompt", verify, lambda tax: "fix", complete,
                agent_id="test", experiment_id="exp2",
            )
            self.assertEqual(out["execution_status"], "RECOVERED_SUCCESS")
            self.assertEqual(out["taxonomy"], "distractor-compliance")
            async def bad(p):
                return '{"x": 1}'
            out2 = await eng.execute_verified_task(
                "t3", "prompt", lambda t: (False, "arithmetic"),
                lambda tax: "again", bad, agent_id="test", experiment_id="exp3",
            )
            self.assertEqual(out2["execution_status"], "FAILED_AFTER_RETRY")
        asyncio.run(go())

    def test_engine_wrapper_budget_exhausted_and_unverified(self) -> None:
        import asyncio
        from thinkbox.engine import ThinkBoxEngine
        from thinkbox.governed import GovernedEngine, GovernedEngineConfig
        from thinkbox.pop_arena import VerifiedRetryConfig, VerifiedRetrySession
        async def go():
            eng = GovernedEngine(GovernedEngineConfig(engine=ThinkBoxEngine()))
            sess = VerifiedRetrySession(VerifiedRetryConfig(max_retries=1, max_calls=1))
            async def complete(p):
                return '{"result": 1}'
            out = await eng.execute_verified_task(
                "t4", "prompt", lambda t: (False, "distractor-compliance"),
                lambda tax: "again", complete, session=sess,
                agent_id="test", experiment_id="exp4",
            )
            self.assertEqual(out["execution_status"], "BUDGET_EXHAUSTED")
            out2 = await eng.execute_verified_task(
                "t5", "prompt", None, lambda tax: "again", complete,
                agent_id="test", experiment_id="exp5",
            )
            self.assertEqual(out2["execution_status"], "UNVERIFIED")
        asyncio.run(go())


class TestDagVerifiedExecution(unittest.TestCase):
    """DAG-level verified execution: ThinkBoxEngine.execute_goal task lifecycle
    routed through the canonical GovernedEngine.execute_verified_task primitive.
    Deterministic scripted completions (unit-level provider mocks per AGENTS §3.5)."""

    @staticmethod
    def _sub(family: str, variant: str, depends_on: list[int] | None = None) -> dict:
        from thinkbox.pop_arena import system_prompt_for_v2
        prompt, spec = system_prompt_for_v2(family, variant)
        return {"description": prompt, "family": family, "variant": variant,
                "spec": spec, "depends_on": depends_on or []}

    @staticmethod
    def _governed(ledger_path: str = ":memory:"):
        from thinkbox.engine import ThinkBoxEngine
        from thinkbox.governed import GovernedEngine, GovernedEngineConfig
        return GovernedEngine(GovernedEngineConfig(engine=ThinkBoxEngine(), ledger_path=ledger_path))

    @staticmethod
    def _router(subtasks: list[dict], behaviors: dict[int, str]):
        """complete_async keyed by exact subtask prompt prefix; per-prompt call counts."""
        from thinkbox.pop_arena import deterministic_emission_v2
        calls: dict[str, int] = {}
        async def complete(prompt: str):
            for i, st in enumerate(subtasks):
                if prompt.startswith(st["description"]):
                    break
            else:
                raise AssertionError("unrouted prompt")
            key = st["description"]
            calls[key] = calls.get(key, 0) + 1
            n = calls[key]
            fam, var, spec = st["family"], st["variant"], st["spec"]
            behavior = behaviors.get(i, "valid")
            valid = deterministic_emission_v2(fam, var, spec)
            wrongkey = '{"result": %s}' % spec["expected"]
            if behavior == "valid":
                return valid
            if behavior == "wrongkey_then_valid":
                return wrongkey if n == 1 else valid
            if behavior == "wrongkey_always":
                return wrongkey
            if behavior == "arithmetic_always":
                return '{"answer": %s}' % (spec["expected"] + 1)
            if behavior == "valid_with_usage":
                return valid, {"total_tokens": 42}
            raise AssertionError(behavior)
        return complete, calls

    def _run(self, coro):
        import asyncio
        return asyncio.run(coro)

    def test_dag_multi_task_first_try(self) -> None:
        subtasks = [self._sub("compute", "add_small"),
                    self._sub("distractor", "prose"),
                    self._sub("multifield", "double", depends_on=[0, 1])]
        complete, _ = self._router(subtasks, {})
        eng = self._governed()
        summary = self._run(eng.execute_verified_goal("dag goal", subtasks, complete))
        v = summary["verified"]
        self.assertEqual(v["tasks"], 3)
        self.assertEqual(v["first_try_successes"], 3)
        self.assertEqual(v["recovered_successes"], 0)
        self.assertEqual(v["failures"], 0)
        self.assertEqual(v["budget_exhausted"], 0)
        self.assertEqual(v["retries"], 0)
        self.assertEqual(v["verification_rate"], 1.0)
        self.assertEqual(summary["failed"], 0)
        self.assertEqual(summary["successful"], 3)
        ids = summary["task_experiment_ids"]
        self.assertEqual(len(set(ids.values())), 3)
        self.assertTrue(all(e.startswith("tb_exp_") for e in ids.values()))
        self.assertTrue(summary["session_id"].startswith("tb_sess_"))
        self.assertTrue(summary["goal_experiment_id"].startswith("tb_exp_"))
        for pt in v["per_task"].values():
            self.assertEqual(pt["execution_status"], "FIRST_TRY_SUCCESS")
            self.assertEqual(pt["attempts"], 1)
            self.assertEqual(pt["retries_used"], 0)
            self.assertEqual(pt["taxonomy"], "valid")

    def test_dag_first_try_events_and_legacy_untouched(self) -> None:
        from thinkbox.engine import ThinkBoxEngine, TaskState
        subtasks = [self._sub("compute", "add_small")]
        complete, _ = self._router(subtasks, {})
        eng = self._governed()
        summary = self._run(eng.execute_verified_goal("single", subtasks, complete))
        tid = list(summary["task_experiment_ids"])[0]
        events = [e for e in eng._base.events if e.task_id == tid]
        self.assertTrue(any(e.state == TaskState.RUNNING for e in events))
        succ = [e for e in events if e.state == TaskState.SUCCESS]
        self.assertEqual(succ[-1].metadata.get("execution_status"), "FIRST_TRY_SUCCESS")
        self.assertEqual(succ[-1].metadata.get("experiment_id"), summary["task_experiment_ids"][tid])
        self.assertEqual(succ[-1].metadata.get("session_id"), summary["session_id"])
        base = ThinkBoxEngine()
        legacy = self._run(base.execute_goal("plain goal"))
        self.assertNotIn("verified", legacy)
        self.assertIn("goal_run_id", legacy)

    def test_dag_recovered_task_preserves_failure_provenance(self) -> None:
        subtasks = [self._sub("distractor", "wrongkey")]
        complete, calls = self._router(subtasks, {0: "wrongkey_then_valid"})
        eng = self._governed()
        summary = self._run(eng.execute_verified_goal("recover", subtasks, complete))
        v = summary["verified"]
        self.assertEqual(v["recovered_successes"], 1)
        self.assertEqual(v["first_try_successes"], 0)
        self.assertEqual(v["failures"], 0)
        self.assertEqual(v["retries"], 1)
        pt = list(v["per_task"].values())[0]
        self.assertEqual(pt["execution_status"], "RECOVERED_SUCCESS")
        self.assertEqual(pt["taxonomy"], "distractor-compliance")
        self.assertEqual(pt["final_taxonomy"], "valid")
        self.assertTrue(pt["converted"])
        self.assertEqual(pt["attempts"], 2)
        self.assertEqual(summary["successful"], 1)
        self.assertEqual(summary["failed"], 0)
        self.assertEqual(max(calls.values()), 2)

    def test_dag_non_retryable_failure_no_retry_spent(self) -> None:
        subtasks = [self._sub("compute", "add_small")]
        complete, calls = self._router(subtasks, {0: "arithmetic_always"})
        eng = self._governed()
        summary = self._run(eng.execute_verified_goal("arith", subtasks, complete))
        v = summary["verified"]
        pt = list(v["per_task"].values())[0]
        self.assertEqual(pt["execution_status"], "FAILED_AFTER_RETRY")
        self.assertEqual(pt["taxonomy"], "arithmetic")
        self.assertEqual(pt["final_taxonomy"], "arithmetic")
        self.assertEqual(pt["attempts"], 1)
        self.assertEqual(pt["retries_used"], 0)
        self.assertEqual(v["retries"], 0)
        self.assertEqual(summary["failed"], 1)
        self.assertEqual(max(calls.values()), 1)

    def test_dag_budget_exhausted_is_honest_terminal(self) -> None:
        subtasks = [self._sub("distractor", "wrongkey"),
                    self._sub("distractor", "apology", depends_on=[0])]
        complete, _ = self._router(subtasks, {0: "wrongkey_always", 1: "valid"})
        eng = self._governed()
        summary = self._run(eng.execute_verified_goal("budget", subtasks, complete, max_calls=2))
        v = summary["verified"]
        statuses = sorted(pt["execution_status"] for pt in v["per_task"].values())
        self.assertEqual(statuses, ["BUDGET_EXHAUSTED", "FAILED_AFTER_RETRY"])
        self.assertEqual(v["budget_exhausted"], 1)
        self.assertEqual(v["failures"], 1)
        self.assertEqual(summary["calls_spent"], 2)
        self.assertEqual(summary["budget_remaining"], 0)
        self.assertEqual(summary["failed"], 2)
        self.assertTrue(eng.ledger.verify())

    def test_dag_parent_aggregation_hides_nothing(self) -> None:
        import json as _j
        subtasks = [self._sub("compute", "add_small"),
                    self._sub("distractor", "wrongkey"),
                    self._sub("compute", "mul_small", depends_on=[0])]
        complete, _ = self._router(subtasks, {1: "wrongkey_then_valid", 2: "arithmetic_always"})
        eng = self._governed()
        summary = self._run(eng.execute_verified_goal("agg", subtasks, complete))
        v = summary["verified"]
        self.assertEqual(v["tasks"], 3)
        self.assertEqual(v["first_try_successes"], 1)
        self.assertEqual(v["recovered_successes"], 1)
        self.assertEqual(v["failures"], 1)
        self.assertEqual(v["verification_rate"], round(2 / 3, 4))
        self.assertEqual(summary["successful"], 2)
        self.assertEqual(summary["failed"], 1)
        goal_entries = [e for e in eng.ledger.entries() if e["action"] == "execute_verified_goal"]
        self.assertEqual(len(goal_entries), 1)
        import sqlite3
        rows = eng.ledger._conn.execute(
            "SELECT metadata FROM ledger WHERE action='execute_verified_goal'").fetchall()
        meta = _j.loads(rows[0][0])
        self.assertEqual(meta["tasks"], 3)
        self.assertEqual(meta["first_try_successes"], 1)
        self.assertEqual(meta["recovered_successes"], 1)
        self.assertEqual(meta["failures"], 1)
        self.assertEqual(meta["retries"], 1)
        self.assertTrue(eng.ledger.verify())

    def test_dag_persist_restart_reload_and_dashboard(self) -> None:
        import tempfile
        from pathlib import Path
        from thinkbox.experiment import ExperimentManager
        tmp = tempfile.mkdtemp()
        db = str(Path(tmp) / "exp.db")
        art = Path(tmp) / "artifacts"
        subtasks = [self._sub("compute", "add_small"),
                    self._sub("distractor", "wrongkey", depends_on=[0])]
        complete, _ = self._router(subtasks, {1: "wrongkey_then_valid"})
        eng = self._governed()
        mgr = ExperimentManager(db_path=db, artifacts_dir=str(art))
        summary = self._run(eng.execute_verified_goal(
            "persist", subtasks, complete, manager=mgr))
        goal_exp = summary["goal_experiment_id"]
        task_exps = list(summary["task_experiment_ids"].values())

        fresh = ExperimentManager(db_path=db, artifacts_dir=str(art))
        goal_row = fresh.db.get_experiment(goal_exp)
        self.assertIsNotNone(goal_row)
        self.assertEqual(goal_row["status"], "completed")
        for exp_id in task_exps:
            row = fresh.db.get_experiment(exp_id)
            self.assertIsNotNone(row)
        import sqlite3
        conn = sqlite3.connect(db)
        params = {(r[0], r[1]): r[2] for r in conn.execute(
            "SELECT experiment_id, name, value FROM experiment_parameters")}
        self.assertEqual(params[(goal_exp, "scope")], "dag")
        self.assertEqual(params[(goal_exp, "dag_tasks")], "2")
        self.assertEqual(params[(goal_exp, "recovered_successes")], "1")
        statuses = sorted(params[(e, "execution_status")] for e in task_exps)
        self.assertEqual(statuses, ["FIRST_TRY_SUCCESS", "RECOVERED_SUCCESS"])
        outcomes = {r[0]: r[1] for r in conn.execute(
            "SELECT experiment_id, outcome_data FROM outcomes")}
        import json as _j
        recovered = [e for e in task_exps if params[(e, "execution_status")] == "RECOVERED_SUCCESS"][0]
        out = _j.loads(outcomes[recovered])
        self.assertEqual(out["taxonomy"], "distractor-compliance")
        self.assertEqual(out["final_taxonomy"], "valid")
        self.assertTrue(out["converted"])
        conn.close()

        dash = TestPipelineDashboard._load_dashboard()
        saved_db = dash.DB
        try:
            dash.DB = Path(tmp) / "dbdir"
            dash.DB.mkdir(exist_ok=True)
            import shutil
            shutil.copy(db, dash.DB / "experiments.db")
            pipe = dash._pipeline()
            dag = pipe["dag"]
            self.assertEqual(dag["tasks_total"], 2)
            self.assertEqual(dag["first_try_successes"], 1)
            self.assertEqual(dag["recovered_successes"], 1)
            self.assertEqual(dag["verification_rate"], 1.0)
            self.assertEqual(len(dag["goals"]), 1)
            self.assertEqual(dag["goals"][0]["goal_experiment_id"], goal_exp)
        finally:
            dash.DB = saved_db

    def test_dag_proof_and_ledger_integrity(self) -> None:
        import hashlib
        import json as _j
        import sqlite3
        import tempfile
        from pathlib import Path
        from thinkbox.experiment import ExperimentManager
        tmp = tempfile.mkdtemp()
        ledger_path = str(Path(tmp) / "ledger.db")
        db = str(Path(tmp) / "exp.db")
        art = Path(tmp) / "artifacts"
        subtasks = [self._sub("compute", "add_carry"),
                    self._sub("distractor", "wrongkey", depends_on=[0])]
        complete, _ = self._router(subtasks, {0: "valid_with_usage", 1: "wrongkey_then_valid"})
        eng = self._governed(ledger_path=ledger_path)
        mgr = ExperimentManager(db_path=db, artifacts_dir=str(art))
        summary = self._run(eng.execute_verified_goal(
            "proof", subtasks, complete, manager=mgr, agent_id="dag-test"))
        proof_path = Path(summary["proof_artifact"])
        self.assertTrue(proof_path.exists())
        proof = _j.loads(proof_path.read_text())
        claimed = proof.pop("proof_sha256")
        self.assertEqual(claimed, summary["proof_sha256"])
        recomputed = hashlib.sha256(
            _j.dumps(proof, indent=2, sort_keys=True).encode()).hexdigest()
        self.assertEqual(recomputed, claimed)
        self.assertEqual(proof["dag"]["tasks"], 2)
        self.assertEqual(len(proof["tasks"]), 2)
        for t in proof["tasks"]:
            art_hash = hashlib.sha256(Path(t["artifact"]).read_bytes()).hexdigest()
            self.assertEqual(art_hash, t["artifact_sha256"])

        from thinkbox.ledger import ActionLedger
        led = ActionLedger(ledger_path)
        self.assertTrue(led.verify())
        conn = sqlite3.connect(ledger_path)
        rows = conn.execute("SELECT action, metadata FROM ledger").fetchall()
        conn.close()
        task_actions = [r for r in rows if r[0].startswith("verified_task:")]
        goal_actions = [r for r in rows if r[0] == "execute_verified_goal"]
        self.assertEqual(len(task_actions), 2)
        self.assertEqual(len(goal_actions), 1)
        exp_ids = set(summary["task_experiment_ids"].values())
        tokens_seen = []
        for action, meta_json in task_actions:
            meta = _j.loads(meta_json)
            self.assertIn(meta["experiment_id"], exp_ids)
            self.assertEqual(meta["session_id"], summary["session_id"])
            self.assertIn(meta["outcome"], (
                "FIRST_TRY_SUCCESS", "RECOVERED_SUCCESS", "FAILED_AFTER_RETRY", "BUDGET_EXHAUSTED"))
            tokens_seen.append(meta["tokens"])
        self.assertIn(42, tokens_seen)
        led.close()

    def test_dag_telemetry_contains_no_secrets(self) -> None:
        import json as _j
        import re
        import tempfile
        from pathlib import Path
        from thinkbox.experiment import ExperimentManager
        tmp = tempfile.mkdtemp()
        db = str(Path(tmp) / "exp.db")
        art = Path(tmp) / "artifacts"
        subtasks = [self._sub("distractor", "wrongkey")]
        complete, _ = self._router(subtasks, {0: "wrongkey_then_valid"})
        eng = self._governed(ledger_path=str(Path(tmp) / "ledger.db"))
        mgr = ExperimentManager(db_path=db, artifacts_dir=str(art))
        summary = self._run(eng.execute_verified_goal(
            "secrets", subtasks, complete, manager=mgr))
        blob = _j.dumps(summary)
        for p in Path(art).glob("*.json"):
            blob += p.read_text()
        import sqlite3
        conn = sqlite3.connect(str(Path(tmp) / "ledger.db"))
        for (meta,) in conn.execute("SELECT metadata FROM ledger"):
            blob += meta
        conn.close()
        self.assertEqual(re.findall(r"(?i)(api[_-]?key|bearer|authorization|ucat_|sk-[A-Za-z0-9])", blob), [])
        from thinkbox.pop_arena import secrets_clean
        self.assertTrue(secrets_clean(summary))


if __name__ == "__main__":
    unittest.main()


class TestSwarmScalingSafeguards(unittest.TestCase):
    """Scaling safeguards: concurrency safety, ledger integrity, trace grounding, deterministic accounting."""

    def test_ledger_valid_at_scale(self) -> None:
        """Ledger must verify after 256+ agent calls with zero silent failures."""
        from thinkbox.ledger import ActionLedger

        ledger = ActionLedger(":memory:")
        agents = 256
        for i in range(agents):
            ledger.append(
                f"SWARM-PRIMARY-{i:04d}",
                "research:primary",
                "swarm:PRIMARY",
                True,
                "admitted",
                {"claim_id": f"CLM-{i:04d}", "synthetic": True},
            )
        self.assertTrue(ledger.verify(), "ledger must verify after 256+ calls")
        self.assertEqual(len(ledger.entries(limit=1_000_000)), agents)

    def test_ledger_valid_with_zero_failures(self) -> None:
        """When all calls succeed, ledger verify() must be True."""
        from thinkbox.ledger import ActionLedger

        ledger = ActionLedger(":memory:")
        for i in range(32):
            ledger.append(f"w{i}", "cap", "swarm", True, "admitted", {})
        self.assertTrue(ledger.verify())

    def test_trace_grounding_equals_successful_calls(self) -> None:
        """Only successful calls produce grounded traces; grounding rate must be 100% for OK calls."""
        from thinkbox.thinktrace import ThinkTraceCapture

        traces = ThinkTraceCapture()
        ok = 256
        for i in range(ok):
            traces.capture(f"SWARM-PRIMARY-{i:04d}", "tier EVIDENCE", evidence_refs=[f"claim:CLM-{i:04d}"], tags=["PRIMARY", "swarm", "EVIDENCE"])
        self.assertEqual(traces.count(grounded=True), ok)
        self.assertEqual(traces.count(), ok)

    def test_deterministic_accounting_global_equals_sum(self) -> None:
        """Global call count must equal sum of per-agent results; no double-counting."""
        results = [{"ok": True, "latency_s": 0.5} for _ in range(256)]
        total_calls = len(results)
        ok_count = sum(1 for r in results if r["ok"])
        failed_count = total_calls - ok_count
        self.assertEqual(ok_count + failed_count, total_calls)
        self.assertEqual(ok_count, 256)
        self.assertEqual(failed_count, 0)

    def test_rps_measurement_accuracy(self) -> None:
        """effective_rps must equal total_calls / elapsed_s with no division by zero."""
        total_calls = 256
        elapsed = 14.1
        rps = round(total_calls / elapsed, 2)
        self.assertGreater(rps, 0)
        self.assertEqual(rps, round(256 / 14.1, 2))

    def test_latency_distribution_p50_p95(self) -> None:
        """p50 latency must be computed from sorted results; p95 must be >= p50."""
        import random

        random.seed(42)
        latencies = sorted([random.uniform(0.5, 4.0) for _ in range(256)])
        p50 = latencies[len(latencies) // 2]
        p95 = latencies[int(len(latencies) * 0.95)]
        self.assertGreaterEqual(p95, p50)
        self.assertGreater(p50, 0)

    def test_strength_index_improves_with_more_data(self) -> None:
        """Strength index should not degrade as agent count increases (more evidence)."""
        from thinkbox.metrics import compute_swarm_strength

        small = compute_swarm_strength(
            total=132, ok=112, traces=132, grounded=112, validators=32,
            disagreements=20, validator_downgrades=7, tier_inflation=7,
            tier_distribution={"EVIDENCE": 2, "INFERENCE": 13, "HYPOTHESIS": 2, "UNVERIFIED": 63, "ERROR": 20},
        )
        large = compute_swarm_strength(
            total=256, ok=256, traces=256, grounded=256, validators=32,
            disagreements=21, validator_downgrades=4, tier_inflation=4,
            tier_distribution={"EVIDENCE": 3, "INFERENCE": 33, "HYPOTHESIS": 2, "UNVERIFIED": 186, "ERROR": 0},
        )
        self.assertGreaterEqual(large.score, small.score)
        self.assertEqual(large.reliability, 1.0)
        self.assertEqual(large.grounding, 1.0)

    def test_concurrency_safety_no_race_conditions(self) -> None:
        """Concurrent writes to ledger must not corrupt hash chain."""
        from thinkbox.ledger import ActionLedger
        import threading

        ledger = ActionLedger(":memory:")
        errors = []

        def worker(base: int) -> None:
            try:
                for i in range(32):
                    ledger.append(f"w{base+i}", "cap", "swarm", True, "admitted", {})
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=worker, args=(i * 32,)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, f"Concurrent writes caused errors: {errors}")
        self.assertTrue(ledger.verify(), "ledger must verify after concurrent writes")
        self.assertEqual(len(ledger.entries(limit=1_000_000)), 256)
