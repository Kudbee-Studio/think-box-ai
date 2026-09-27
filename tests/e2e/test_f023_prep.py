"""F023 prep — hermetic experiment persistence, ModelProvider wiring, Think Job API surface."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from core.providers.base import ModelProvider
from thinkbox.experiment import ExperimentManager, ExperimentStatus

from tests.e2e.hermetic_scaffold import HermeticModelProvider, subtask_spec


class TestModelProviderHermeticWiring(unittest.TestCase):
    def test_mock_satisfies_protocol(self) -> None:
        provider: ModelProvider = HermeticModelProvider([subtask_spec("compute", "add_small")])
        self.assertTrue(provider.capabilities.completion)


class TestExperimentPersistenceOnDisk(unittest.TestCase):
    def test_experiment_round_trip_sqlite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "experiments.db"
            art_dir = Path(tmp) / "artifacts"
            mgr = ExperimentManager(db_path=str(db_path), artifacts_dir=str(art_dir))
            record = mgr.create_experiment(
                intent="f023 prep",
                hypothesis="hermetic persistence",
                agent_id="f023-agent",
            )
            mgr.complete_experiment(
                record.experiment_id,
                outcome={"status": "ok"},
                confidence=1.0,
                four_state=ExperimentStatus.COMPLETED.value,
            )
            loaded = mgr.db.get_experiment(record.experiment_id)
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded["session_id"], record.session_id)
            proof_path = Path(tmp) / "proof.json"
            proof_path.write_text(
                json.dumps({"experiment_id": record.experiment_id}),
                encoding="utf-8",
            )
            art_id = mgr.add_artifact(record.experiment_id, "proof", str(proof_path), {"evidence_label": "simulated"})
            self.assertTrue(art_id.startswith("art_"))


class TestThinkJobApiSurface(unittest.TestCase):
    def test_run_endpoint_contract(self) -> None:
        router_path = Path(__file__).resolve().parents[2] / "backend/api/v1/router.py"
        source = router_path.read_text(encoding="utf-8")
        self.assertIn('@api_v1_router.post("/run"', source)
        self.assertIn("class RunRequest(BaseModel):", source)
        self.assertIn("governance_token", source)
        self.assertIn("require_http_admission", source)
        self.assertIn("execute_governed_run_background", source)
        self.assertIn("ThinkJobEntry", source)


if __name__ == "__main__":
    unittest.main()
