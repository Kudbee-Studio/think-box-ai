from __future__ import annotations

import os
import unittest
from unittest import mock

from thinkbox.pipeline_founder_proof_preflight import (
    assert_founder_proof_key_configured,
    resolve_founder_proof_key,
)


class TestFounderProofPreflight(unittest.TestCase):
    def test_staging_rejects_default_key(self) -> None:
        with mock.patch.dict(
            os.environ,
            {
                "THINKBOX_PIPELINE_DEPLOYMENT_ENV": "staging",
                "THINKBOX_FOUNDER_MERGE_PROOF_KEY": "",
            },
            clear=False,
        ):
            with self.assertRaises(RuntimeError):
                assert_founder_proof_key_configured()

    def test_staging_accepts_configured_key(self) -> None:
        with mock.patch.dict(
            os.environ,
            {
                "THINKBOX_PIPELINE_DEPLOYMENT_ENV": "staging",
                "THINKBOX_FOUNDER_MERGE_PROOF_KEY": "operator-secret-key",
            },
            clear=False,
        ):
            self.assertEqual(resolve_founder_proof_key(), "operator-secret-key")

    def test_hermetic_dev_allows_default(self) -> None:
        env = {
            k: v
            for k, v in os.environ.items()
            if k not in ("THINKBOX_PIPELINE_DEPLOYMENT_ENV", "THINKBOX_FOUNDER_MERGE_PROOF_KEY")
        }
        with mock.patch.dict(os.environ, env, clear=True):
            key = resolve_founder_proof_key()
            self.assertTrue(key)


if __name__ == "__main__":
    unittest.main()
