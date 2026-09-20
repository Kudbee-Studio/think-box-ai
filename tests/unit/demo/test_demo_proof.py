"""Tests: demo proof bundle emission."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from thinkbox.agent.control_plane.store import ActionReceiptStore
from thinkbox.agent.control_plane.demo_record import DemoRunRecord, create_run_table, save_run
from thinkbox.agent.control_plane.demo_proof import emit_proof_bundle
from thinkbox.agent.control_plane.kernel_hooks import HookContext, on_admit


class TestDemoProofBundle(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.store = ActionReceiptStore(":memory:")
        self.proof_dir = Path(self.tmpdir) / "proofs"

    def tearDown(self) -> None:
        self.store.close()

    def test_emit_creates_bundle(self) -> None:
        for i in range(2):
            on_admit(self.store, HookContext(agent_id="demo", action=f"call-{i}"))
        bundle = emit_proof_bundle(self.store, "demo-001", output_dir=self.proof_dir)
        self.assertTrue(Path(bundle["jsonl"]).exists())
        self.assertTrue(Path(bundle["manifest"]).exists())

    def test_bundle_chain_valid(self) -> None:
        for i in range(2):
            on_admit(self.store, HookContext(agent_id="demo", action=f"call-{i}"))
        bundle = emit_proof_bundle(self.store, "demo-001", output_dir=self.proof_dir)
        self.assertTrue(bundle["chain_valid"])
        self.assertEqual(bundle["receipt_count"], 2)

    def test_bundle_sha256_present(self) -> None:
        for i in range(1):
            on_admit(self.store, HookContext(agent_id="demo", action="call-0"))
        bundle = emit_proof_bundle(self.store, "demo-002", output_dir=self.proof_dir)
        self.assertIn("sha256", bundle)
        self.assertEqual(len(bundle["sha256"]), 64)

    def test_evidence_label_simulated(self) -> None:
        on_admit(self.store, HookContext(agent_id="demo", action="call-0", evidence_label="simulated"))
        bundle = emit_proof_bundle(self.store, "demo-003", output_dir=self.proof_dir)
        content = Path(bundle["jsonl"]).read_text()
        record = json.loads(content.splitlines()[0])
        self.assertEqual(record["evidence_label"], "simulated")

    def test_gitignored_directory(self) -> None:
        bundle = emit_proof_bundle(self.store, "demo-004", output_dir=self.proof_dir)
        self.assertTrue(Path(bundle["jsonl"]).exists())
