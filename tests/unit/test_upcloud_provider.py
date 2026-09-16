"""Unit tests for UpCloud ExecutionProvider.

All tests are deterministic and mocked — no real API calls are made.
Credential source precedence: UPCLOUD_API_MAIN first, UPCLOUD_API_KEY fallback.
No real credential values are embedded in any test.
Live smoke tests are in tests/integration/test_upcloud_live.py.
"""

from __future__ import annotations

import json
import os
import unittest
from unittest.mock import MagicMock, patch

from core.foundation.errors import ProviderUnavailableError
from core.providers.execution import (
    CapabilityStatus,
    ExecutionProvider,
    ExecutionProviderCapabilities,
)
from core.providers.upcloud import UpCloudExecutionProvider


class TestUpCloudProviderInit(unittest.TestCase):
    def test_init_with_config(self) -> None:
        provider = UpCloudExecutionProvider({"api_key": "test-key"})
        self.assertEqual(provider.provider_name, "upcloud")
        self.assertEqual(provider.auth_status, "untested")

    def test_init_without_any_credential(self) -> None:
        with patch.dict(
            os.environ, {"UPCLOUD_API_MAIN": "", "UPCLOUD_API_KEY": ""}, clear=True
        ):
            provider = UpCloudExecutionProvider()
            self.assertEqual(provider.provider_name, "upcloud")
            self.assertEqual(provider.credential_source, "none")
            self.assertEqual(provider._api_key, "")

    def test_init_prefers_main(self) -> None:
        with patch.dict(
            os.environ,
            {"UPCLOUD_API_MAIN": "main-key", "UPCLOUD_API_KEY": "fallback-key"},
            clear=True,
        ):
            provider = UpCloudExecutionProvider({"api_key": "config-key"})
            self.assertEqual(provider._api_key, "main-key")
            self.assertEqual(provider.credential_source, "UPCLOUD_API_MAIN")

    def test_init_fallback_to_key(self) -> None:
        with patch.dict(
            os.environ,
            {"UPCLOUD_API_MAIN": "", "UPCLOUD_API_KEY": "fallback-key"},
            clear=True,
        ):
            provider = UpCloudExecutionProvider()
            self.assertEqual(provider._api_key, "fallback-key")
            self.assertEqual(provider.credential_source, "UPCLOUD_API_KEY")

    def test_init_config_when_no_env(self) -> None:
        with patch.dict(
            os.environ, {"UPCLOUD_API_MAIN": "", "UPCLOUD_API_KEY": ""}, clear=True
        ):
            provider = UpCloudExecutionProvider({"api_key": "config-key"})
            self.assertEqual(provider._api_key, "config-key")
            self.assertEqual(provider.credential_source, "config")

    def test_provider_name(self) -> None:
        provider = UpCloudExecutionProvider()
        self.assertEqual(provider.provider_name, "upcloud")

    def test_capabilities_default(self) -> None:
        provider = UpCloudExecutionProvider()
        caps = provider.capabilities
        for attr in [
            "list_servers", "get_server", "create_server", "delete_server",
            "list_storage", "get_storage", "create_storage", "delete_storage",
            "list_networks", "get_ip", "assign_ip", "list_locations",
            "discover_gpu", "check_availability", "create_server_from_template",
            "reboot_server",
        ]:
            self.assertEqual(
                getattr(caps, attr), CapabilityStatus.NOT_TESTED
            )

    def test_evidence_starts_empty(self) -> None:
        provider = UpCloudExecutionProvider()
        self.assertEqual(provider.evidence, [])


class TestUpCloudProviderAuth(unittest.TestCase):
    def test_check_auth_no_key(self) -> None:
        with patch.dict(
            os.environ, {"UPCLOUD_API_MAIN": "", "UPCLOUD_API_KEY": ""}, clear=True
        ):
            provider = UpCloudExecutionProvider()
            result = provider.check_auth()
        self.assertEqual(result.status, CapabilityStatus.DENIED)
        self.assertIn("No UPCLOUD_API_MAIN", result.detail)

    def test_check_auth_invalid_token(self) -> None:
        provider = UpCloudExecutionProvider({"api_key": "bad-token"})
        with patch.object(
            provider, "_request", return_value=(401, {"error": "Unauthorized"})
        ):
            result = provider.check_auth()
        self.assertEqual(result.status, CapabilityStatus.DENIED)
        self.assertIn("401", result.detail)
        self.assertEqual(provider.auth_status, "denied")

    def test_check_auth_success(self) -> None:
        provider = UpCloudExecutionProvider({"api_key": "good-token"})
        with patch.object(
            provider, "_request", return_value=(200, {"customer_id": "abc"})
        ):
            result = provider.check_auth()
        self.assertEqual(result.status, CapabilityStatus.VERIFIED)
        self.assertEqual(provider.auth_status, "authenticated")
        self.assertIn(provider.credential_source, result.detail)
        self.assertNotIn("good-token", result.detail)

    def test_check_auth_unreachable(self) -> None:
        provider = UpCloudExecutionProvider({"api_key": "token"})
        with patch.object(
            provider, "_request", side_effect=ProviderUnavailableError("unreachable")
        ):
            result = provider.check_auth()
        self.assertEqual(result.status, CapabilityStatus.DENIED)

    def test_check_auth_never_logs_token(self) -> None:
        provider = UpCloudExecutionProvider({"api_key": "super-secret-token"})
        with patch.object(
            provider, "_request", return_value=(200, {})
        ):
            provider.check_auth()
        for record in provider.evidence:
            serialized = str(record.__dict__)
            self.assertNotIn("super-secret-token", serialized)
        import logging
        log_capture = logging.getLogger()
        for handler in log_capture.handlers:
            if hasattr(handler, "stream") and handler.stream:
                content = (
                    handler.stream.getvalue()
                    if hasattr(handler.stream, "getvalue")
                    else ""
                )
                self.assertNotIn("super-secret-token", content)


class TestUpCloudProviderCapabilities(unittest.TestCase):
    def test_discover_capabilities_auth_failed(self) -> None:
        provider = UpCloudExecutionProvider({"api_key": "bad"})
        with patch.object(
            provider, "check_auth", return_value=MagicMock(
                status=CapabilityStatus.DENIED
            )
        ) as mock_auth:
            checks = provider.discover_capabilities()
        self.assertTrue(mock_auth.called)
        self.assertTrue(all(c.status == CapabilityStatus.NOT_TESTED for c in checks[1:]))

    def test_discover_capabilities_verified(self) -> None:
        provider = UpCloudExecutionProvider({"api_key": "good"})
        with patch.object(
            provider, "_request", return_value=(200, {})
        ):
            checks = provider.discover_capabilities()
        self.assertEqual(checks[0].status, CapabilityStatus.VERIFIED)
        for check in checks[1:]:
            self.assertIn(
                check.status,
                [CapabilityStatus.VERIFIED, CapabilityStatus.NOT_TESTED],
            )

    def test_discover_capabilities_updates_capabilities(self) -> None:
        provider = UpCloudExecutionProvider({"api_key": "good"})
        with patch.object(provider, "_request", return_value=(200, {})):
            provider.discover_capabilities()
        caps = provider.capabilities
        self.assertEqual(caps.list_servers, CapabilityStatus.VERIFIED)

    def test_discover_capabilities_requires_admin(self) -> None:
        provider = UpCloudExecutionProvider({"api_key": "good"})
        with patch.object(
            provider, "_request", return_value=(403, {"error": "forbidden"})
        ):
            checks = provider.discover_capabilities()
        for check in checks[1:]:
            self.assertEqual(check.status, CapabilityStatus.REQUIRES_ADMIN_APPROVAL)


class TestUpCloudProviderPlan(unittest.TestCase):
    def test_plan_dry_run(self) -> None:
        provider = UpCloudExecutionProvider()
        actions = [
            {"action": "create_server", "destructive": False, "billable": True},
            {"action": "list_servers", "destructive": False, "billable": False},
        ]
        plan = provider.plan("job-1", actions)
        self.assertTrue(plan.dry_run)
        self.assertTrue(plan.requires_approval)
        self.assertEqual(len(plan.actions), 2)
        self.assertEqual(plan.job_id, "job-1")

    def test_plan_no_approval_needed(self) -> None:
        provider = UpCloudExecutionProvider()
        actions = [{"action": "list_servers", "destructive": False, "billable": False}]
        plan = provider.plan("job-2", actions)
        self.assertFalse(plan.requires_approval)

    def test_plan_generates_evidence(self) -> None:
        provider = UpCloudExecutionProvider()
        actions = [{"action": "list_servers"}]
        provider.plan("job-3", actions)
        self.assertEqual(len(provider.evidence), 1)
        ev = provider.evidence[0]
        self.assertEqual(ev.action, "plan")
        self.assertTrue(ev.dry_run)


class TestUpCloudProviderExecute(unittest.TestCase):
    def test_execute_not_authenticated(self) -> None:
        provider = UpCloudExecutionProvider({"api_key": "bad"})
        provider._auth_status = "denied"
        result = provider.execute("job-1", "list_servers")
        self.assertFalse(result.success)
        self.assertIn("authenticated", result.error)

    def test_execute_destructive_without_approval(self) -> None:
        provider = UpCloudExecutionProvider({"api_key": "good"})
        provider._auth_status = "authenticated"
        result = provider.execute("job-1", "delete_server", {"server_uuid": "srv-1"})
        self.assertFalse(result.success)
        self.assertIn("approval", result.error.lower())

    def test_execute_billable_without_approval(self) -> None:
        provider = UpCloudExecutionProvider({"api_key": "good"})
        provider._auth_status = "authenticated"
        result = provider.execute(
            "job-1", "create_server", {"name": "test"}
        )
        self.assertFalse(result.success)
        self.assertIn("approval", result.error.lower())

    def test_execute_with_approval_success(self) -> None:
        provider = UpCloudExecutionProvider({"api_key": "good"})
        provider._auth_status = "authenticated"
        provider._auth_checked = True
        with patch.object(provider, "_request", return_value=(200, {"uuid": "srv-123"})):
            result = provider.execute(
                "job-1", "get_server", {"server_uuid": "srv-123"}, approve=True
            )
        self.assertTrue(result.success)
        self.assertEqual(result.resource_id, "srv-123")

    def test_execute_create_with_approval(self) -> None:
        provider = UpCloudExecutionProvider({"api_key": "good"})
        provider._auth_status = "authenticated"
        provider._auth_checked = True
        with patch.object(
            provider, "_request", return_value=(201, {"uuid": "srv-456"})
        ):
            result = provider.execute(
                "job-1", "create_server", {"name": "test"}, approve=True
            )
        self.assertTrue(result.success)
        self.assertEqual(result.resource_id, "srv-456")

    def test_execute_http_error(self) -> None:
        provider = UpCloudExecutionProvider({"api_key": "good"})
        provider._auth_status = "authenticated"
        provider._auth_checked = True
        with patch.object(
            provider, "_request", return_value=(404, {"error": "not found"})
        ):
            result = provider.execute(
                "job-1", "get_server", {"server_uuid": "missing"}, approve=True
            )
        self.assertFalse(result.success)
        self.assertIn("404", result.error)

    def test_execute_connection_error(self) -> None:
        provider = UpCloudExecutionProvider({"api_key": "good"})
        provider._auth_status = "authenticated"
        provider._auth_checked = True
        with patch.object(
            provider, "_request", side_effect=ProviderUnavailableError("unreachable")
        ):
            result = provider.execute("job-1", "list_servers", approve=True)
        self.assertFalse(result.success)

    def test_execute_unknown_action(self) -> None:
        provider = UpCloudExecutionProvider({"api_key": "good"})
        provider._auth_status = "authenticated"
        provider._auth_checked = True
        result = provider.execute("job-1", "unknown_action")
        self.assertFalse(result.success)
        self.assertIn("Unknown", result.error)

    def test_execute_generates_evidence(self) -> None:
        provider = UpCloudExecutionProvider({"api_key": "good"})
        provider._auth_status = "authenticated"
        provider._auth_checked = True
        with patch.object(provider, "_request", return_value=(200, {"uuid": "x"})):
            provider.execute("job-1", "list_servers", approve=True)
        self.assertEqual(len(provider.evidence), 1)
        ev = provider.evidence[0]
        self.assertEqual(ev.action, "list_servers")
        self.assertEqual(ev.result, "SUCCESS")


class TestUpCloudRegistry(unittest.TestCase):
    def test_registry_has_upcloud(self) -> None:
        from core.providers import ProviderExecutionRegistry
        cls = ProviderExecutionRegistry.get("upcloud")
        self.assertIsNotNone(cls)
        self.assertTrue(issubclass(cls, ExecutionProvider))

    def test_registry_list_providers(self) -> None:
        from core.providers import ProviderExecutionRegistry
        providers = ProviderExecutionRegistry.list_providers()
        self.assertIn("upcloud", providers)


class TestUpCloudNoSecretsInEvidence(unittest.TestCase):
    def test_evidence_does_not_contain_api_key(self) -> None:
        provider = UpCloudExecutionProvider({"api_key": "super-secret"})
        provider._auth_status = "authenticated"
        with patch.object(provider, "_request", return_value=(200, {})):
            provider.execute("job-1", "list_servers", approve=True)
        for record in provider.evidence:
            serialized = str(record.__dict__)
            self.assertNotIn("super-secret", serialized)

    def test_plan_does_not_contain_api_key(self) -> None:
        provider = UpCloudExecutionProvider({"api_key": "super-secret"})
        plan = provider.plan("job-1", [{"action": "list_servers"}])
        serialized = str(plan.__dict__)
        self.assertNotIn("super-secret", serialized)


if __name__ == "__main__":
    unittest.main()
