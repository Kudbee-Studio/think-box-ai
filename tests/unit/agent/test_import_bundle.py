"""Tests for import + offline verify bundle."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from thinkbox.agent.control_plane.store import ActionReceiptStore
from thinkbox.agent.control_plane.export import export_proof_bundle
from thinkbox.agent.control_plane.import_bundle import (
    import_bundle,
    verify_bundle_offline,
)


class TestImportBundle(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.store = ActionReceiptStore(":memory:")

    def tearDown(self) -> None:
        self.store.close()

    def test_import_from_jsonl(self) -> None:
        for i in range(3):
            self.store.append(f"act-{i}", "allowed", f"reason-{i}", "simulated")
        bundle = export_proof_bundle(self.store, output_dir=self.tmpdir, prefix="imp")
        self.store.close()
        reopened = ActionReceiptStore(os.path.join(self.tmpdir, "imported.db"))
        try:
            result = import_bundle(reopened, bundle["jsonl"])
            self.assertEqual(result["imported"], 3)
            self.assertTrue(reopened.verify())
        finally:
            reopened.close()

    def test_import_missing_file_raises(self) -> None:
        with self.assertRaises(FileNotFoundError):
            import_bundle(self.store, "/nonexistent/bundle.jsonl")

    def test_import_missing_field_raises(self) -> None:
        import sqlite3
        path = os.path.join(self.tmpdir, "bad.jsonl")
        with open(path, "w") as f:
            f.write(json.dumps({"action": "missing-fields"}) + "\n")
        with self.assertRaises(ValueError):
            import_bundle(self.store, path)

    def test_import_preserves_metadata(self) -> None:
        self.store.append("admit", "allowed", "ok", "verified", metadata={"key": "val"})
        bundle = export_proof_bundle(self.store, output_dir=self.tmpdir, prefix="meta")
        self.store.close()
        reopened = ActionReceiptStore(os.path.join(self.tmpdir, "imported.db"))
        try:
            import_bundle(reopened, bundle["jsonl"])
            rows = reopened._conn.execute("SELECT metadata FROM receipts").fetchall()
            self.assertEqual(json.loads(rows[0][0])["key"], "val")
        finally:
            reopened.close()

    def test_verify_bundle_offline_valid(self) -> None:
        for i in range(3):
            self.store.append(f"act-{i}", "allowed", f"reason-{i}", "simulated")
        bundle = export_proof_bundle(self.store, output_dir=self.tmpdir, prefix="off")
        result = verify_bundle_offline(bundle["jsonl"])
        self.assertTrue(result["chain_valid"])
        self.assertEqual(result["receipt_count"], 3)
        self.assertTrue(result["offline"])

    def test_verify_bundle_offline_detects_tamper(self) -> None:
        self.store.append("admit", "allowed", "ok", "verified")
        bundle = export_proof_bundle(self.store, output_dir=self.tmpdir, prefix="tamper")
        content = Path(bundle["jsonl"]).read_text()
        records = [json.loads(line) for line in content.splitlines() if line.strip()]
        records[0]["reason"] = "tampered"
        Path(bundle["jsonl"]).write_text(
            "\n".join(json.dumps(r) for r in records) + "\n"
        )
        result = verify_bundle_offline(bundle["jsonl"])
        self.assertFalse(result["chain_valid"])

    def test_verify_bundle_offline_sha256(self) -> None:
        self.store.append("admit", "allowed", "ok", "verified")
        bundle = export_proof_bundle(self.store, output_dir=self.tmpdir, prefix="sha")
        manifest = json.loads(Path(bundle["manifest"]).read_text())
        result = verify_bundle_offline(bundle["jsonl"])
        self.assertEqual(result["sha256"], manifest["sha256"])
