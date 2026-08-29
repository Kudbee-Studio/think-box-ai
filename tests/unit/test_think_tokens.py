"""Tests for think tokens: mint + exec-challenge Elo."""

from __future__ import annotations

import json
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

    def test_mint_token_empty_box_id_raises(self):
        with self.assertRaises(ValueError):
            self.store.mint_token(box_id="", claim="test")

    def test_mint_token_empty_claim_raises(self):
        with self.assertRaises(ValueError):
            self.store.mint_token(box_id="tb-1", claim="")

    def test_add_challenge_invalid_outcome_raises(self):
        token_id = self.store.mint_token(box_id="tb-1", claim="test")
        with self.assertRaises(ValueError):
            self.store.add_challenge(token_id, "exec", outcome=5)

    def test_get_token_empty_id(self):
        self.assertIsNone(self.store.get_token(""))

    def test_list_tokens_empty_id(self):
        self.assertEqual(self.store.list_tokens(""), [])

    def test_replay_challenge(self):
        token_id = self.store.mint_token(box_id="tb-1", claim="test")
        self.store.add_challenge(token_id, "exec", outcome=1)
        initial = self.store.get_token(token_id)["s"]
        challenge_id = self.store.challenge_replay(token_id)
        self.assertIsNotNone(challenge_id)
        token = self.store.get_token(token_id)
        self.assertGreater(token["s"], initial)
        challenges = self.store.list_challenges(token_id)
        self.assertEqual(len(challenges), 2)
        self.assertEqual(challenges[1]["type"], "replay")
        self.assertEqual(challenges[1]["w"], 1.0)

    def test_replay_no_prior_challenge(self):
        token_id = self.store.mint_token(box_id="tb-1", claim="test")
        result = self.store.challenge_replay(token_id)
        self.assertIsNone(result)

    # ------------------------------------------------------------------
    # Jury challenge tests
    # ------------------------------------------------------------------
    def test_jury_no_url_returns_none(self):
        token_id = self.store.mint_token(box_id="tb-1", claim="echo hello")
        result = self.store.challenge_jury(token_id, None)
        self.assertIsNone(result)

    def test_jury_empty_url_returns_none(self):
        token_id = self.store.mint_token(box_id="tb-1", claim="echo hello")
        result = self.store.challenge_jury(token_id, "")
        self.assertIsNone(result)

    def test_jury_nonexistent_token(self):
        result = self.store.challenge_jury("tt-nonexistent", "http://localhost:8000")
        self.assertIsNone(result)


class TestJuryChallengeMocked(unittest.TestCase):
    """Tests for jury challenge with mocked HTTP responses."""

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self._tmpdir, "test.db")
        self.store = MemoryStore(self.db_path)

    def _mock_response(self, content: str):
        mock_resp = unittest.mock.MagicMock()
        mock_resp.read.return_value = json.dumps({
            "choices": [{"message": {"content": content}}]
        }).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = lambda s, *a: None
        return mock_resp

    def test_jury_yes_increases_score(self):
        token_id = self.store.mint_token(box_id="tb-1", claim="2+2=4")
        initial = self.store.get_token(token_id)["s"]

        with unittest.mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = self._mock_response("YES")
            challenge_id = self.store.challenge_jury(token_id, "http://localhost:8000")

        self.assertIsNotNone(challenge_id)
        token = self.store.get_token(token_id)
        self.assertGreater(token["s"], initial)
        challenges = self.store.list_challenges(token_id)
        self.assertEqual(len(challenges), 1)
        self.assertEqual(challenges[0]["type"], "jury")
        self.assertEqual(challenges[0]["w"], 2.0)
        self.assertEqual(challenges[0]["o"], 1)

    def test_jury_no_decreases_score(self):
        token_id = self.store.mint_token(box_id="tb-1", claim="2+2=5")
        initial = self.store.get_token(token_id)["s"]

        with unittest.mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = self._mock_response("NO")
            challenge_id = self.store.challenge_jury(token_id, "http://localhost:8000")

        self.assertIsNotNone(challenge_id)
        token = self.store.get_token(token_id)
        self.assertLess(token["s"], initial)

    def test_jury_garbage_reply_outcome_zero(self):
        token_id = self.store.mint_token(box_id="tb-1", claim="something")

        with unittest.mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = self._mock_response("maybe perhaps")
            challenge_id = self.store.challenge_jury(token_id, "http://localhost:8000")

        self.assertIsNotNone(challenge_id)
        challenges = self.store.list_challenges(token_id)
        self.assertEqual(challenges[0]["o"], 0)
        # Score changes slightly due to Elo formula (o - expected)
        self.assertNotEqual(self.store.get_token(token_id)["s"], 1.0)

    def test_jury_timeout_returns_none(self):
        token_id = self.store.mint_token(box_id="tb-1", claim="test")

        with unittest.mock.patch("urllib.request.urlopen", side_effect=TimeoutError):
            result = self.store.challenge_jury(token_id, "http://localhost:8000")

        self.assertIsNone(result)
        self.assertEqual(len(self.store.list_challenges(token_id)), 0)

    def test_jury_connection_error_returns_none(self):
        token_id = self.store.mint_token(box_id="tb-1", claim="test")

        import urllib.error
        with unittest.mock.patch("urllib.request.urlopen", side_effect=urllib.error.URLError("refused")):
            result = self.store.challenge_jury(token_id, "http://localhost:8000")

        self.assertIsNone(result)
        self.assertEqual(len(self.store.list_challenges(token_id)), 0)


if __name__ == "__main__":
    unittest.main()
