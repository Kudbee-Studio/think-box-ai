"""Hermetic tests for the autonomous-loop action-integrity UI renderer (PR #251 follow-up).

The operator-facing chain indicator must distinguish four states — endpoint down,
durability disabled, valid, and tampered — and must reliably clear the warning
styling when a chain transitions back to valid.

Two layers:

1. Static assertions that the client source exposes the helpers and the four
   states (always run).
2. Runtime assertions executed in Node against the real client file, so the
   renderer's actual behaviour is verified rather than assumed. Skipped if Node
   is unavailable in the environment.
"""

from __future__ import annotations

import shutil
import subprocess
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_CLIENT = _ROOT / "public/control-plane/autonomous_loop_client.js"
_NODE_TEST = _ROOT / "tests/js/autonomous_loop_client_integrity.test.js"


class TestIntegrityRendererSource(unittest.TestCase):
    """Static guarantees about the client source."""

    def setUp(self) -> None:
        self.js = _CLIENT.read_text(encoding="utf-8")

    def test_fetch_uses_integrity_endpoint(self) -> None:
        self.assertIn("/api/v1/autonomous-loop/actions/integrity", self.js)

    def test_renderer_handles_all_four_states(self) -> None:
        for marker in ("OFFLINE", "NOT ATTACHED", "VALID", "TAMPERED"):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.js)

    def test_renderer_reads_integrity_elements(self) -> None:
        self.assertIn("integrityBadge", self.js)
        self.assertIn("integrityDetail", self.js)

    def test_renderer_clears_warning_style_on_valid(self) -> None:
        # Inline styles must be reset, else a recovered chain stays red.
        self.assertIn('badge.style.background = ""', self.js)
        self.assertIn('badge.style.color = ""', self.js)

    def test_helpers_exported(self) -> None:
        self.assertIn("fetchActionIntegrity", self.js)
        self.assertIn("renderActionIntegrity", self.js)


@unittest.skipIf(shutil.which("node") is None, "node not available")
class TestIntegrityRendererRuntime(unittest.TestCase):
    """Execute the renderer in Node against the real client file."""

    def test_node_suite_passes(self) -> None:
        self.assertTrue(_NODE_TEST.exists(), f"missing node fixture {_NODE_TEST}")
        proc = subprocess.run(
            ["node", str(_NODE_TEST)],
            cwd=str(_ROOT),
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(
            proc.returncode,
            0,
            f"Node integrity suite failed.\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}",
        )


if __name__ == "__main__":
    unittest.main()
