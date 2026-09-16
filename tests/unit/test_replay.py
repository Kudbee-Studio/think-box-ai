"""Unit tests for the replay driver (stdlib unittest)."""

from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from core.sessions import SessionManager
from thinkbox.engine import EngineConfig
from thinkbox.flightrecorder import FlightRecorder
from thinkbox.replay import ReplayDriver, ReplayError, ReplayResult


def _make_session(metadata: dict | None = None) -> tuple[SessionManager, str]:
    mgr = SessionManager()
    sid = mgr.create_session("test", metadata or {})
    return mgr, sid


class TestReplayResolve(unittest.TestCase):
    def test_resolve_returns_goal(self) -> None:
        mgr, sid = _make_session({"goal": "test goal", "engine_config": {}})
        fr = FlightRecorder(":memory:")
        driver = ReplayDriver(mgr, fr)
        self.assertEqual(driver.resolve(sid), "test goal")

    def test_resolve_missing_session(self) -> None:
        fr = FlightRecorder(":memory:")
        driver = ReplayDriver(SessionManager(), fr)
        with self.assertRaises(ReplayError):
            driver.resolve("nonexistent")

    def test_resolve_missing_goal(self) -> None:
        mgr, sid = _make_session({"engine_config": {}})
        fr = FlightRecorder(":memory:")
        driver = ReplayDriver(mgr, fr)
        with self.assertRaises(ReplayError):
            driver.resolve(sid)


class TestReplayRestoreConfig(unittest.TestCase):
    def test_restore_config_from_metadata(self) -> None:
        mgr, sid = _make_session({
            "goal": "test",
            "engine_config": {
                "model_config": {"model": "mercury-2", "temperature": 0.2},
                "speculative": False,
                "max_retries": 5,
            },
        })
        fr = FlightRecorder(":memory:")
        driver = ReplayDriver(mgr, fr)
        config = driver.restore_config(sid)
        self.assertEqual(config.model_config.model, "mercury-2")
        self.assertEqual(config.model_config.temperature, 0.2)
        self.assertFalse(config.speculative)
        self.assertEqual(config.max_retries, 5)

    def test_restore_config_missing(self) -> None:
        mgr, sid = _make_session({"goal": "test"})
        fr = FlightRecorder(":memory:")
        driver = ReplayDriver(mgr, fr)
        with self.assertRaises(ReplayError):
            driver.restore_config(sid)

    def test_restore_config_defaults(self) -> None:
        mgr, sid = _make_session({"goal": "test", "engine_config": {}})
        fr = FlightRecorder(":memory:")
        driver = ReplayDriver(mgr, fr)
        config = driver.restore_config(sid)
        self.assertIsInstance(config, EngineConfig)
        self.assertEqual(config.model_config.model, "llama3.1:8b")
        self.assertEqual(config.scaler_config.default_workers, 16)
        self.assertTrue(config.speculative)
        self.assertEqual(config.max_retries, 3)


class TestReplayCompare(unittest.TestCase):
    def setUp(self) -> None:
        fr = FlightRecorder(":memory:")
        mgr, _ = _make_session({})
        self.driver = ReplayDriver(mgr, fr)

    def test_match_when_equal(self) -> None:
        orig = {"total_tasks": 5, "successful": 5, "completed": 5}
        replay = {"total_tasks": 5, "successful": 5, "completed": 5}
        result = self.driver.compare(orig, replay)
        self.assertEqual(result["verdict"], "MATCH")
        self.assertEqual(result["mismatch_fields"], [])

    def test_mismatch_when_different(self) -> None:
        orig = {"total_tasks": 5, "successful": 4, "completed": 5}
        replay = {"total_tasks": 5, "successful": 3, "completed": 5}
        result = self.driver.compare(orig, replay)
        self.assertEqual(result["verdict"], "MISMATCH")
        self.assertIn("successful", result["mismatch_fields"])

    def test_nondeterministic_fields_excluded(self) -> None:
        orig = {"total_tasks": 5, "successful": 5, "total_time_ms": 1000, "events": 10}
        replay = {"total_tasks": 5, "successful": 5, "total_time_ms": 2000, "events": 25}
        result = self.driver.compare(orig, replay)
        self.assertEqual(result["verdict"], "MATCH")
        self.assertEqual(result["mismatch_fields"], [])

    def test_mixed_match_and_mismatch(self) -> None:
        orig = {"total_tasks": 5, "successful": 5, "total_time_ms": 1000, "events": 10}
        replay = {"total_tasks": 5, "successful": 3, "total_time_ms": 2000, "events": 25}
        result = self.driver.compare(orig, replay)
        self.assertEqual(result["verdict"], "MISMATCH")
        self.assertEqual(result["mismatch_fields"], ["successful"])

    def test_compare_returns_tuple_pairs(self) -> None:
        orig = {"total_tasks": 5}
        replay = {"total_tasks": 3}
        result = self.driver.compare(orig, replay)
        self.assertEqual(result["compared"]["total_tasks"], (5, 3))


class TestReplayVerify(unittest.TestCase):
    def test_verify_delegates_to_flight_recorder(self) -> None:
        fr = FlightRecorder(":memory:")
        fr.save_genome("sess_v", {"model": "m"})
        mgr, _ = _make_session({"goal": "g", "engine_config": {}})
        driver = ReplayDriver(mgr, fr)
        self.assertTrue(driver.verify("sess_v"))

    def test_verify_false_when_no_genome(self) -> None:
        fr = FlightRecorder(":memory:")
        mgr, _ = _make_session({"goal": "g", "engine_config": {}})
        driver = ReplayDriver(mgr, fr)
        self.assertFalse(driver.verify("nonexistent"))


class TestReplayExecute(unittest.TestCase):
    def test_execute_runs_goal(self) -> None:
        mgr, sid = _make_session({
            "goal": "test goal",
            "engine_config": {
                "model_config": {"model": "mercury-2"},
                "speculative": False,
            },
        })
        fr = FlightRecorder(":memory:")
        driver = ReplayDriver(mgr, fr)
        with patch("thinkbox.engine.ThinkBoxEngine") as mock_engine_cls:
            mock_engine = MagicMock()
            mock_engine_cls.return_value = mock_engine
            mock_engine.execute_goal = AsyncMock(
                return_value={"total_tasks": 1, "successful": 1}
            )
            result = driver.execute(sid)
        self.assertEqual(result["total_tasks"], 1)
        mock_engine.execute_goal.assert_awaited_once_with("test goal")

    def test_execute_missing_session(self) -> None:
        fr = FlightRecorder(":memory:")
        mgr, _ = _make_session()
        driver = ReplayDriver(mgr, fr)
        with self.assertRaises(ReplayError):
            driver.execute("nonexistent")


class TestReplayRun(unittest.TestCase):
    def test_run_full_replay_with_match(self) -> None:
        fr = FlightRecorder(":memory:")
        mgr, sid = _make_session({
            "goal": "test goal",
            "engine_config": {
                "model_config": {"model": "mercury-2"},
                "speculative": False,
            },
        })
        fr.save_genome(sid, {"model": "m"})
        driver = ReplayDriver(mgr, fr)
        with patch("thinkbox.engine.ThinkBoxEngine") as mock_engine_cls:
            mock_engine = MagicMock()
            mock_engine_cls.return_value = mock_engine
            mock_engine.execute_goal = AsyncMock(
                return_value={"total_tasks": 2, "successful": 2}
            )
            result = driver.run(sid, original_summary={"total_tasks": 2, "successful": 2})
        self.assertEqual(result.session_id, sid)
        self.assertEqual(result.verdict, "MATCH")
        self.assertTrue(result.genome_verified)
        self.assertEqual(result.goal, "test goal")

    def test_run_full_replay_with_mismatch(self) -> None:
        fr = FlightRecorder(":memory:")
        mgr, sid = _make_session({
            "goal": "test goal",
            "engine_config": {"speculative": False},
        })
        fr.save_genome(sid, {"model": "m"})
        driver = ReplayDriver(mgr, fr)
        with patch("thinkbox.engine.ThinkBoxEngine") as mock_engine_cls:
            mock_engine = MagicMock()
            mock_engine_cls.return_value = mock_engine
            mock_engine.execute_goal = AsyncMock(
                return_value={"total_tasks": 2, "successful": 1}
            )
            result = driver.run(sid, original_summary={"total_tasks": 2, "successful": 2})
        self.assertEqual(result.verdict, "MISMATCH")
        self.assertIn("successful", result.mismatch_fields)

    def test_run_without_original_summary(self) -> None:
        fr = FlightRecorder(":memory:")
        mgr, sid = _make_session({
            "goal": "test goal",
            "engine_config": {"speculative": False},
        })
        fr.save_genome(sid, {"model": "m"})
        driver = ReplayDriver(mgr, fr)
        with patch("thinkbox.engine.ThinkBoxEngine") as mock_engine_cls:
            mock_engine = MagicMock()
            mock_engine_cls.return_value = mock_engine
            mock_engine.execute_goal = AsyncMock(return_value={"total_tasks": 1})
            result = driver.run(sid)
        self.assertEqual(result.verdict, "MATCH")
        self.assertEqual(result.original_summary, {})

    def test_run_to_dict(self) -> None:
        result = ReplayResult(
            session_id="s",
            goal="g",
            verdict="MATCH",
            genome_verified=True,
            original_summary={"a": 1},
            replay_summary={"a": 1},
            mismatch_fields=[],
        )
        d = result.to_dict()
        self.assertEqual(d["session_id"], "s")
        self.assertEqual(d["verdict"], "MATCH")
        self.assertEqual(d["genome_verified"], True)


if __name__ == "__main__":
    unittest.main()
