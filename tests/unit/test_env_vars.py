"""Unit tests for thinkbox.env_vars (PR #200)."""

from __future__ import annotations

import unittest

from thinkbox.env_vars.boolean import parse_bool
from thinkbox.env_vars.cassette import cassette_environ, load_cassette
from thinkbox.env_vars.ci_matrix import minimal_hermetic_environ
from thinkbox.env_vars.documentation import documented_keys, schema_keys_union
from thinkbox.env_vars.errors import EnvVarsError
from thinkbox.env_vars.fixtures import malformed_int_environ, valid_cloud_worker_environ
from thinkbox.env_vars.hub import evaluate_env_pack, load_all_parsed
from thinkbox.env_vars.integer import parse_int
from thinkbox.env_vars.parse import parse_schema
from thinkbox.env_vars.profile import EnvProfile, detect_profile
from thinkbox.env_vars.redact import looks_sensitive_key, redact_environ_for_display
from thinkbox.env_vars.secrets_shape import sanitize_error_message
from thinkbox.env_vars.cloud_execution_keys import CLOUD_EXECUTION_FIELDS
from thinkbox.env_vars.validate import validate_fields
from thinkbox.env_vars.version import GATE_ID, PR_NUMBER


class TestEnvVarsParse(unittest.TestCase):
    def test_bool_truthy(self) -> None:
        self.assertTrue(parse_bool("yes", "X"))

    def test_bool_invalid(self) -> None:
        with self.assertRaises(EnvVarsError):
            parse_bool("maybe", "X")

    def test_int_valid(self) -> None:
        self.assertEqual(parse_int("42", "N"), 42)

    def test_int_malformed(self) -> None:
        with self.assertRaises(EnvVarsError):
            parse_int("nope", "N")

    def test_malformed_cassette_fails_validation(self) -> None:
        env = cassette_environ("malformed_int.json")
        result = validate_fields(CLOUD_EXECUTION_FIELDS, env)
        self.assertFalse(result.ok)

    def test_valid_cassette_loads(self) -> None:
        env = cassette_environ("valid_minimal.json")
        parsed = load_all_parsed(env)
        self.assertIn("THINKBOX_CLOUD_EXEC_WORKER_ID", parsed)

    def test_redact_sensitive_keys(self) -> None:
        out = redact_environ_for_display({"INCEPTION_API_KEY": "sk-test-placeholder-not-real"})
        self.assertEqual(out["INCEPTION_API_KEY"], "[REDACTED]")

    def test_looks_sensitive(self) -> None:
        self.assertTrue(looks_sensitive_key("THINKBOX_API_KEY"))

    def test_profile_ci(self) -> None:
        self.assertEqual(detect_profile({"CI": "true"}), EnvProfile.CI)

    def test_evaluate_pack_hermetic(self) -> None:
        summary = evaluate_env_pack(minimal_hermetic_environ())
        self.assertEqual(summary["gate_id"], GATE_ID)
        self.assertEqual(summary["pr_number"], PR_NUMBER)
        self.assertFalse(summary["live_verified"])

    def test_valid_cloud_worker_fixture(self) -> None:
        result = validate_fields(CLOUD_EXECUTION_FIELDS, valid_cloud_worker_environ())
        self.assertTrue(result.ok)

    def test_malformed_int_fixture(self) -> None:
        result = validate_fields(CLOUD_EXECUTION_FIELDS, malformed_int_environ())
        self.assertFalse(result.ok)

    def test_cassette_metadata(self) -> None:
        doc = load_cassette("valid_minimal.json")
        self.assertFalse(doc["live_verified"])

    def test_documented_keys_nonempty(self) -> None:
        self.assertGreater(len(documented_keys()), 5)

    def test_schema_keys_overlap(self) -> None:
        self.assertGreater(len(schema_keys_union()), 10)

    def test_sanitize_error(self) -> None:
        msg = sanitize_error_message("failed", env_key="THINKBOX_API_KEY")
        self.assertEqual(msg, "[REDACTED_ERROR]")

    def test_parse_schema_cloud_fields(self) -> None:
        parsed = parse_schema(CLOUD_EXECUTION_FIELDS, valid_cloud_worker_environ())
        self.assertEqual(parsed["THINKBOX_CLOUD_EXEC_MAX_ACTIVE_JOBS"], 2)


if __name__ == "__main__":
    unittest.main()
