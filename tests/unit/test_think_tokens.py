"""Tests for think tokens: mint + exec-challenge Elo."""

from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

from core.memory.store import MemoryStore


class TestThinkTokens(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self._tmpdir, "test.db")
        self.store = MemoryStore(self.db_path)

    def test_mint_token(self):
        token_id = self.store.mint_token(box_id="tb-1", claim="echo hello")
        self.assertIsNotNone(token_id)
        token = self.store.get_token(token_id)
        self.assertEqual(token["box_id"], "tb-1")
        self.assertEqual(token["claim"], "echo hello")
        self.assertEqual(token["s"], 1.0)
        self.assertEqual(token["grounded"], 1)

    def test_mint_duplicate_returns_none(self):
        self.store.mint_token(box_id="tb-1", claim="echo hello")
        result = self.store.mint_token(box_id="tb-1", claim="echo hello")
        self.assertIsNone(result)

    def test_claim_cap_200(self):
        long_claim = "x" * 300
        token_id = self.store.mint_token(box_id="tb-1", claim=long_claim)
        token = self.store.get_token(token_id)
        self.assertEqual(len(token["claim"]), 200)

    def test_exec_challenge_increases_score(self):
        token_id = self.store.mint_token(box_id="tb-1", claim="echo hello")
        initial = self.store.get_token(token_id)["s"]
        self.store.add_challenge(token_id, "exec", outcome=1)
        updated = self.store.get_token(token_id)["s"]
        self.assertGreater(updated, initial)
        self.assertLessEqual(updated, 100.0)

    def test_exec_challenge_decreases_score_on_failure(self):
        token_id = self.store.mint_token(box_id="tb-1", claim="echo hello")
        # First increase
        self.store.add_challenge(token_id, "exec", outcome=1)
        after_success = self.store.get_token(token_id)["s"]
        # Then decrease
        self.store.add_challenge(token_id, "exec", outcome=-1)
        after_fail = self.store.get_token(token_id)["s"]
        self.assertLess(after_fail, after_success)
        self.assertGreaterEqual(after_fail, 0.0)

    def test_score_floor(self):
        token_id = self.store.mint_token(box_id="tb-1", claim="echo hello")
        for _ in range(20):
            self.store.add_challenge(token_id, "exec", outcome=-1)
        token = self.store.get_token(token_id)
        self.assertGreaterEqual(token["s"], 0.0)

    def test_list_tokens(self):
        self.store.mint_token(box_id="tb-1", claim="echo a")
        self.store.mint_token(box_id="tb-1", claim="echo b")
        self.store.mint_token(box_id="tb-2", claim="echo c")
        tokens = self.store.list_tokens("tb-1")
        self.assertEqual(len(tokens), 2)

    def test_list_challenges(self):
        token_id = self.store.mint_token(box_id="tb-1", claim="echo hello")
        self.store.add_challenge(token_id, "exec", outcome=1)
        self.store.add_challenge(token_id, "exec", outcome=-1)
        challenges = self.store.list_challenges(token_id)
        self.assertEqual(len(challenges), 2)
        self.assertEqual(challenges[0]["type"], "exec")
        self.assertEqual(challenges[0]["w"], 3.0)

    def test_unknown_challenge_type_rejected(self):
        token_id = self.store.mint_token(box_id="tb-1", claim="echo hello")
        result = self.store.add_challenge(token_id, "invalid_type", outcome=1)
        self.assertIsNone(result)

    def test_challenge_nonexistent_token(self):
        result = self.store.add_challenge("tt-nonexistent", "exec", outcome=1)
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
