"""Unit tests for thinkbox/substrate.py — live substrate binding."""

import os
import unittest
from unittest.mock import MagicMock, Mock, patch

from thinkbox.substrate import (
    SubstrateProbe,
    ThinkBoxVectorSync,
    bind_think_box,
    detect_substrate,
)
from thinkbox.workspace import WorkspaceRegistry


class TestDetectSubstrate(unittest.TestCase):
    def test_upstash_box_priority(self):
        with patch.dict(os.environ, {"UPSTASH_PUBLIC_BOX_URL": "https://mybox.preview.box.upstash.com/"}, clear=True):
            self.assertEqual(detect_substrate(), "mybox.preview.box.upstash.com")

    def test_upcloud_gpu(self):
        with patch.dict(os.environ, {"THINKBOX_UPCLOUD_API_TOKEN": "x"}, clear=True):
            self.assertEqual(detect_substrate(), "upcloud-gpu")

    def test_ci_if_ci_var(self):
        with patch.dict(os.environ, {"CI": "true"}, clear=True):
            self.assertEqual(detect_substrate(), "ci")

    def test_local_fallback(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(detect_substrate(), "local")


class TestSubstrateProbe(unittest.TestCase):
    def test_probe_reports_tools_as_bools(self):
        probe = SubstrateProbe()
        report = probe.probe()
        self.assertTrue(report.substrate)
        by_name = {p.tool: p.available for p in report.isolation_tools}
        self.assertIn("unshare", by_name)
        self.assertIsInstance(by_name["unshare"], bool)
        self.assertEqual(len(probe.history()), 1)


class TestThinkBoxVectorSync(unittest.TestCase):
    def test_disabled_without_env(self):
        with patch.dict(os.environ, {}, clear=True):
            sync = ThinkBoxVectorSync()
            self.assertFalse(sync.enabled)
            self.assertFalse(sync.snapshot(Mock()))
            self.assertIsNone(sync.fetch("box_x"))
            self.assertFalse(sync.delete("box_x"))

    def test_vector_dimensions_match_backend(self):
        vector = ThinkBoxVectorSync._vector_for("box_abc")
        self.assertEqual(len(vector), 1536)
        self.assertEqual(vector, ThinkBoxVectorSync._vector_for("box_abc"))

    def test_upsert_payload_shape(self):
        registry = WorkspaceRegistry()
        box = registry.create(owner_id="a1", state={"k": "v"})
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"result":"Success"}'
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.__exit__.return_value = False
        with patch.dict(os.environ, {"UPSTASH_VECTOR_REST_URL": "https://vec.upstash.io/", "UPSTASH_VECTOR_REST_TOKEN": "t"}, clear=True):
            sync = ThinkBoxVectorSync()
            with patch("urllib.request.urlopen", return_value=mock_resp) as m:
                self.assertTrue(sync.snapshot(box))
                path = m.call_args.args[0].full_url
                self.assertEqual(path, "https://vec.upstash.io/upsert")
                payload = m.call_args.args[0].data
                self.assertIn(b'"id": "thinkbox:', payload)
                self.assertIn(b'"vector":', payload)

    def test_bind_uses_detected_substrate(self):
        registry = WorkspaceRegistry()
        box = registry.create(owner_id="a1")
        with patch.dict(os.environ, {"UPSTASH_PUBLIC_BOX_URL": "https://live.preview.box.upstash.com/"}, clear=True):
            result = bind_think_box(box, sync=Mock())
            self.assertIn("live.preview.box.upstash.com", result["substrate"])
            self.assertEqual(box.substrate, result["substrate"])


if __name__ == "__main__":
    unittest.main()