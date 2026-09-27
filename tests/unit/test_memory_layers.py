"""Hermetic tests for the four memory layers (PR #203)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.memory.schema import MemoryLayer
from core.memory.store import MemoryStore
from thinkbox.memory_layers import (
    MemoryLayerError,
    catalog_markdown,
    CHRONICLE_FACTS,
    chronicle_facts,
    chronicle_patterns,
    ingest_markdown,
    record_task_error,
    record_task_step,
    snapshot_layers,
    write_organizational,
    write_session,
    write_task,
    write_verified,
)


class TestMemoryLayers(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.store = MemoryStore(self.root / "layers.db")

    def tearDown(self) -> None:
        self.store.close()
        self.tmp.cleanup()

    def test_catalog_skips_git_and_lists_titles(self) -> None:
        (self.root / "AGENTS.md").write_text("# Agents\n", encoding="utf-8")
        (self.root / ".git").mkdir()
        (self.root / ".git" / "notes.md").write_text("# hidden\n", encoding="utf-8")
        (self.root / "docs").mkdir()
        (self.root / "docs" / "STATUS.md").write_text("# Status\n", encoding="utf-8")
        rows = catalog_markdown(self.root)
        paths = [row["path"] for row in rows]
        self.assertEqual(paths, ["AGENTS.md", "docs/STATUS.md"])
        self.assertEqual(rows[0]["title"], "Agents")

    def test_session_write_is_not_live(self) -> None:
        entry = write_session(
            self.store,
            {
                "session_id": "tb_sess_test",
                "goal": "ingest docs",
                "live_verified": True,
            },
        )
        stored = self.store.get(entry.key)
        self.assertEqual(stored.layer, MemoryLayer.SESSION)
        self.assertFalse(stored.value["live_verified"])
        self.assertTrue(stored.key.startswith("session:"))

    def test_task_write_records_steps(self) -> None:
        entry = write_task(
            self.store,
            {
                "task_id": "pr203-memory-layers",
                "status": "running",
                "steps": {"ingest": True},
            },
        )
        stored = self.store.get(entry.key)
        self.assertEqual(stored.layer, MemoryLayer.TASK)
        self.assertEqual(stored.value["steps"]["ingest"], True)
        self.assertFalse(stored.value["live_verified"])

    def test_org_requires_evidence(self) -> None:
        with self.assertRaises(MemoryLayerError) as err:
            write_organizational(
                self.store,
                {"pattern_id": "guess", "description": "maybe"},
            )
        self.assertEqual(err.exception.code, "missing_evidence")
        self.assertEqual(self.store.count(MemoryLayer.ORGANIZATIONAL), 0)

    def test_org_accepts_evidenced_pattern(self) -> None:
        entry = write_organizational(
            self.store,
            {
                "pattern_id": "four-layers",
                "description": "Memory has four layers.",
                "evidence": ["docs/architecture-v1.md"],
            },
        )
        stored = self.store.get(entry.key)
        self.assertEqual(stored.layer, MemoryLayer.ORGANIZATIONAL)
        self.assertEqual(stored.value["evidence"], ["docs/architecture-v1.md"])

    def test_verified_rejects_live_claim(self) -> None:
        with self.assertRaises(MemoryLayerError) as err:
            write_verified(
                self.store,
                {
                    "id": "live-lie",
                    "fact": "this is live",
                    "how": "none",
                    "live_verified": True,
                },
            )
        self.assertEqual(err.exception.code, "live_claim")

    def test_verified_requires_how(self) -> None:
        with self.assertRaises(MemoryLayerError) as err:
            write_verified(self.store, {"id": "bare", "fact": "x"})
        self.assertEqual(err.exception.code, "missing_how")

    def test_ingest_writes_all_four_layers(self) -> None:
        (self.root / "AGENTS.md").write_text("# Agents\nMemory First\n", encoding="utf-8")
        (self.root / "docs").mkdir()
        (self.root / "docs" / "CONTINUITY.md").write_text("# Continuity\n", encoding="utf-8")
        summary = ingest_markdown(
            self.root,
            self.store,
            session_id="tb_sess_test",
            task_id="pr203-memory-layers",
            agent_id="unit",
        )
        self.assertEqual(summary["markdown_files"], 2)
        self.assertFalse(summary["live_verified"])
        self.assertGreaterEqual(self.store.count(MemoryLayer.SESSION), 1)
        self.assertGreaterEqual(self.store.count(MemoryLayer.TASK), 1)
        self.assertGreaterEqual(self.store.count(MemoryLayer.ORGANIZATIONAL), 1)
        self.assertGreaterEqual(self.store.count(MemoryLayer.VERIFIED_KNOWLEDGE), 1)
        self.assertIn("AGENTS.md", [row["path"] for row in summary["catalog"]])
        self.assertIn("snapshot", summary)
        self.assertFalse(summary["snapshot"]["live_verified"])
        self.assertGreaterEqual(summary["snapshot"]["organizational"], 1)

    def test_session_rejects_transient_ui(self) -> None:
        with self.assertRaises(MemoryLayerError) as err:
            write_session(
                self.store,
                {"session_id": "tb_sess_ui", "scroll": 12, "viewport": "wide"},
            )
        self.assertEqual(err.exception.code, "transient_ui")
        self.assertEqual(self.store.count(MemoryLayer.SESSION), 0)

    def test_org_rejects_live_claim(self) -> None:
        with self.assertRaises(MemoryLayerError) as err:
            write_organizational(
                self.store,
                {
                    "pattern_id": "live-lie",
                    "description": "not live",
                    "evidence": ["AGENTS.md"],
                    "live_verified": True,
                },
            )
        self.assertEqual(err.exception.code, "live_claim")

    def test_verified_requires_fact(self) -> None:
        with self.assertRaises(MemoryLayerError) as err:
            write_verified(self.store, {"id": "empty", "how": "unit", "fact": "  "})
        self.assertEqual(err.exception.code, "missing_fact")

    def test_verified_rejects_invalid_confidence(self) -> None:
        with self.assertRaises(MemoryLayerError) as err:
            write_verified(
                self.store,
                {"id": "hot", "fact": "x", "how": "unit", "confidence": 1.5},
            )
        self.assertEqual(err.exception.code, "invalid_confidence")
        with self.assertRaises(MemoryLayerError) as err2:
            write_verified(
                self.store,
                {"id": "nan", "fact": "x", "how": "unit", "confidence": "nope"},
            )
        self.assertEqual(err2.exception.code, "invalid_confidence")

    def test_verified_rejects_contradiction_unless_corrects(self) -> None:
        write_verified(
            self.store,
            {"id": "catalog-count", "fact": "2 files", "how": "walk", "confidence": 1.0},
        )
        with self.assertRaises(MemoryLayerError) as err:
            write_verified(
                self.store,
                {"id": "catalog-count", "fact": "9 files", "how": "walk", "confidence": 1.0},
            )
        self.assertEqual(err.exception.code, "contradiction")
        entry = write_verified(
            self.store,
            {
                "id": "catalog-count",
                "fact": "3 files",
                "how": "walk after add",
                "confidence": 1.0,
                "corrects": "catalog-count",
            },
        )
        stored = self.store.get(entry.key)
        self.assertEqual(stored.value["fact"], "3 files")

    def test_chronicle_patterns_require_all_evidence(self) -> None:
        (self.root / "AGENTS.md").write_text("# Agents\n", encoding="utf-8")
        ids = [row["pattern_id"] for row in chronicle_patterns(self.root)]
        self.assertIn("governance-default", ids)
        self.assertIn("pr-before-work", ids)
        self.assertNotIn("memory-four-layers", ids)
        self.assertNotIn("trait-lab-engine-is-truth", ids)

    def test_snapshot_and_task_step_error(self) -> None:
        write_task(self.store, {"task_id": "pr203-memory-layers", "status": "running"})
        record_task_step(self.store, "pr203-memory-layers", "ingest", {"ok": True})
        record_task_error(self.store, "pr203-memory-layers", "disk I/O", {"store": "cursor"})
        snap = snapshot_layers(self.store)
        self.assertEqual(snap["task"], 3)
        self.assertFalse(snap["live_verified"])
        self.assertIn("task:pr203-memory-layers:step:ingest", snap["keys"]["task"])

    def test_ingest_without_chronicle_still_writes_org(self) -> None:
        (self.root / "notes.md").write_text("# Notes\n", encoding="utf-8")
        summary = ingest_markdown(
            self.root,
            self.store,
            session_id="tb_sess_notes",
            task_id="pr203-fallback",
            agent_id="unit",
        )
        self.assertEqual(summary["patterns"], [])
        self.assertGreaterEqual(self.store.count(MemoryLayer.ORGANIZATIONAL), 1)
        self.assertIn("org:pattern:md-ingest-catalog", self.store.keys(MemoryLayer.ORGANIZATIONAL))



REPO_ROOT = Path(__file__).resolve().parents[2]


class TestChronicleFacts(unittest.TestCase):
    """Verified Knowledge seeded from committed proof artifacts. A fact is
    written only when its artifact exists AND still carries the proof hash
    the fact was recorded against."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.store = MemoryStore(self.root / "layers.db")

    def tearDown(self) -> None:
        self.store.close()
        self.tmp.cleanup()

    def _place(self, fact_id: str, proof_hash: str) -> dict:
        import json
        fact = next(f for f in CHRONICLE_FACTS if f["id"] == fact_id)
        for rel in fact["evidence"]:
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            if rel.endswith(".json"):
                path.write_text(json.dumps({"proof_hash": proof_hash}), encoding="utf-8")
            else:
                path.write_text("# evidence\n", encoding="utf-8")
        return fact

    def test_facts_require_evidence_on_disk(self) -> None:
        self.assertEqual(chronicle_facts(self.root), [])

    def test_fact_with_matching_proof_hash_is_returned(self) -> None:
        fact = self._place("synthesis-calibration-v2-result", "")
        self._place("synthesis-calibration-v2-result", fact["proof_hash"])
        ids = [row["id"] for row in chronicle_facts(self.root)]
        self.assertIn("synthesis-calibration-v2-result", ids)

    def test_changed_artifact_refuses_fact(self) -> None:
        self._place("synthesis-calibration-v2-result", "0" * 64)
        with self.assertRaises(MemoryLayerError) as ctx:
            chronicle_facts(self.root)
        self.assertEqual(ctx.exception.code, "fact_evidence_mismatch")

    def test_every_fact_is_well_formed(self) -> None:
        for fact in CHRONICLE_FACTS:
            self.assertTrue(fact["fact"].strip())
            self.assertTrue(fact["how"].strip())
            self.assertTrue(fact["evidence"])
            self.assertLessEqual(fact["confidence"], 1.0)
            self.assertFalse(fact.get("live_verified"))

    def test_ingest_writes_facts_to_verified_layer(self) -> None:
        fact = self._place("synthesis-calibration-v1-result", "")
        self._place("synthesis-calibration-v1-result", fact["proof_hash"])
        summary = ingest_markdown(
            self.root, self.store, session_id="s", task_id="t", agent_id="unit"
        )
        self.assertIn("synthesis-calibration-v1-result", summary["facts"])
        self.assertIn(
            "verified:synthesis-calibration-v1-result",
            self.store.keys(MemoryLayer.VERIFIED_KNOWLEDGE),
        )


class TestRepoChronicle(unittest.TestCase):
    """Read-only checks against the real repository: every seeded lesson and
    fact must actually be backed by committed files right now."""

    def test_all_chronicle_patterns_have_evidence_in_repo(self) -> None:
        from thinkbox.memory_layers import CHRONICLE_PATTERNS
        found = {row["pattern_id"] for row in chronicle_patterns(REPO_ROOT)}
        expected = {pid for pid, _desc, _ev in CHRONICLE_PATTERNS}
        self.assertEqual(expected - found, set())

    def test_all_chronicle_facts_verify_in_repo(self) -> None:
        found = {row["id"] for row in chronicle_facts(REPO_ROOT)}
        self.assertEqual({f["id"] for f in CHRONICLE_FACTS} - found, set())

if __name__ == "__main__":
    unittest.main()
