"""Tests for PR-scoped database provisioning and lifecycle.

Covers: provisioning, isolation, TTL, cleanup, failure, repeated cleanup.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest.mock import patch

from thinkbox.pr_db import (
    PRDatabaseConfig,
    PRDatabaseProvisioner,
    PRDatabaseRecord,
    PRDBLifecycle,
    PRDBState,
)


class TestPRDBConfig(unittest.TestCase):
    def test_default_ttl(self) -> None:
        config = PRDatabaseConfig(pr_number=104)
        self.assertEqual(config.ttl_hours, 72)

    def test_custom_ttl(self) -> None:
        config = PRDatabaseConfig(pr_number=104, ttl_hours=24)
        self.assertEqual(config.ttl_hours, 24)

    def test_test_mode(self) -> None:
        config = PRDatabaseConfig(pr_number=104, test_mode=True)
        self.assertTrue(config.test_mode)

    def test_pr_number_tied(self) -> None:
        config = PRDatabaseConfig(pr_number=104, branch="feat/test")
        self.assertEqual(config.pr_number, 104)
        self.assertEqual(config.branch, "feat/test")


class TestPRDBProvisioner(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()

    def test_provision_test_mode(self) -> None:
        config = PRDatabaseConfig(pr_number=104, test_mode=True)
        provisioner = PRDatabaseProvisioner(config)
        record = provisioner.provision()
        self.assertEqual(record.state, PRDBState.PROVISIONED.value)
        self.assertEqual(record.db_type, "local_sqlite")
        self.assertTrue(record.db_path.startswith(tempfile.gettempdir()) or "pr_db_104" in record.db_path)
        self.assertNotEqual(record.db_path, "")

    def test_provision_blocked_without_token(self) -> None:
        config = PRDatabaseConfig(pr_number=104, test_mode=False)
        with patch.dict(os.environ, {"UPSTASH_API_KEY": ""}, clear=True):
            provisioner = PRDatabaseProvisioner(config)
            with self.assertRaises(RuntimeError) as ctx:
                provisioner.provision()
            self.assertIn("BLOCKED", str(ctx.exception))

    def test_provision_with_token(self) -> None:
        config = PRDatabaseConfig(pr_number=105, test_mode=False)
        with patch.dict(os.environ, {"UPSTASH_API_KEY": "test-token"}, clear=True):
            provisioner = PRDatabaseProvisioner(config)
            record = provisioner.provision()
            self.assertEqual(record.db_type, "upstash_rds")
            self.assertEqual(record.pr_number, 105)

    def test_get_status(self) -> None:
        config = PRDatabaseConfig(pr_number=104, test_mode=True)
        provisioner = PRDatabaseProvisioner(config)
        record = provisioner.provision()
        status = provisioner.get_status(record.db_id)
        self.assertIsNotNone(status)
        self.assertEqual(status["state"], PRDBState.PROVISIONED.value)
        self.assertIsInstance(status["is_expired"], bool)

    def test_get_status_not_found(self) -> None:
        config = PRDatabaseConfig(pr_number=104, test_mode=True)
        provisioner = PRDatabaseProvisioner(config)
        status = provisioner.get_status("nonexistent")
        self.assertIsNone(status)

    def test_health_check_active(self) -> None:
        config = PRDatabaseConfig(pr_number=104, test_mode=True)
        provisioner = PRDatabaseProvisioner(config)
        record = provisioner.provision()
        provisioner.activate(record.db_id)
        health = provisioner.health_check(record.db_id)
        self.assertTrue(health["healthy"])

    def test_health_check_not_found(self) -> None:
        config = PRDatabaseConfig(pr_number=104, test_mode=True)
        provisioner = PRDatabaseProvisioner(config)
        health = provisioner.health_check("nonexistent")
        self.assertFalse(health["healthy"])
        self.assertEqual(health["error"], "not_found")

    def test_activate(self) -> None:
        config = PRDatabaseConfig(pr_number=104, test_mode=True)
        provisioner = PRDatabaseProvisioner(config)
        record = provisioner.provision()
        activated = provisioner.activate(record.db_id)
        self.assertEqual(activated.state, PRDBState.ACTIVE.value)

    def test_activate_invalid_transition(self) -> None:
        config = PRDatabaseConfig(pr_number=104, test_mode=True)
        provisioner = PRDatabaseProvisioner(config)
        record = provisioner.provision()
        provisioner.activate(record.db_id)
        with self.assertRaises(ValueError):
            provisioner.activate(record.db_id)

    def test_cleanup_idempotent(self) -> None:
        config = PRDatabaseConfig(pr_number=104, test_mode=True)
        provisioner = PRDatabaseProvisioner(config)
        record = provisioner.provision()
        provisioner.activate(record.db_id)
        provisioner.cleanup(record.db_id)
        cleaned_record = provisioner.cleanup(record.db_id)
        self.assertEqual(cleaned_record.state, PRDBState.CLEANED.value)

    def test_cleanup_valid_transition(self) -> None:
        config = PRDatabaseConfig(pr_number=104, test_mode=True)
        provisioner = PRDatabaseProvisioner(config)
        record = provisioner.provision()
        provisioner.activate(record.db_id)
        cleaned = provisioner.cleanup(record.db_id)
        self.assertEqual(cleaned.state, PRDBState.CLEANED.value)

    def test_cleanup_from_active(self) -> None:
        config = PRDatabaseConfig(pr_number=104, test_mode=True)
        provisioner = PRDatabaseProvisioner(config)
        record = provisioner.provision()
        provisioner.activate(record.db_id)
        self.assertEqual(record.state, PRDBState.ACTIVE.value)
        cleaned = provisioner.cleanup(record.db_id)
        self.assertEqual(cleaned.state, PRDBState.CLEANED.value)

    def test_cleanup_from_provisioned(self) -> None:
        config = PRDatabaseConfig(pr_number=104, test_mode=True)
        provisioner = PRDatabaseProvisioner(config)
        record = provisioner.provision()
        cleaned = provisioner.cleanup(record.db_id)
        self.assertEqual(cleaned.state, PRDBState.CLEANED.value)

    def test_cleanup_not_found(self) -> None:
        config = PRDatabaseConfig(pr_number=104, test_mode=True)
        provisioner = PRDatabaseProvisioner(config)
        with self.assertRaises(ValueError):
            provisioner.cleanup("nonexistent")

    def test_list_all(self) -> None:
        config = PRDatabaseConfig(pr_number=104, test_mode=True)
        provisioner = PRDatabaseProvisioner(config)
        r1 = provisioner.provision()
        r2 = provisioner.provision()
        records = provisioner.list_all()
        self.assertEqual(len(records), 2)
        db_ids = {r["db_id"] for r in records}
        self.assertIn(r1.db_id, db_ids)
        self.assertIn(r2.db_id, db_ids)

    def test_get_manager_active(self) -> None:
        config = PRDatabaseConfig(pr_number=104, test_mode=True)
        provisioner = PRDatabaseProvisioner(config)
        record = provisioner.provision()
        provisioner.activate(record.db_id)
        mgr = provisioner.get_manager(record.db_id)
        self.assertIsInstance(mgr, type(mgr))

    def test_get_manager_not_active(self) -> None:
        config = PRDatabaseConfig(pr_number=104, test_mode=True)
        provisioner = PRDatabaseProvisioner(config)
        record = provisioner.provision()
        with self.assertRaises(ValueError):
            provisioner.get_manager(record.db_id)

    def test_isolated_dbs_different_paths(self) -> None:
        config1 = PRDatabaseConfig(pr_number=104, test_mode=True)
        config2 = PRDatabaseConfig(pr_number=105, test_mode=True)
        p1 = PRDatabaseProvisioner(config1)
        p2 = PRDatabaseProvisioner(config2)
        r1 = p1.provision()
        r2 = p2.provision()
        self.assertNotEqual(r1.db_path, r2.db_path)

    def test_evidence_contains_pr_info(self) -> None:
        config = PRDatabaseConfig(pr_number=104, branch="feat/test", test_mode=True)
        provisioner = PRDatabaseProvisioner(config)
        record = provisioner.provision()
        ev = record.evidence
        self.assertEqual(ev["pr_number"], 104)
        self.assertEqual(ev["branch"], "feat/test")
        self.assertEqual(ev["provisioned_by"], "PRDatabaseProvisioner")
        self.assertIn("provisioned_at", ev)
        self.assertIn("ttl_hours", ev)
        self.assertFalse(ev.get("cleaned_at"))

    def test_expired_detected(self) -> None:
        config = PRDatabaseConfig(pr_number=104, test_mode=True, ttl_hours=0)
        provisioner = PRDatabaseProvisioner(config)
        record = provisioner.provision()
        provisioner.activate(record.db_id)
        status = provisioner.get_status(record.db_id)
        self.assertTrue(status["is_expired"])
        self.assertEqual(status["state"], PRDBState.EXPIRED.value)


class TestPRDBLifecycle(unittest.TestCase):
    def test_valid_transitions(self) -> None:
        self.assertTrue(PRDBLifecycle.can_transition("PROVISIONED", "ACTIVE"))
        self.assertTrue(PRDBLifecycle.can_transition("PROVISIONED", "CLEANED"))
        self.assertTrue(PRDBLifecycle.can_transition("ACTIVE", "EXPIRED"))
        self.assertTrue(PRDBLifecycle.can_transition("ACTIVE", "CLEANED"))
        self.assertTrue(PRDBLifecycle.can_transition("EXPIRED", "CLEANED"))

    def test_invalid_transitions(self) -> None:
        self.assertFalse(PRDBLifecycle.can_transition("ACTIVE", "PROVISIONED"))
        self.assertFalse(PRDBLifecycle.can_transition("CLEANED", "ACTIVE"))
        self.assertFalse(PRDBLifecycle.can_transition("PROVISIONED", "EXPIRED"))

    def test_validate_transition_invalid(self) -> None:
        with self.assertRaises(ValueError):
            PRDBLifecycle.validate_transition("PROVISIONED", "EXPIRED")
        with self.assertRaises(ValueError):
            PRDBLifecycle.validate_transition("INVALID", "ACTIVE")
        with self.assertRaises(ValueError):
            PRDBLifecycle.validate_transition("ACTIVE", "INVALID")

    def test_terminal_state(self) -> None:
        self.assertTrue(PRDBLifecycle.is_terminal("CLEANED"))
        self.assertFalse(PRDBLifecycle.is_terminal("ACTIVE"))
        self.assertFalse(PRDBLifecycle.is_terminal("PROVISIONED"))
