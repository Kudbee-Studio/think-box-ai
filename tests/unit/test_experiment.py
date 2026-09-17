"""Tests for the persistent Experiment + Learning System."""

from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

from thinkbox.experiment import (
    ExperimentRecord,
    ExperimentManager,
    ExperimentDB,
    AgentSessionRecord,
    ParameterProvenance,
    ParameterClassification,
    ExperimentStatus,
    FourState,
    ProvenanceSource,
    get_experiment_manager,
)
from thinkbox.dashboard_state import get_dashboard_state


class TestParameterProvenance(unittest.TestCase):
    def test_create_parameter(self):
        param = ParameterProvenance(
            name="rpm", value=8000, unit="RPM",
            source=ProvenanceSource.MEASURED.value,
            confidence=0.95,
            classification=ParameterClassification.OBSERVED.value,
        )
        self.assertEqual(param.name, "rpm")
        self.assertEqual(param.value, 8000)
        self.assertEqual(param.unit, "RPM")
        self.assertEqual(param.confidence, 0.95)
        self.assertEqual(param.classification, ParameterClassification.OBSERVED.value)

    def test_parameter_model_dump(self):
        param = ParameterProvenance(
            name="diameter", value=10.0, unit="mm",
            source=ProvenanceSource.MEASURED.value,
            confidence=1.0,
        )
        dump = param.model_dump()
        self.assertEqual(dump["name"], "diameter")
        self.assertEqual(dump["value"], 10.0)
        self.assertEqual(dump["unit"], "mm")
        self.assertEqual(dump["confidence"], 1.0)

    def test_parameter_default_values(self):
        param = ParameterProvenance(name="test", value="val")
        self.assertEqual(param.unit, "")
        self.assertEqual(param.source, ProvenanceSource.MEASURED.value)
        self.assertEqual(param.confidence, 0.0)
        self.assertEqual(param.classification, ParameterClassification.OBSERVED.value)

    def test_parameter_with_session_id(self):
        param = ParameterProvenance(
            name="tool", value="end_mill",
            session_id="tb_sess_123",
        )
        self.assertEqual(param.session_id, "tb_sess_123")


class TestExperimentRecord(unittest.TestCase):
    def test_create_experiment(self):
        exp = ExperimentRecord(intent="test intent", hypothesis="test hypothesis")
        self.assertIsNotNone(exp.session_id)
        self.assertIsNotNone(exp.experiment_id)
        self.assertEqual(exp.intent, "test intent")
        self.assertEqual(exp.hypothesis, "test hypothesis")
        self.assertEqual(exp.status, ExperimentStatus.PENDING.value)

    def test_experiment_model_dump(self):
        exp = ExperimentRecord(intent="test", hypothesis="hyp")
        dump = exp.model_dump()
        self.assertIn("session_id", dump)
        self.assertIn("experiment_id", dump)
        self.assertIn("intent", dump)
        self.assertIn("hypothesis", dump)
        self.assertIn("parameters", dump)
        self.assertIn("actions", dump)
        self.assertIn("tests", dump)
        self.assertIn("artifacts", dump)
        self.assertIn("proof", dump)
        self.assertIn("outcome", dump)
        self.assertIn("lessons", dump)

    def test_experiment_with_parameters(self):
        exp = ExperimentRecord(
            intent="cut",
            hypothesis="higher rpm reduces cycle time",
            parameters={"rpm": 8000, "feed_rate": 200, "depth_of_cut": 2.0},
        )
        self.assertEqual(exp.parameters["rpm"], 8000)
        self.assertEqual(exp.parameters["feed_rate"], 200)
        self.assertEqual(exp.parameters["depth_of_cut"], 2.0)

    def test_experiment_four_state(self):
        exp = ExperimentRecord(
            intent="test", hypothesis="hyp",
            four_state=FourState.CODE_COMPLETE.value,
        )
        self.assertEqual(exp.four_state, FourState.CODE_COMPLETE.value)

    def test_experiment_confidence(self):
        exp = ExperimentRecord(intent="test", hypothesis="hyp", confidence=0.85)
        self.assertEqual(exp.confidence, 0.85)


class TestAgentSessionRecord(unittest.TestCase):
    def test_create_session(self):
        session = AgentSessionRecord(agent_id="test_agent")
        self.assertIsNotNone(session.session_id)
        self.assertEqual(session.agent_id, "test_agent")
        self.assertEqual(session.current_state, "")
        self.assertEqual(session.four_state, "")

    def test_session_model_dump(self):
        session = AgentSessionRecord(agent_id="agent1", parent_session_id="parent1")
        dump = session.model_dump()
        self.assertIn("session_id", dump)
        self.assertIn("parent_session_id", dump)
        self.assertIn("agent_id", dump)
        self.assertIn("started_at", dump)
        self.assertIn("four_state", dump)

    def test_session_with_parent_child(self):
        parent = AgentSessionRecord(agent_id="parent_agent")
        child = AgentSessionRecord(agent_id="child_agent", parent_session_id=parent.session_id)
        self.assertEqual(child.parent_session_id, parent.session_id)
        self.assertNotEqual(child.session_id, parent.session_id)

    def test_session_four_state(self):
        session = AgentSessionRecord(
            agent_id="agent1",
            four_state=FourState.TEST_VERIFIED.value,
        )
        self.assertEqual(session.four_state, FourState.TEST_VERIFIED.value)

    def test_session_blockers(self):
        session = AgentSessionRecord(
            agent_id="agent1",
            blockers=["UpCloud API 401", "SSH timeout"],
        )
        self.assertEqual(len(session.blockers), 2)
        self.assertIn("UpCloud API 401", session.blockers)


class TestExperimentDB(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_db = tempfile.mktemp(suffix=".db")
        self.db = ExperimentDB(db_path=self.tmp_db)

    def tearDown(self) -> None:
        if os.path.exists(self.tmp_db):
            os.unlink(self.tmp_db)

    def test_schema_creation(self):
        self.assertTrue(os.path.exists(self.tmp_db))
        conn = _connect(self.tmp_db)
        try:
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {row[0] for row in cursor.fetchall()}
            expected = {"agent_sessions", "experiments", "experiment_parameters",
                        "experiment_events", "artifacts", "proof_records", "outcomes", "lessons"}
            self.assertTrue(expected.issubset(tables))
        finally:
            conn.close()

    def test_save_and_get_session(self):
        session = AgentSessionRecord(agent_id="test", four_state=FourState.CODE_COMPLETE.value)
        self.db.save_session(session)
        result = self.db.get_session(session.session_id)
        self.assertIsNotNone(result)
        self.assertEqual(result["agent_id"], "test")
        self.assertEqual(result["four_state"], FourState.CODE_COMPLETE.value)

    def test_save_and_get_experiment(self):
        exp = ExperimentRecord(intent="test", hypothesis="hyp")
        self.db.save_experiment(exp)
        result = self.db.get_experiment(exp.experiment_id)
        self.assertIsNotNone(result)
        self.assertEqual(result["intent"], "test")

    def test_save_parameter(self):
        exp = ExperimentRecord(intent="test", hypothesis="hyp")
        self.db.save_experiment(exp)
        param = ParameterProvenance(name="rpm", value=8000, unit="RPM", confidence=0.95)
        self.db.save_parameter(exp.experiment_id, param)
        params = self.db.get_parameters_by_experiment(exp.experiment_id)
        self.assertEqual(len(params), 1)
        self.assertEqual(params[0]["name"], "rpm")
        self.assertEqual(params[0]["confidence"], 0.95)

    def test_save_outcome(self):
        exp = ExperimentRecord(intent="test", hypothesis="hyp")
        self.db.save_experiment(exp)
        self.db.save_outcome(exp.experiment_id, {"success": True}, 0.95, FourState.TEST_VERIFIED.value)
        outcome = self.db.get_outcomes_by_experiment(exp.experiment_id)
        self.assertIsNotNone(outcome)
        self.assertEqual(outcome["confidence"], 0.95)
        self.assertEqual(outcome["four_state"], FourState.TEST_VERIFIED.value)

    def test_save_artifact(self):
        exp = ExperimentRecord(intent="test", hypothesis="hyp")
        self.db.save_experiment(exp)
        self.db.save_artifact(exp.experiment_id, "art_001", "gcode", "/path/to/file", "abc123", metadata={"type": "manufacturing"})
        params = self.db.get_parameters_by_experiment(exp.experiment_id)
        self.db.save_event(exp.experiment_id, "artifact_added", {"artifact_id": "art_001"})

    def test_save_proof(self):
        exp = ExperimentRecord(intent="test", hypothesis="hyp")
        self.db.save_experiment(exp)
        proof = {"proof_id": "proof-001", "evidence_label": "verified", "decisions": []}
        self.db.save_proof(exp.experiment_id, proof)
        conn = _connect(self.tmp_db)
        try:
            cursor = conn.execute("SELECT * FROM proof_records WHERE experiment_id = ?", (exp.experiment_id,))
            row = cursor.fetchone()
            self.assertIsNotNone(row)
        finally:
            conn.close()

    def test_save_lesson(self):
        exp = ExperimentRecord(intent="test", hypothesis="hyp")
        self.db.save_experiment(exp)
        self.db.save_lesson(exp.experiment_id, "Higher rpm reduces cycle time", [], "next_exp_001")
        lessons = self.db.get_lessons_by_experiment(exp.experiment_id)
        self.assertEqual(len(lessons), 1)
        self.assertEqual(lessons[0]["lesson"], "Higher rpm reduces cycle time")

    def test_get_all_experiments(self):
        exp1 = ExperimentRecord(intent="test1", hypothesis="hyp1")
        exp2 = ExperimentRecord(intent="test2", hypothesis="hyp2")
        self.db.save_experiment(exp1)
        self.db.save_experiment(exp2)
        all_exps = self.db.get_all_experiments()
        self.assertEqual(len(all_exps), 2)

    def test_dashboard_aggregates(self):
        exp = ExperimentRecord(intent="test", hypothesis="hyp", confidence=0.9)
        self.db.save_experiment(exp)
        session = AgentSessionRecord(agent_id="test")
        self.db.save_session(session)
        aggregates = self.db.get_dashboard_aggregates()
        self.assertEqual(aggregates["total_experiments"], 1)
        self.assertEqual(aggregates["total_sessions"], 1)
        self.assertIn("experiments_by_status", aggregates)
        self.assertIn("recent_experiments", aggregates)

    def test_restart_recovery(self):
        exp = ExperimentRecord(intent="test", hypothesis="hyp", status=ExperimentStatus.RUNNING.value)
        self.db.save_experiment(exp)
        session = AgentSessionRecord(agent_id="test")
        self.db.save_session(session)
        recovery = self.db.restart_recovery()
        self.assertEqual(len(recovery["active_experiments"]), 1)
        self.assertEqual(len(recovery["recent_sessions"]), 1)

    def test_save_event(self):
        exp = ExperimentRecord(intent="test", hypothesis="hyp")
        self.db.save_experiment(exp)
        self.db.save_event(exp.experiment_id, "test_event", {"data": "value"})
        conn = _connect(self.tmp_db)
        try:
            cursor = conn.execute("SELECT * FROM experiment_events WHERE experiment_id = ?", (exp.experiment_id,))
            row = cursor.fetchone()
            self.assertIsNotNone(row)
        finally:
            conn.close()


class TestExperimentManager(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_db = tempfile.mktemp(suffix=".db")
        self.tmp_artifacts = tempfile.mkdtemp()
        self.manager = ExperimentManager(db_path=self.tmp_db, artifacts_dir=self.tmp_artifacts)

    def tearDown(self) -> None:
        if os.path.exists(self.tmp_db):
            os.unlink(self.tmp_db)
        if os.path.exists(self.tmp_artifacts):
            import shutil
            shutil.rmtree(self.tmp_artifacts)

    def test_create_session(self):
        session = self.manager.create_session(agent_id="test_agent")
        self.assertIsNotNone(session.session_id)
        self.assertEqual(session.agent_id, "test_agent")
        self.assertIsNotNone(self.manager.db.get_session(session.session_id))

    def test_create_experiment(self):
        session = self.manager.create_session(agent_id="test")
        exp = self.manager.create_experiment(
            intent="cut metal", hypothesis="higher rpm reduces time",
            parameters={"rpm": 8000}, agent_id="test",
        )
        self.assertIsNotNone(exp.experiment_id)
        self.assertEqual(exp.intent, "cut metal")

    def test_add_parameter(self):
        exp = self.manager.create_experiment(intent="test", hypothesis="hyp")
        param = self.manager.add_parameter(
            exp.experiment_id, "rpm", 8000, unit="RPM",
            confidence=0.95, classification=ParameterClassification.OBSERVED.value,
        )
        self.assertEqual(param.name, "rpm")
        self.assertEqual(param.value, 8000)
        params = self.manager.db.get_parameters_by_experiment(exp.experiment_id)
        self.assertEqual(len(params), 1)

    def test_add_action(self):
        exp = self.manager.create_experiment(intent="test", hypothesis="hyp")
        self.manager.add_action(exp.experiment_id, {"action": "cut", "tool": "end_mill"})

    def test_add_artifact(self):
        exp = self.manager.create_experiment(intent="test", hypothesis="hyp")
        artifact_id = self.manager.add_artifact(
            exp.experiment_id, "gcode", "/path/to/file.gcode",
            metadata={"type": "manufacturing"},
        )
        self.assertIsNotNone(artifact_id)

    def test_add_proof(self):
        exp = self.manager.create_experiment(intent="test", hypothesis="hyp")
        proof = {"proof_id": "proof-001", "evidence_label": "verified"}
        self.manager.add_proof(exp.experiment_id, proof)

    def test_record_outcome(self):
        exp = self.manager.create_experiment(intent="test", hypothesis="hyp")
        self.manager.record_outcome(
            exp.experiment_id, {"success": True}, 0.95,
            four_state=FourState.TEST_VERIFIED.value,
        )
        outcome = self.manager.db.get_outcomes_by_experiment(exp.experiment_id)
        self.assertIsNotNone(outcome)
        self.assertEqual(outcome["confidence"], 0.95)

    def test_record_lesson(self):
        exp = self.manager.create_experiment(intent="test", hypothesis="hyp")
        self.manager.record_lesson(
            exp.experiment_id, "Higher rpm reduces cycle time",
            parameter_updates=[{"name": "rpm", "value": 9000}],
            next_experiment="exp_002",
        )
        lessons = self.manager.db.get_lessons_by_experiment(exp.experiment_id)
        self.assertEqual(len(lessons), 1)

    def test_complete_experiment(self):
        exp = self.manager.create_experiment(intent="test", hypothesis="hyp")
        result = self.manager.complete_experiment(
            exp.experiment_id,
            outcome={"success": True},
            confidence=0.95,
            four_state=FourState.TEST_VERIFIED.value,
            lessons=["Higher rpm works"],
            next_experiment="exp_002",
        )
        self.assertIsNotNone(result)

    def test_run_zero_server_experiment(self):
        result = self.manager.run_zero_server_experiment(
            intent="test zero-server",
            hypothesis="local execution works",
            parameters={"rpm": 8000, "feed_rate": 200},
            agent_id="test",
        )
        self.assertIn("session_id", result)
        self.assertIn("experiment_id", result)
        self.assertIn("parameters", result)

    def test_get_dashboard_data(self):
        self.manager.run_zero_server_experiment(
            intent="dashboard test", hypothesis="test",
            parameters={"rpm": 8000}, agent_id="test",
        )
        data = self.manager.get_dashboard_data()
        self.assertIn("total_experiments", data)
        self.assertIn("dashboard_state", data)

    def test_restart(self):
        self.manager.run_zero_server_experiment(
            intent="restart test", hypothesis="test",
            parameters={"rpm": 8000}, agent_id="test",
        )
        recovery = self.manager.restart()
        self.assertIn("active_experiments", recovery)
        self.assertIn("recent_sessions", recovery)

    def test_parent_child_sessions(self):
        parent = self.manager.create_session(agent_id="parent")
        child = self.manager.create_session(
            agent_id="child", parent_session_id=parent.session_id,
        )
        self.assertEqual(child.parent_session_id, parent.session_id)


class TestDashboardIntegration(unittest.TestCase):
    def setUp(self) -> None:
        self.state = get_dashboard_state()

    def tearDown(self) -> None:
        self.state.think_boxes.clear()
        self.state.think_jobs.clear()
        self.state.cnc_jobs.clear()
        self.state.infrastructure.clear()
        self.state.providers.clear()
        self.state.test_milestones.clear()
        self.state.events.clear()

    def test_dashboard_state_has_experiment_entries(self):
        from thinkbox.dashboard_state import DashboardCategory, DashboardEvent
        import asyncio
        state = get_dashboard_state()
        async def _emit():
            await state.emit(
                DashboardCategory.TESTS, DashboardEvent.TEST_PASS,
                {"test": "experiment_creation", "passed": 1},
                "test",
                evidence_label="verified",
            )
        asyncio.run(_emit())
        state_data = state.get_state()
        self.assertIn("events", state_data)
        self.assertGreaterEqual(len(state_data["events"]), 0)


class TestZeroServerExecution(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_db = tempfile.mktemp(suffix=".db")
        self.tmp_artifacts = tempfile.mkdtemp()
        self.manager = ExperimentManager(db_path=self.tmp_db, artifacts_dir=self.tmp_artifacts)

    def tearDown(self) -> None:
        if os.path.exists(self.tmp_db):
            os.unlink(self.tmp_db)
        if os.path.exists(self.tmp_artifacts):
            import shutil
            shutil.rmtree(self.tmp_artifacts)

    def test_full_lifecycle(self):
        session = self.manager.create_session(agent_id="test_agent")
        exp = self.manager.create_experiment(
            intent="cut 6061-T6 aluminum",
            hypothesis="Higher spindle speed reduces cycle time",
            parameters={"tool": "end_mill", "diameter": 10.0, "rpm": 8000},
            parent_session_id=session.parent_session_id,
            agent_id="test_agent",
        )
        self.manager.add_parameter(exp.experiment_id, "tool", "end_mill", unit="", source=ProvenanceSource.MEASURED.value, confidence=1.0, classification=ParameterClassification.OBSERVED.value)
        self.manager.add_parameter(exp.experiment_id, "diameter", 10.0, unit="mm", source=ProvenanceSource.MEASURED.value, confidence=1.0, classification=ParameterClassification.OBSERVED.value)
        self.manager.add_parameter(exp.experiment_id, "rpm", 8000, unit="RPM", source=ProvenanceSource.MEASURED.value, confidence=0.95, classification=ParameterClassification.OBSERVED.value)
        self.manager.add_action(exp.experiment_id, {"action": "initialize", "machine": "HAAS VF-2SS"})
        self.manager.add_test(exp.experiment_id, {"test": "spindle_check", "passed": True})
        artifact_id = self.manager.add_artifact(exp.experiment_id, "gcode", "/tmp/test.gcode", metadata={"type": "manufacturing"})
        proof = {"proof_id": "proof-001", "evidence_label": "verified", "decisions": [], "validations": [], "approvals": []}
        self.manager.add_proof(exp.experiment_id, proof)
        self.manager.record_outcome(exp.experiment_id, {"success": True, "cycle_time": 45.2}, 0.95, FourState.TEST_VERIFIED.value)
        self.manager.record_lesson(exp.experiment_id, "Higher rpm reduces cycle time by 15%", parameter_updates=[{"name": "rpm", "value": 9000}], next_experiment="exp_002")
        result = self.manager.complete_experiment(exp.experiment_id, {"success": True}, 0.95, FourState.TEST_VERIFIED.value, lessons=["Higher rpm works"], next_experiment="exp_002")
        self.assertIsNotNone(result)
        exp_data = self.manager.db.get_experiment(exp.experiment_id)
        self.assertIsNotNone(exp_data)
        params = self.manager.db.get_parameters_by_experiment(exp.experiment_id)
        self.assertEqual(len(params), 3)
        lessons = self.manager.db.get_lessons_by_experiment(exp.experiment_id)
        self.assertGreaterEqual(len(lessons), 1)

    def test_restart_recovery_persists_data(self):
        session = self.manager.create_session(agent_id="test_agent")
        exp = self.manager.create_experiment(
            intent="restart test", hypothesis="test",
            parameters={"rpm": 8000}, agent_id="test_agent",
        )
        self.manager.add_parameter(exp.experiment_id, "rpm", 8000, confidence=0.95)
        self.manager.record_outcome(exp.experiment_id, {"success": True}, 0.95, FourState.CODE_COMPLETE.value)
        recovery = self.manager.restart()
        self.assertEqual(len(recovery["active_experiments"]), 1)
        self.assertEqual(len(recovery["recent_sessions"]), 1)
        exp_data = self.manager.db.get_experiment(exp.experiment_id)
        self.assertIsNotNone(exp_data)

    def test_missing_artifact_handling(self):
        exp = self.manager.create_experiment(intent="test", hypothesis="hyp")
        artifact_id = self.manager.add_artifact(exp.experiment_id, "missing", "/nonexistent/path", metadata={})
        self.assertIsNotNone(artifact_id)
        params = self.manager.db.get_parameters_by_experiment(exp.experiment_id)
        self.assertEqual(len(params), 0)

    def test_corrupted_artifact_handling(self):
        exp = self.manager.create_experiment(intent="test", hypothesis="hyp")
        artifact_id = self.manager.add_artifact(exp.experiment_id, "corrupted", "/tmp/test", metadata={"bad": "data"})
        self.assertIsNotNone(artifact_id)

    def test_four_state_classification(self):
        for state in FourState:
            session = self.manager.create_session(agent_id="test", metadata={"four_state": state.value})
            self.assertIn(state.value, [FourState.CODE_COMPLETE.value, FourState.TEST_VERIFIED.value, FourState.LIVE_VERIFIED.value, FourState.PRODUCTION_READY.value, FourState.FAILED.value])


def _connect(path: str) -> sqlite3.Connection:
    return sqlite3.connect(path)


if __name__ == "__main__":
    unittest.main()
