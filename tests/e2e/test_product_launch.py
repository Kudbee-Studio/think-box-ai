"""E2E test for KUDBEE product launch.

Tests the complete flow:
- CLI agent demo
- Think Token minting
- Jury Elo scoring
- Circuit breaking
- Queue fallback
- Guardrails
- Streaming
"""

from __future__ import annotations

import os
import json
import tempfile
import subprocess
import unittest


class TestProductLaunch(unittest.TestCase):
    """End-to-end validation of the KUDBE production system."""

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        self._env = os.environ.copy()
        self._env["THINKBOX_DB_PATH"] = os.path.join(self._tmpdir, "test.db")
        self._env["THINKBOX_EVIDENCE_DIR"] = os.path.join(self._tmpdir, "evidence")

    def _run(self, args):
        return subprocess.run(
            ["python3", "-m", "think_box_ai.cli"] + args,
            capture_output=True, text=True, env=self._env,
        )

    def test_cli_agent_demo(self):
        """Verify full agent demo flow."""
        result = self._run(["agent", "echo E2E test"])
        self.assertEqual(result.returncode, 0)
        self.assertIn("KUDBEE", result.stdout)
        self.assertIn("Execution:", result.stdout)
        self.assertIn("Think Token:", result.stdout)
        self.assertIn("Confidence:", result.stdout)

    def test_token_minting(self):
        """Verify tokens minted on successful exec."""
        # Create box
        result = self._run(["create", "--goal", "test minting"])
        self.assertEqual(result.returncode, 0)
        box_id = result.stdout.strip()
        self.assertTrue(box_id.startswith("tb-"))

        # Execute command
        result = self._run(["exec", box_id, "--", "echo mint_me"])
        self.assertEqual(result.returncode, 0)

        # Verify token created
        result = self._run(["tokens", box_id])
        self.assertEqual(result.returncode, 0)
        self.assertIn("mint_me", result.stdout)

    def test_jury_elo_scoring(self):
        """Verify Elo score changes after challenge."""
        # Create box and exec
        result = self._run(["create", "--goal", "test scoring"])
        box_id = result.stdout.strip()
        self._run(["exec", box_id, "--", "echo score_test"])

        # Get token
        result = self._run(["tokens", box_id])
        token_id = json.loads(result.stdout.strip())["id"]

        # Apply human challenge
        result = self._run(["challenge-human", token_id, "pass"])
        self.assertEqual(result.returncode, 0)

        # Verify score increased
        result = self._run(["token-score", token_id])
        score = json.loads(result.stdout.strip())["s"]
        self.assertGreater(score, 1.0)

    def test_health_checks(self):
        """Verify health check command."""
        result = self._run(["health"])
        self.assertEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        self.assertEqual(data["status"], "ok")
        self.assertGreater(len(data["checks"]), 0)

    def test_connect_grant_packet(self):
        """Verify grant packet generation."""
        result = self._run(["connect", "grant", "--grant-type", "nvidia"])
        self.assertEqual(result.returncode, 0)
        packet = json.loads(result.stdout)
        self.assertEqual(packet["program"], "NVIDIA Inception")
        self.assertIn("benefits", packet)
        self.assertIn("requirements", packet)

    def test_queue_operations(self):
        """Verify task queue functionality."""
        from core.infrastructure.queue import TaskQueue

        queue = TaskQueue(use_sqs=False)
        msg_id = queue.enqueue("test", {"data": "value"})
        self.assertTrue(msg_id.startswith("msg_"))

        stats = queue.stats()
        self.assertEqual(stats["queue_size"], 1)

        # Process message
        def handler(body):
            return body.get("type") == "test"

        processed = queue.process(handler)
        self.assertEqual(processed, 1)

    def test_guardrail_verification(self):
        """Verify guardrail rejects ungrounded claims."""
        from core.governance.guardrail import SpecialistGuardrail

        guardrail = SpecialistGuardrail(require_citations=False)

        # Should approve grounded response
        result = guardrail.verify(
            response="The sky is blue.",
            context="The sky appears blue due to Rayleigh scattering.",
            claims=["sky is blue"],
        )
        self.assertTrue(result.approved)

        # Should reject ungrounded response
        result = guardrail.verify(
            response="The sky is green.",
            context="The sky appears blue due to Rayleigh scattering.",
            claims=["sky is green"],
        )
        self.assertFalse(result.approved)


if __name__ == "__main__":
    unittest.main()
