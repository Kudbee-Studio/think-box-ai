"""F023 prep — hermetic experiment persistence, ModelProvider wiring, Think Job API surface."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from core.providers.base import CompletionResponse, Message, ModelProvider, ProviderCapabilities
from thinkbox.experiment import ExperimentManager, ExperimentStatus


class _HermeticMockProvider:
    """Minimal ModelProvider for F023 wiring tests (no network)."""

    capabilities = ProviderCapabilities(completion=True, streaming=False)

    async def complete(self, messages: list[Message], **kwargs: Any) -> CompletionResponse:
        return CompletionResponse(content='{"answer": 1}', model="mock", usage={})

    async def stream(self, messages: list[Message], **kwargs: Any):
        yield CompletionResponse(content="{}", model="mock")

    async def embed(self, texts: list[str], **kwargs: Any) -> list[list[float]]:
        return [[0.0] * 4 for _ in texts]


class TestModelProviderHermeticWiring(unittest.TestCase):
    def test_mock_satisfies_protocol(self) -> None:
        provider: ModelProvider = _HermeticMockProvider()
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
        self.assertIn("async def run_goal(request: RunRequest)", source)
        self.assertIn("ThinkJobEntry", source)


if __name__ == "__main__":
    unittest.main()
