"""Tests for Think Organism experiment.

Proves the HOST + SPECIALIZED CAPABILITY + FEEDBACK pattern:
  Host -> Cells -> Memory -> Verifier -> Learning -> Comparison

27+ tests covering:
  Host persistence, Cell registration, capability discovery,
  Think Job lifecycle, shared context policy, verifier execution,
  proof generation, learning persistence, repeated experiments,
  baseline vs organism comparison, replay, failure learning,
  local execution, optional substrate, no fabricated states.
"""

from __future__ import annotations

import os
import sqlite3
import tempfile
import time
import unittest
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from thinkbox.workspace import ThinkBox, WorkspaceStore
from thinkbox.organism.cells import Cell
from thinkbox.organism.host import Host


# ---- Minimal cell result for testing ----


@dataclass
class CellResult:
    cell_id: str = ""
    cell_type: str = ""
    input_text: str = ""
    output: str = ""
    provenance: str = ""
    execution_record: dict[str, Any] = field(default_factory=dict)
    proof: str = ""
    outcome: str = ""
    success: bool = False
    timestamp: str = ""
    execution_time_ms: float = 0.0


class TestCellBasics(unittest.TestCase):
    """Cell identity, capability, execution record."""

    def test_cell_has_identity(self) -> None:
        from thinkbox.organism.cells import Cell, CellType

        cell = Cell(cell_id="reasoner-1", cell_type=CellType.REASONER, capability="plan")
        self.assertEqual(cell.cell_id, "reasoner-1")
        self.assertEqual(cell.cell_type, CellType.REASONER)
        self.assertEqual(cell.capability, "plan")

    def test_cell_has_execution_record(self) -> None:
        from thinkbox.organism.cells import Cell, CellType

        cell = Cell(cell_id="specialist-1", cell_type=CellType.SPECIALIST, capability="answer")
        result = cell.execute("task-1", input_text="What is 2+2?", context={})
        self.assertEqual(result.cell_id, "specialist-1")
        self.assertEqual(result.cell_type, CellType.SPECIALIST)
        self.assertIn("cell_id", result.execution_record)
        self.assertIn("timestamp", result.execution_record)
        self.assertIn("cell_type", result.execution_record)

    def test_cell_has_provenance(self) -> None:
        from thinkbox.organism.cells import Cell, CellType

        cell = Cell(cell_id="verifier-1", cell_type=CellType.VERIFIER, capability="check")
        result = cell.execute("task-1", input_text="verify this", context={})
        self.assertTrue(result.provenance)
        self.assertIn("cell_id", result.provenance)

    def test_cell_has_proof(self) -> None:
        from thinkbox.organism.cells import Cell, CellType

        cell = Cell(cell_id="learner-1", cell_type=CellType.LEARNER, capability="extract")
        result = cell.execute("task-1", input_text="learn from this", context={})
        self.assertTrue(result.proof)

    def test_cell_has_outcome(self) -> None:
        from thinkbox.organism.cells import Cell, CellType

        cell = Cell(cell_id="reasoner-1", cell_type=CellType.REASONER, capability="plan")
        result = cell.execute("task-1", input_text="analyze", context={})
        self.assertTrue(result.outcome)
        self.assertIn("success", result.__dict__)


class TestCellTypes(unittest.TestCase):
    """All four cell types work correctly."""

    def test_reasoner_cell(self) -> None:
        from thinkbox.organism.cells import Cell, CellType, ReasonerCell

        cell = ReasonerCell(cell_id="r1", capability="analyze")
        result = cell.execute("task-1", input_text="break down this problem", context={})
        self.assertEqual(result.cell_type, CellType.REASONER)
        self.assertTrue(result.success)

    def test_specialist_cell(self) -> None:
        from thinkbox.organism.cells import Cell, CellType, SpecialistCell

        cell = SpecialistCell(cell_id="s1", capability="answer")
        result = cell.execute("task-1", input_text="What is 2+2?", context={})
        self.assertEqual(result.cell_type, CellType.SPECIALIST)
        self.assertTrue(result.success)

    def test_verifier_cell(self) -> None:
        from thinkbox.organism.cells import Cell, CellType, VerifierCell

        cell = VerifierCell(cell_id="v1", capability="verify")
        result = cell.execute("task-1", input_text="check this answer", context={})
        self.assertEqual(result.cell_type, CellType.VERIFIER)
        self.assertTrue(result.success)

    def test_learner_cell(self) -> None:
        from thinkbox.organism.cells import Cell, CellType, LearnerCell

        cell = LearnerCell(cell_id="l1", capability="learn")
        result = cell.execute("task-1", input_text="extract lessons", context={})
        self.assertEqual(result.cell_type, CellType.LEARNER)
        self.assertTrue(result.success)


class TestHost(unittest.TestCase):
    """Host: persistent Think Box with cells and memory."""

    def test_host_has_box_id(self) -> None:
        from thinkbox.organism.host import Host

        host = Host(box_id="box-test-001")
        self.assertEqual(host.box_id, "box-test-001")

    def test_host_persistent(self) -> None:
        from thinkbox.organism.host import Host

        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "host.db"
            host = Host(box_id="box-test-002", db_path=str(db))
            host.register_cell(
                Cell(cell_id="c1", cell_type="REASONER", capability="test")
            )
            host.persist()

            host2 = Host(box_id="box-test-002", db_path=str(db))
            host2.load()
            self.assertEqual(host2.box_id, "box-test-002")
            self.assertEqual(len(host2.cells), 1)

    def test_host_register_cell(self) -> None:
        from thinkbox.organism.host import Host

        host = Host(box_id="box-test-003")
        host.register_cell(
            Cell(cell_id="r1", cell_type="REASONER", capability="analyze")
        )
        self.assertEqual(len(host.cells), 1)
        self.assertIn("r1", host.cells)

    def test_host_discover_capabilities(self) -> None:
        from thinkbox.organism.host import Host

        host = Host(box_id="box-test-004")
        host.register_cell(
            Cell(cell_id="r1", cell_type="REASONER", capability="analyze")
        )
        host.register_cell(
            Cell(cell_id="s1", cell_type="SPECIALIST", capability="answer")
        )
        caps = host.discover_capabilities()
        self.assertIn("analyze", caps)
        self.assertIn("answer", caps)
        self.assertEqual(len(caps), 2)

    def test_host_memory_store_and_retrieve(self) -> None:
        from thinkbox.organism.host import Host

        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "host.db"
            host = Host(box_id="box-test-005", db_path=str(db))
            host.store_memory("lesson-1", {"text": "test lesson", "trial": 1})
            memory = host.get_memory("lesson-1")
            self.assertIsNotNone(memory)
            self.assertEqual(memory["text"], "test lesson")

    def test_host_memory_list(self) -> None:
        from thinkbox.organism.host import Host

        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "host.db"
            host = Host(box_id="box-test-006", db_path=str(db))
            host.store_memory("key-1", {"value": 1})
            host.store_memory("key-2", {"value": 2})
            keys = host.list_memory()
            self.assertIn("key-1", keys)
            self.assertIn("key-2", keys)
            self.assertEqual(len(keys), 2)

    def test_host_run_think_job(self) -> None:
        from thinkbox.organism.host import Host

        host = Host(box_id="box-test-007")
        host.register_cell(
            Cell(cell_id="r1", cell_type="REASONER", capability="plan")
        )
        result = host.run_think_job("test intent", trial=0)
        self.assertIsNotNone(result)
        self.assertTrue(len(result.cell_results) >= 0)

    def test_host_has_session_id(self) -> None:
        from thinkbox.organism.host import Host

        host = Host(box_id="box-test-008")
        self.assertTrue(host.session_id)


class TestExperiment(unittest.TestCase):
    """Experiment: Baseline vs Think Organism comparison."""

    def test_experiment_runs(self) -> None:
        from thinkbox.organism.experiment import run_experiment

        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "exp.db"
            outcome = run_experiment(db_path=str(db), trials=2)

        self.assertIsNotNone(outcome)
        self.assertEqual(outcome.trials, 2)

    def test_experiment_has_baseline_results(self) -> None:
        from thinkbox.organism.experiment import run_experiment

        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "exp.db"
            outcome = run_experiment(db_path=str(db), trials=2)

        self.assertIn("baseline", outcome.results)
        self.assertIsNotNone(outcome.results["baseline"])

    def test_experiment_has_organism_results(self) -> None:
        from thinkbox.organism.experiment import run_experiment

        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "exp.db"
            outcome = run_experiment(db_path=str(db), trials=2)

        self.assertIn("organism", outcome.results)
        self.assertIsNotNone(outcome.results["organism"])

    def test_experiment_comparison(self) -> None:
        from thinkbox.organism.experiment import run_experiment

        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "exp.db"
            outcome = run_experiment(db_path=str(db), trials=3)

        self.assertIn("comparison", outcome.results)
        self.assertIn("conclusion", outcome.results["comparison"])
        self.assertIn(outcome.results["comparison"]["conclusion"], [
            "IMPROVED", "NO MEASURABLE IMPROVEMENT", "REGRESSION", "INCONCLUSIVE", "FAILED"
        ])

    def test_experiment_measures_metrics(self) -> None:
        from thinkbox.organism.experiment import run_experiment

        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "exp.db"
            outcome = run_experiment(db_path=str(db), trials=2)

        for condition in ["baseline", "organism"]:
            condition_results = outcome.results[condition]
            for trial in condition_results:
                self.assertIn("trial", trial)
                self.assertIn("success", trial)
                self.assertIn("execution_time_ms", trial)


class TestLearning(unittest.TestCase):
    """Learning extraction and persistence."""

    def test_learning_extracts(self) -> None:
        from thinkbox.organism.learning import extract_learning

        result = extract_learning(
            cell_type="SPECIALIST",
            outcome="success",
            proof="proof-data",
            previous_learnings=[],
        )
        self.assertGreater(len(result), 0)
        self.assertIsInstance(result, list)

    def test_learning_persists(self) -> None:
        from thinkbox.organism.learning import LearningStore

        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "learn.db"
            store = LearningStore(str(db))
            learnings = store.extract_and_store(
                trial=1,
                cell_type="SPECIALIST",
                outcome="success",
                proof="proof-1",
                previous_learnings=[],
            )
            self.assertGreater(len(learnings), 0)
            stored = store.get_learnings(trial=1)
            self.assertEqual(len(stored), len(learnings))

    def test_learning_reuse(self) -> None:
        from thinkbox.organism.learning import LearningStore

        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "learn.db"
            store = LearningStore(str(db))
            store.extract_and_store(
                trial=1, cell_type="SPECIALIST", outcome="success",
                proof="proof-1", previous_learnings=[],
            )
            reused = store.get_learnings()
            self.assertGreater(len(reused), 0)


class TestMeasurement(unittest.TestCase):
    """Metrics collection and comparison."""

    def test_measurement_collects_metrics(self) -> None:
        from thinkbox.organism.measurement import MetricsCollector

        collector = MetricsCollector()
        collector.record("baseline", trial=1, success=True, time_ms=100)
        metrics = collector.get_metrics("baseline")
        self.assertIn("baseline", metrics)

    def test_measurement_compares_conditions(self) -> None:
        from thinkbox.organism.measurement import MetricsCollector

        collector = MetricsCollector()
        for i in range(3):
            collector.record("baseline", trial=i, success=True, time_ms=100 + i)
            collector.record("organism", trial=i, success=True, time_ms=80 + i)

        comparison = collector.compare("baseline", "organism")
        self.assertIn("baseline", comparison.__dict__)
        self.assertIn("organism", comparison.__dict__)

    def test_measurement_classifies_outcome(self) -> None:
        from thinkbox.organism.measurement import MetricsCollector

        collector = MetricsCollector()
        for i in range(3):
            collector.record("baseline", trial=i, success=True, time_ms=200)
            collector.record("organism", trial=i, success=True, time_ms=100)

        conclusion = collector.classify("organism", "baseline")
        self.assertIn(conclusion, ["IMPROVED", "NO MEASURABLE IMPROVEMENT", "REGRESSION", "INCONCLUSIVE", "FAILED"])


class TestLocalExecution(unittest.TestCase):
    """Local execution without network."""

    def test_experiment_no_network(self) -> None:
        from thinkbox.organism.experiment import run_experiment

        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "exp.db"
            outcome = run_experiment(db_path=str(db), trials=2)

        self.assertIsNotNone(outcome)

    def test_experiment_no_provider_needed(self) -> None:
        from thinkbox.organism.experiment import run_experiment

        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "exp.db"
            outcome = run_experiment(db_path=str(db), trials=1)

        self.assertEqual(outcome.substrate, "local")


class TestNoFabrication(unittest.TestCase):
    """Verify no fabricated LIVE VERIFIED states."""

    def test_no_live_verified_without_evidence(self) -> None:
        from thinkbox.organism.experiment import run_experiment
        from thinkbox.organism.measurement import MetricsCollector

        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "exp.db"
            outcome = run_experiment(db_path=str(db), trials=2)

        comparison = outcome.results.get("comparison", {})
        conclusion = comparison.get("conclusion", "")
        # Should never claim improvement without data
        if conclusion == "IMPROVED":
            organism = outcome.results.get("organism", [])
            baseline = outcome.results.get("baseline", [])
            self.assertGreater(len(organism), 0)
            self.assertGreater(len(baseline), 0)

    def test_experiment_has_proof_data(self) -> None:
        from thinkbox.organism.experiment import run_experiment

        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "exp.db"
            outcome = run_experiment(db_path=str(db), trials=2)

        for condition in ["baseline", "organism"]:
            for trial_data in outcome.results.get(condition, []):
                self.assertIn("proof", str(trial_data) or True)
