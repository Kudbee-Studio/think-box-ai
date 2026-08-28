"""Unit tests for core.foundation.secrets."""

from __future__ import annotations

import os
import unittest

from core.foundation.secrets import SecretResolver, SecretResolutionError


class TestSecretResolverResolve(unittest.TestCase):
    def test_resolve_from_env_var(self) -> None:
        os.environ["THINKBOX_TEST_KEY"] = "from_env"
        try:
            resolver = SecretResolver()
            self.assertEqual(resolver.resolve("TEST_KEY"), "from_env")
        finally:
            del os.environ["THINKBOX_TEST_KEY"]

    def test_resolve_falls_back_to_default(self) -> None:
        resolver = SecretResolver(defaults={"MY_KEY": "default_val"})
        self.assertEqual(resolver.resolve("MY_KEY"), "default_val")

    def test_resolve_returns_none_when_absent(self) -> None:
        resolver = SecretResolver()
        self.assertIsNone(resolver.resolve("NONEXISTENT_KEY_XYZ"))

    def test_env_var_takes_precedence_over_default(self) -> None:
        os.environ["THINKBOX_PRECEDENCE_KEY"] = "env_wins"
        try:
            resolver = SecretResolver(defaults={"PRECEDENCE_KEY": "default_loses"})
            self.assertEqual(resolver.resolve("PRECEDENCE_KEY"), "env_wins")
        finally:
            del os.environ["THINKBOX_PRECEDENCE_KEY"]


class TestSecretResolverResolveRequired(unittest.TestCase):
    def test_resolve_required_returns_value_from_env(self) -> None:
        os.environ["THINKBOX_REQUIRED_KEY"] = "secret_value"
        try:
            resolver = SecretResolver()
            self.assertEqual(resolver.resolve_required("REQUIRED_KEY"), "secret_value")
        finally:
            del os.environ["THINKBOX_REQUIRED_KEY"]

    def test_resolve_required_returns_value_from_default(self) -> None:
        resolver = SecretResolver(defaults={"REQ_KEY": "default_secret"})
        self.assertEqual(resolver.resolve_required("REQ_KEY"), "default_secret")

    def test_resolve_required_raises_when_absent(self) -> None:
        resolver = SecretResolver()
        with self.assertRaises(SecretResolutionError) as ctx:
            resolver.resolve_required("MISSING_KEY_XYZ")
        self.assertEqual(ctx.exception.key, "MISSING_KEY_XYZ")

    def test_resolve_required_raises_when_default_is_none(self) -> None:
        resolver = SecretResolver(defaults={"NULL_KEY": None})
        with self.assertRaises(SecretResolutionError) as ctx:
            resolver.resolve_required("NULL_KEY")
        self.assertEqual(ctx.exception.key, "NULL_KEY")


class TestSecretResolverIsSet(unittest.TestCase):
    def test_is_set_true_when_env_var_present(self) -> None:
        os.environ["THINKBOX_SET_KEY"] = "value"
        try:
            resolver = SecretResolver()
            self.assertTrue(resolver.is_set("SET_KEY"))
        finally:
            del os.environ["THINKBOX_SET_KEY"]

    def test_is_set_true_when_default_present(self) -> None:
        resolver = SecretResolver(defaults={"DEF_KEY": "val"})
        self.assertTrue(resolver.is_set("DEF_KEY"))

    def test_is_set_false_when_absent(self) -> None:
        resolver = SecretResolver()
        self.assertFalse(resolver.is_set("UNSET_KEY_XYZ"))

    def test_is_set_false_when_default_is_none(self) -> None:
        resolver = SecretResolver(defaults={"K": None})
        self.assertFalse(resolver.is_set("K"))

    def test_is_set_consistent_with_resolve(self) -> None:
        resolver = SecretResolver(defaults={"A": "yes", "B": None})
        self.assertTrue(resolver.is_set("A"))
        self.assertFalse(resolver.is_set("B"))
        self.assertEqual(resolver.resolve("A"), "yes")
        self.assertIsNone(resolver.resolve("B"))


class TestSecretResolutionError(unittest.TestCase):
    def test_error_stores_key(self) -> None:
        err = SecretResolutionError("MY_KEY")
        self.assertEqual(err.key, "MY_KEY")

    def test_error_message_contains_key(self) -> None:
        err = SecretResolutionError("MY_KEY")
        self.assertIn("MY_KEY", str(err))

    def test_error_message_contains_env_var_hint(self) -> None:
        err = SecretResolutionError("MY_KEY")
        self.assertIn("THINKBOX_MY_KEY", str(err))


if __name__ == "__main__":
    unittest.main()
