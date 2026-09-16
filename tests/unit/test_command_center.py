"""Tests for THINK BOX COMMAND CENTER v2 (dashboard + new instruments)."""

from __future__ import annotations

import json
import socket
import sys
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from thinkbox.flightrecorder import FlightRecorder, WorkerRecord
from thinkbox.metrics import MetricsStore, compute_swarm_strength
from thinkbox.mission_control import MissionControl, READY, DEGRADED, UNAVAILABLE, MISSING, UNKNOWN

import experiments.swarm_dashboard as dash


VALID_STATUSES = {READY, DEGRADED, UNAVAILABLE, MISSING, UNKNOWN}


class TestMissionControl(unittest.TestCase):
    def test_snapshot_shape(self) -> None:
        snap = MissionControl().run()
        for key in ("generated_at", "overall", "readiness", "counts", "capabilities",
                    "blockers", "degraded", "human_intervention_required", "note"):
            self.assertIn(key, snap)

    def test_every_capability_has_valid_status_and_detail(self) -> None:
        snap = MissionControl().run()
        self.assertTrue(snap["capabilities"], "no capabilities probed")
        for c in snap["capabilities"]:
            with self.subTest(cap=c["key"]):
                self.assertIn(c["status"], VALID_STATUSES, f"{c['key']} bad status")
                self.assertTrue(c["detail"], f"{c['key']} has no detail")
                self.assertIn("layer", c)
                self.assertIn("human_action", c)

    def test_readiness_in_range_and_counts_consistent(self) -> None:
        snap = MissionControl().run()
        self.assertGreaterEqual(snap["readiness"], 0.0)
        self.assertLessEqual(snap["readiness"], 1.0)
        total = sum(snap["counts"].values())
        self.assertEqual(total, len(snap["capabilities"]))

    def test_blockers_are_unavailable_or_missing(self) -> None:
        snap = MissionControl().run()
        for b in snap["blockers"]:
            self.assertIn(b["status"], (UNAVAILABLE, MISSING))

    def test_vector_is_reported_degraded_when_configured(self) -> None:
        """Presence of the env var must not be reported as healthy."""
        import os
        if not os.environ.get("UPSTASH_VECTOR_REST_URL"):
            self.skipTest("vector not configured in this environment")
        snap = MissionControl().run()
        vec = next((c for c in snap["capabilities"] if c["key"] == "vector"), None)
        self.assertIsNotNone(vec)
        self.assertEqual(vec["status"], DEGRADED)
        self.assertIn("dense", vec["detail"].lower())

    def test_probes_are_pure(self) -> None:
        """Two runs must not mutate state or drift in capability count."""
        a = MissionControl().run()
        b = MissionControl().run()
        self.assertEqual(len(a["capabilities"]), len(b["capabilities"]))

    def test_core_and_external_readiness_are_separate(self) -> None:
        """A blocked external dep must not be reported as core unavailability."""
        snap = MissionControl().run()
        self.assertIn("core_readiness", snap)
        self.assertIn("external_readiness", snap)
        self.assertIn("core_blockers", snap)
        self.assertIn("external_blockers", snap)
        # external deps in this environment are blocked; core is not
        self.assertGreater(snap["core_readiness"], snap["external_readiness"])

    def test_overall_reflects_core_not_external(self) -> None:
        snap = MissionControl().run()
        core_blocked = [c for c in snap["capabilities"]
                        if c.get("critical") and c["status"] in (UNAVAILABLE, MISSING)]
        if core_blocked:
            self.assertEqual(snap["overall"], UNAVAILABLE)
        else:
            core_degraded = [c for c in snap["capabilities"]
                             if c.get("critical") and c["status"] == DEGRADED]
            self.assertEqual(snap["overall"], DEGRADED if core_degraded else READY)

    def test_external_capabilities_are_flagged_non_critical(self) -> None:
        snap = MissionControl().run()
        by_key = {c["key"]: c for c in snap["capabilities"]}
        for key in ("vector", "box", "upcloud", "redis", "mcp"):
            with self.subTest(cap=key):
                self.assertIn(key, by_key)
                self.assertFalse(by_key[key]["critical"],
                                 f"{key} must not be on the core runtime path")

    def test_ledger_probe_is_read_only(self) -> None:
        """Mission control must not open the ledger read-write."""
        import inspect
        src = inspect.getsource(__import__("thinkbox.mission_control", fromlist=["check_ledger"]).check_ledger)
        self.assertIn("mode=ro", src)
        self.assertNotIn("ActionLedger(str(path))", src)
        self.assertIn("ActionLedger._compute_hash", src)


class TestArenaPersistence(unittest.TestCase):
    def setUp(self) -> None:
        self.fr = FlightRecorder(":memory:")

    def test_record_and_report(self) -> None:
        self.fr.record_arena_outcome("s1", "P1", "hallucination_trap", "w1",
                                     "EVIDENCE", "UNVERIFIED", False, True, True)
        self.fr.record_arena_outcome("s1", "P2", "hallucination_trap", "w2",
                                     "UNVERIFIED", "UNVERIFIED", True, False, False)
        rep = self.fr.arena_report("s1")
        self.assertEqual(rep["probes"], 2)
        self.assertEqual(rep["by_trap_type"]["hallucination_trap"]["detected"], 1)
        self.assertAlmostEqual(rep["overall"]["detection_rate"], 0.5)
        self.assertAlmostEqual(rep["overall"]["recovery_rate"], 0.5)

    def test_report_scoped_by_session(self) -> None:
        self.fr.record_arena_outcome("s1", "P1", "contradiction", "w1", "HYPOTHESIS", "", True, False, False)
        self.fr.record_arena_outcome("s2", "P2", "contradiction", "w2", "UNVERIFIED", "", True, False, False)
        self.assertEqual(self.fr.arena_report("s1")["probes"], 1)
        self.assertEqual(self.fr.arena_report()["probes"], 2)

    def test_empty_report_is_well_formed(self) -> None:
        rep = self.fr.arena_report("nope")
        self.assertEqual(rep["probes"], 0)
        self.assertEqual(rep["overall"]["detection_rate"], 0.0)


class TestProofExplorer(unittest.TestCase):
    def setUp(self) -> None:
        self.fr = FlightRecorder(":memory:")

    def _chain(self, claim_id: str = "C1") -> str:
        c = self.fr.build_proof_chain(
            session_id="s1", claim_id=claim_id, claim="synthetic claim",
            evidence_nodes=[{"ref": f"claim:{claim_id}"}],
            worker_nodes=[{"worker": "w1", "tier": "UNVERIFIED"}],
            challenge_nodes=[], validator_nodes=[], decision="UNVERIFIED",
        )
        return c["chain_id"]

    def test_list_and_verify_all(self) -> None:
        self._chain("C1")
        self._chain("C2")
        chains = self.fr.list_chains("s1")
        self.assertEqual(len(chains), 2)
        for c in chains:
            self.assertTrue(c["verified"])
        self.assertEqual(self.fr.verify_all_chains(), {"total": 2, "valid": 2, "invalid": 0})

    def test_tampering_detected_in_listing(self) -> None:
        cid = self._chain("C1")
        self.fr._conn.execute("UPDATE proof_nodes SET node_hash='deadbeef' WHERE chain_id=?", (cid,))
        self.fr._conn.commit()
        chains = self.fr.list_chains("s1")
        self.assertFalse(chains[0]["verified"])
        self.assertEqual(self.fr.verify_all_chains()["invalid"], 1)


class TestGenomeReplay(unittest.TestCase):
    def setUp(self) -> None:
        self.fr = FlightRecorder(":memory:")

    def test_list_genomes_verifies(self) -> None:
        self.fr.save_genome("s1", {"model": "m", "primary_workers": 8})
        genomes = self.fr.list_genomes()
        self.assertEqual(len(genomes), 1)
        self.assertTrue(genomes[0]["verified"])

    def test_record_and_list_replay(self) -> None:
        self.fr.record_replay("s1", "s2", "hash", 0.60, 0.75, True, "note")
        replays = self.fr.list_replays()
        self.assertEqual(len(replays), 1)
        self.assertAlmostEqual(replays[0]["index_delta"], 0.15)
        self.assertEqual(replays[0]["config_match"], 1)

    def test_replay_delta_none_when_index_missing(self) -> None:
        self.fr.record_replay("s1", "s2", "hash", None, 0.7, False)
        self.assertIsNone(self.fr.list_replays()[0]["index_delta"])


class TestMetricsSessionLookup(unittest.TestCase):
    def test_session_returns_row(self) -> None:
        ms = MetricsStore(":memory:")
        ms.start_session("sess", "big_swarm", "mercury-2", 8)
        idx = compute_swarm_strength(total=1, ok=1, traces=1, grounded=1, validators=1,
                                     disagreements=0, validator_downgrades=0, tier_inflation=0,
                                     tier_distribution={"UNVERIFIED": 1})
        ms.finish_session("sess", 1, 1, 0, 1.0, 1.0, 2, True, "h", idx)
        row = ms.session("sess")
        self.assertIsNotNone(row)
        self.assertEqual(row["model"], "mercury-2")
        self.assertAlmostEqual(row["strength_score"], round(idx.score, 4))

    def test_session_missing_returns_none(self) -> None:
        self.assertIsNone(MetricsStore(":memory:").session("nope"))


class TestDashboardReaders(unittest.TestCase):
    """Readers must degrade gracefully on empty stores, never raise."""

    def test_readers_return_expected_shapes(self) -> None:
        cases = {
            "api_live": ("events", "phase"),
            "api_learning": ("points", "components", "tokens", "improvements"),
            "api_arena": ("probes", "by_trap_type", "overall", "outcomes"),
            "api_memory": ("by_state", "by_event", "recent"),
            "api_reputation": ("leaderboard", "summary"),
            "api_efficiency": ("series", "totals", "price_note"),
            "api_genome": ("genomes", "total", "verified"),
            "api_replay": ("replays", "total", "config_matched"),
            "api_proofs": ("chains", "total", "verified", "invalid", "ledger"),
            "api_mission": ("overall", "readiness", "capabilities", "blockers"),
            "api_instruments": ("flight_records", "ledger"),
        }
        for fn_name, keys in cases.items():
            with self.subTest(reader=fn_name):
                payload = getattr(dash, fn_name)()
                self.assertIsInstance(payload, dict)
                for k in keys:
                    self.assertIn(k, payload, f"{fn_name} missing {k}")

    def test_trace_never_raises(self) -> None:
        payload = dash.api_trace("", "")
        self.assertIsInstance(payload, dict)
        self.assertIn("trace", payload)

    def test_sessions_is_list(self) -> None:
        self.assertIsInstance(dash.api_sessions(), list)

    def test_proof_route_returns_dict(self) -> None:
        self.assertIsInstance(dash.api_proof(), dict)


class TestDashboardHTTP(unittest.TestCase):
    """Every documented route must answer 200 and parse as JSON (or HTML at /)."""

    ROUTES = [
        "/healthz", "/api/live", "/api/strength", "/api/instruments", "/api/sessions",
        "/api/learning", "/api/arena", "/api/memory", "/api/reputation",
        "/api/efficiency", "/api/genome", "/api/replay", "/api/mission",
        "/api/trace", "/api/proofs",
    ]

    @classmethod
    def setUpClass(cls) -> None:
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            cls.port = s.getsockname()[1]
        cls.srv = ThreadingHTTPServer(("127.0.0.1", cls.port), dash.Handler)
        cls.t = threading.Thread(target=cls.srv.serve_forever, daemon=True)
        cls.t.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.srv.shutdown()
        cls.srv.server_close()

    def _get(self, route: str):
        return urllib.request.urlopen(f"http://127.0.0.1:{self.port}{route}", timeout=10)

    def test_healthz(self) -> None:
        with self._get("/healthz") as r:
            body = json.loads(r.read())
            self.assertTrue(body["ok"])
            self.assertEqual(body["version"], "command-center/2.0")

    def test_html_has_security_headers(self) -> None:
        with self._get("/") as r:
            self.assertEqual(r.status, 200)
            self.assertIn("text/html", r.headers.get("Content-Type", ""))
            for h in ("Content-Security-Policy", "X-Frame-Options",
                      "X-Content-Type-Options", "Referrer-Policy"):
                self.assertIn(h, r.headers, f"missing security header {h}")

    def test_all_json_routes(self) -> None:
        for route in self.ROUTES:
            with self.subTest(route=route):
                with self._get(route) as r:
                    self.assertEqual(r.status, 200)
                    json.loads(r.read())

    def test_unknown_route_404(self) -> None:
        import urllib.error
        with self.assertRaises(urllib.error.HTTPError) as cm:
            self._get("/api/does-not-exist")
        self.assertEqual(cm.exception.code, 404)

    def test_tabs_present_in_page(self) -> None:
        with self._get("/") as r:
            html = r.read().decode()
        for tab in ("Command", "Trace", "Proof", "Learning", "Arena",
                    "Memory", "Workers", "Cost×Intel", "Replay", "Mission"):
            self.assertIn(tab, html, f"tab missing: {tab}")


class TestDashboardRegressionV1(unittest.TestCase):
    """v1 payload shapes must survive the v2 evolution (additive only)."""

    def test_strength_alias_matches_learning(self) -> None:
        s = dash.api_strength()
        l = dash.api_learning()
        self.assertEqual(set(s.keys()), set(l.keys()))

    def test_instruments_still_has_v1_keys(self) -> None:
        d = dash.api_instruments()
        for k in ("flight_records", "memory_by_state", "memory_by_event",
                  "reputation_leaderboard", "reputation_summary", "proof_chain",
                  "genome", "arena", "run_id", "session_id", "proof_hash", "ledger"):
            self.assertIn(k, d)


class TestWorkerRecordRoundtrip(unittest.TestCase):
    def test_full_field_retention(self) -> None:
        fr = FlightRecorder(":memory:")
        fr.record(WorkerRecord(
            session_id="s", worker_id="w", role="PRIMARY", model="mercury-2",
            prompt_version="v2", trace_id="t", box_id="b", claim_id="C",
            capability="research:primary", total_tokens=10, latency_s=0.2,
            decision="UNVERIFIED", evidence_refs=["claim:C"], outcome="ok",
        ))
        row = fr.session_records("s")[0]
        self.assertEqual(row["capability"], "research:primary")
        self.assertEqual(row["evidence_refs"], ["claim:C"])
        self.assertEqual(row["prompt_version"], "v2")


if __name__ == "__main__":
    unittest.main()
