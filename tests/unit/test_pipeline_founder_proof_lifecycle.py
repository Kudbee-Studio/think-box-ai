from __future__ import annotations

import unittest

from thinkbox.pipeline_founder_proof_lifecycle import (
    build_proof_attestation,
    validate_proof_key_rotation,
)


class TestFounderProofLifecycle(unittest.TestCase):
    def test_attestation_includes_fingerprint_not_raw_key(self) -> None:
        att = build_proof_attestation(42, "secret-key-v1", key_version="v1")
        self.assertEqual(att["pr_number"], 42)
        self.assertNotIn("secret-key", str(att))
        self.assertTrue(att["founder_proof"])

    def test_rotation_detected(self) -> None:
        old_fp = validate_proof_key_rotation("key-a", "")["current_fingerprint"]
        rot = validate_proof_key_rotation("key-b", old_fp)
        self.assertTrue(rot["rotation_detected"])


if __name__ == "__main__":
    unittest.main()
