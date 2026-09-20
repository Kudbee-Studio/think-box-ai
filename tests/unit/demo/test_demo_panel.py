"""Tests: dashboard demo panel."""

import unittest
from pathlib import Path


class TestDemoPanel(unittest.TestCase):
    def setUp(self) -> None:
        self.html = Path("public/control-plane/demo.html").read_text()

    def test_has_copy_cmd_button(self) -> None:
        self.assertIn("Copy run cmd", self.html)
        self.assertIn("copyCmd()", self.html)

    def test_has_last_run_summary(self) -> None:
        self.assertIn("Last Run Summary", self.html)

    def test_has_run_button(self) -> None:
        self.assertIn("runDemo()", self.html)

    def test_has_verify_chain_button(self) -> None:
        self.assertIn("Verify chain", self.html)
        self.assertIn("verifyChain()", self.html)

    def test_dark_design(self) -> None:
        self.assertIn("design-system.css", self.html)
        self.assertIn("components.css", self.html)
