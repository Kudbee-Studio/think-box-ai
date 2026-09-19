"""Tests for export proof bundle."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from thinkbox.agent.control_plane.store import ActionReceiptStore
from thinkbox.agent.control_plane.export import export_proof_bundle, PROOFS_DIR


class TestExportProofBundle(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.store = ActionReceiptStore(":memory:")

    def tearDown(self) -> None:
        self.store.close()

    def test_export_creates_files(self) -> None:
        self.store.append("admit", "allowed", "ok", "verified")
        bundle = export_proof_bundle(self.store, output_dir=self.tmpdir)
        self.assertTrue(Path(bundle["jsonl"]).exists())
        self.assertTrue(Path(bundle["manifest"]).exists())

    def test_export_jsonl_content(self) -> None:
        self.store.append("admit", "allowed", "ok", "verified")
        bundle = export_proof_bundle(self.store, output_dir=self.tmpdir)
        content = Path(bundle["jsonl"]).read_text()
        records = [json.loads(line) for line in content.splitlines() if line.strip()]
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["action"], "admit")

    def test_export_manifest_sha256(self) -> None:
        self.store.append("admit", "allowed", "ok", "verified")
        bundle = export_proof_bundle(self.store, output_dir=self.tmpdir)
        manifest = json.loads(Path(bundle["manifest"]).read_text())
        self.assertEqual(manifest["sha256"], bundle["sha256"])
        self.assertEqual(manifest["receipt_count"], 1)

    def test_export_chain_valid_true(self) -> None:
        self.store.append("admit", "allowed", "ok", "verified")
        self.store.append("capacity", "allowed", "ok", "simulated")
        bundle = export_proof_bundle(self.store, output_dir=self.tmpdir)
        manifest = json.loads(Path(bundle["manifest"]).read_text())
        self.assertTrue(manifest["chain_valid"])

    def test_export_with_tamper_shows_invalid(self) -> None:
        import sqlite3, tempfile
        path = tempfile.mktemp(suffix=".db")
        store = ActionReceiptStore(path)
        store.append("admit", "allowed", "ok", "verified")
        conn = sqlite3.connect(path)
        conn.execute("UPDATE receipts SET reason='tampered' WHERE action='admit'")
        conn.commit()
        conn.close()
        bundle = export_proof_bundle(store, output_dir=self.tmpdir)
        manifest = json.loads(Path(bundle["manifest"]).read_text())
        self.assertFalse(manifest["chain_valid"])
        store.close()

    def test_export_creates_proofs_dir(self) -> None:
        bundle = export_proof_bundle(self.store, output_dir=self.tmpdir)
        self.assertTrue(Path(bundle["jsonl"]).parent.exists())

    def test_export_multiple_receipts(self) -> None:
        for i in range(5):
            self.store.append(f"action-{i}", "allowed", f"reason-{i}", "simulated")
        bundle = export_proof_bundle(self.store, output_dir=self.tmpdir)
        content = Path(bundle["jsonl"]).read_text()
        records = [json.loads(line) for line in content.splitlines() if line.strip()]
        self.assertEqual(len(records), 5)
        self.assertEqual(bundle["receipt_count"], 5)

    def test_export_prefix_custom(self) -> None:
        self.store.append("admit", "allowed", "ok", "verified")
        bundle = export_proof_bundle(self.store, output_dir=self.tmpdir, prefix="custom")
        self.assertIn("custom_", bundle["jsonl"])
        self.assertIn("custom_", bundle["manifest"])
