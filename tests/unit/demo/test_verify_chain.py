"""Tests: verify-chain button presence in dashboard."""

import unittest
from pathlib import Path


class TestVerifyChainButton(unittest.TestCase):
    def test_verify_chain_button_present(self) -> None:
        html = Path("public/control-plane/demo.html").read_text()
        self.assertIn("Verify chain", html)
        self.assertIn("verifyChain()", html)

    def test_verify_chain_api_called(self) -> None:
        html = Path("public/control-plane/demo.html").read_text()
        self.assertIn("/api/v1/receipts/verify", html)
