"""Tests for Loop Session Management (PR #240).

Proves:
1. LoopSessionManager.start_session creates a new session with loop_id
2. close_session fails-closed when <3 iterations
3. close_session creates a LoopSession with aggregate metrics when >=3 iterations
4. list_sessions, get_session, get_session_count work correctly
5. compare_sessions computes throughput/latency/error deltas and improved flag
6. No session manager -> no-op in engine
7. Engine can close and start new sessions for cross-cycle comparison
"""

from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import unittest

from thinkbox.engine import ThinkBoxEngine, EngineConfig
from thinkbox.experiment import ExperimentManager
from thinkbox.experiment_analytics import (
    ExperimentAnalytics,
    OpportunityManager,
    LoopTracer,
    EngineAutoTuner,
    CrossExperimentGeneralizer,
    LoopSessionManager,
    LoopSession,
    SessionComparison,
)


def _make_all(tmpdir: str):
    db_path = os.path.join(tmpdir, "experiments.db")
    artifacts_dir = os.path.join(tmpdir, "artifacts")
    opp_db = os.path.join(tmpdir, "opportunities.db")
    loop_db = os.path.join(tmpdir, "loop.db")
    tuner_db = os.path.join(tmpdir, "tuner.db")
    gen_db = os.path.join(tmpdir, "generalizer.db")
    sess_db = os.path.join(tmpdir, "sessions.db")
    manager = ExperimentManager(db_path=db_path, artifacts_dir=artifacts_dir)
    analytics = ExperimentAnalytics(manager)
    opp_mgr = OpportunityManager(manager, analytics, db_path=opp_db)
    tracer = LoopTracer(db_path=loop_db)
    tuner = EngineAutoTuner(tracer, db_path=tuner_db)
    generalizer = CrossExperimentGeneralizer(tracer, manager, analytics, db_path=gen_db)
    sess_mgr = LoopSessionManager(tracer, generalizer, db_path=sess_db)
    return manager, analytics, opp_mgr, tracer, tuner, generalizer, sess_mgr


def _insert_iteration(tracer: LoopTracer, recommendation_type: str,
                      throughput: float, p50_latency: float, error_rate: float,
                      goal_run_id: str = "goal") -> None:
    conn = sqlite3.connect(tracer._db_path)
    try:
        conn.row_factory = sqlite3.Row
        count = conn.execute("SELECT COUNT(*) FROM loop_iterations").fetchone()[0]
    finally:
        conn.close()

    iteration_id = f"iter_{count}"
    loop_id = tracer.get_current_loop_id() or f"loop_{iteration_id}"
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    metrics = {
        "throughput": throughput,
        "p50_latency": p50_latency,
        "p95_latency": p50_latency * 2,
        "p99_latency": p50_latency * 3,
        "error_rate": error_rate,
        "iteration_count": 1,
    }

    conn = sqlite3.connect(tracer._db_path)
    try:
        if not tracer.get_current_loop_id():
            conn.execute("INSERT OR REPLACE INTO loop_metadata (key, value) VALUES (?, ?)",
                         ("current_loop_id", loop_id))
        conn.execute(
            "INSERT INTO loop_iterations "
            "(iteration_id, loop_id, started_at, completed_at, cycle_time_s, "
            "goal_run_id, experiment_id, opportunity_id, recommendation_type, priority, metrics) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (iteration_id, loop_id, now, now, 1.0,
             goal_run_id, f"exp_{count}", f"opp_{count}",
             recommendation_type, "medium", json.dumps(metrics)),
        )
        conn.execute("INSERT OR REPLACE INTO loop_metadata (key, value) VALUES (?, ?)",
                     ("latest_iteration_id", iteration_id))
        if count == 0:
            conn.execute("INSERT OR REPLACE INTO loop_metadata (key, value) VALUES (?, ?)",
                         ("first_iteration_id", iteration_id))
        conn.commit()
    finally:
        conn.close()


class TestLoopSessionManager(unittest.TestCase):

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.manager, self.analytics, self.opp_mgr, self.tracer, \
            self.tuner, self.generalizer, self.sess_mgr = _make_all(self.tmpdir)

    def test_start_session(self) -> None:
        session_id = self.sess_mgr.start_session()
        self.assertTrue(session_id.startswith("sess_"))
        loop_id = self.tracer.get_current_loop_id()
        self.assertTrue(loop_id.startswith("loop_"))

    def test_close_session_fewer_than_3_iterations(self) -> None:
        self.sess_mgr.start_session()
        _insert_iteration(self.tracer, "validation_run", 5.0, 0.1, 0.01, "g1")
        _insert_iteration(self.tracer, "validation_run", 6.0, 0.1, 0.01, "g2")

        result = self.sess_mgr.close_session()
        self.assertIsNone(result)
        self.assertEqual(self.sess_mgr.get_session_count(), 0)

    def test_close_session_with_3_iterations(self) -> None:
        self.sess_mgr.start_session()
        for i in range(3):
            _insert_iteration(self.tracer, "validation_run", 5.0 + i, 0.1, 0.01, f"g_{i}")

        session = self.sess_mgr.close_session()
        self.assertIsNotNone(session)
        self.assertIsInstance(session, LoopSession)
        self.assertEqual(session.iterations_count, 3)
        self.assertAlmostEqual(session.avg_throughput, 6.0, places=1)
        self.assertEqual(session.patterns_identified, 0)

    def test_list_sessions(self) -> None:
        for i in range(2):
            self.sess_mgr.start_session()
            for j in range(3):
                _insert_iteration(self.tracer, "validation_run", 5.0 + j, 0.1, 0.01, f"g_{i}_{j}")
            self.sess_mgr.close_session()

        sessions = self.sess_mgr.list_sessions()
        self.assertEqual(len(sessions), 2)

    def test_get_session(self) -> None:
        self.sess_mgr.start_session()
        for i in range(3):
            _insert_iteration(self.tracer, "validation_run", 5.0, 0.1, 0.01, f"g_{i}")
        session = self.sess_mgr.close_session()

        retrieved = self.sess_mgr.get_session(session.session_id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.session_id, session.session_id)
        self.assertEqual(retrieved.iterations_count, 3)

    def test_get_session_not_found(self) -> None:
        result = self.sess_mgr.get_session("nonexistent")
        self.assertIsNone(result)

    def test_get_session_count(self) -> None:
        self.assertEqual(self.sess_mgr.get_session_count(), 0)
        self.sess_mgr.start_session()
        for i in range(3):
            _insert_iteration(self.tracer, "validation_run", 5.0, 0.1, 0.01, f"g_{i}")
        self.sess_mgr.close_session()
        self.assertEqual(self.sess_mgr.get_session_count(), 1)

    def test_compare_sessions_improved(self) -> None:
        self.sess_mgr.start_session()
        for i in range(3):
            _insert_iteration(self.tracer, "validation_run", 3.0, 0.1, 0.01, f"b_{i}")
        baseline = self.sess_mgr.close_session()

        self.sess_mgr.start_session()
        for i in range(3):
            _insert_iteration(self.tracer, "validation_run", 8.0, 0.1, 0.01, f"c_{i}")
        candidate = self.sess_mgr.close_session()

        comparison = self.sess_mgr.compare_sessions(baseline.session_id, candidate.session_id)
        self.assertIsInstance(comparison, SessionComparison)
        self.assertGreater(comparison.throughput_delta, 0)
        self.assertTrue(comparison.improved)

    def test_compare_sessions_degraded(self) -> None:
        self.sess_mgr.start_session()
        for i in range(3):
            _insert_iteration(self.tracer, "validation_run", 10.0, 0.1, 0.01, f"b_{i}")
        baseline = self.sess_mgr.close_session()

        self.sess_mgr.start_session()
        for i in range(3):
            _insert_iteration(self.tracer, "validation_run", 5.0, 0.1, 0.01, f"c_{i}")
        candidate = self.sess_mgr.close_session()

        comparison = self.sess_mgr.compare_sessions(baseline.session_id, candidate.session_id)
        self.assertLess(comparison.throughput_delta, 0)
        self.assertFalse(comparison.improved)

    def test_compare_sessions_missing_raises(self) -> None:
        with self.assertRaises(ValueError):
            self.sess_mgr.compare_sessions("nonexistent1", "nonexistent2")


class TestEngineSessionBinding(unittest.IsolatedAsyncioTestCase):

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.manager, self.analytics, self.opp_mgr, self.tracer, \
            self.tuner, self.generalizer, self.sess_mgr = _make_all(self.tmpdir)

    async def test_engine_close_and_start_session(self) -> None:
        engine = ThinkBoxEngine(EngineConfig(speculative=False))
        engine.wire_experiment_feedback(self.manager, self.analytics, self.opp_mgr)
        engine.set_loop_tracer(self.tracer)
        engine.set_auto_tuner(self.tuner)
        engine.set_generalizer(self.generalizer)
        engine.set_session_manager(self.sess_mgr)

        session_id = self.sess_mgr.start_session()
        self.assertTrue(session_id.startswith("sess_"))

        for i in range(3):
            await engine.execute_goal(f"Goal {i}")

        session = self.sess_mgr.close_session()
        self.assertIsNotNone(session)
        self.assertEqual(session.iterations_count, 3)

        new_session_id = self.sess_mgr.start_session()
        self.assertNotEqual(new_session_id, session_id)

    async def test_no_session_manager_no_op(self) -> None:
        engine = ThinkBoxEngine(EngineConfig(speculative=False))
        engine.wire_experiment_feedback(self.manager, self.analytics, self.opp_mgr)
        engine.set_loop_tracer(self.tracer)
        engine.set_auto_tuner(self.tuner)
        engine.set_generalizer(self.generalizer)
        engine.set_session_manager(None)

        await engine.execute_goal("Goal without session manager")
        self.assertEqual(self.sess_mgr.get_session_count(), 0)


if __name__ == "__main__":
    unittest.main()
