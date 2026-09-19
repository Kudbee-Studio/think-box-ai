"""Unit tests for thinkbox/mesh/coordinator — Mesh compromise detection and expulsion."""

import unittest

from thinkbox.mesh.coordinator import (
    CompromiseEvent,
    CompromiseSignal,
    DetectionRule,
    ExpulsionRecord,
    MeshCoordinator,
)
from thinkbox.occupancy import MeshCellManager


class TestCompromiseSignalEnum(unittest.TestCase):
    def test_signal_values(self):
        self.assertEqual(CompromiseSignal.ANOMALOUS_CAPABILITY.value, "anomalous_capability")
        self.assertEqual(CompromiseSignal.UNAUTHORIZED_MEMBER.value, "unauthorized_member")
        self.assertEqual(CompromiseSignal.EXPIRED_CREDENTIAL.value, "expired_credential")
        self.assertEqual(CompromiseSignal.SUSPICIOUS_TRAFFIC.value, "suspicious_traffic")
        self.assertEqual(CompromiseSignal.DUPLICATED_TOKEN.value, "duplicated_token")
        self.assertEqual(CompromiseSignal.OFF_POLICY_ACTION.value, "off_policy_action")


class TestCompromiseEvent(unittest.TestCase):
    def test_creation(self):
        event = CompromiseEvent(
            event_id="evt_1",
            cell_id="cell_1",
            signal=CompromiseSignal.ANOMALOUS_CAPABILITY,
            severity=0.8,
            details={"key": "value"},
        )
        self.assertEqual(event.cell_id, "cell_1")
        self.assertEqual(event.signal, CompromiseSignal.ANOMALOUS_CAPABILITY)
        self.assertEqual(event.severity, 0.8)
        self.assertFalse(event.resolved)
        self.assertGreater(event.detected_at, 0)


class TestDetectionRule(unittest.TestCase):
    def test_creation(self):
        rule = DetectionRule(
            rule_id="rule_1",
            signal_type=CompromiseSignal.ANOMALOUS_CAPABILITY,
            threshold=0.7,
            check=lambda x: True,
            description="Test rule",
        )
        self.assertEqual(rule.rule_id, "rule_1")
        self.assertEqual(rule.threshold, 0.7)


class TestMeshCoordinator(unittest.TestCase):
    def setUp(self):
        self.mesh = MeshCellManager()
        self.coordinator = MeshCoordinator(self.mesh, severity_threshold=0.7)

    def test_detect_below_threshold(self):
        cell = self.mesh.create("test", "owner", capabilities=["file:read"])
        events = self.coordinator.detect(
            cell.cell_id,
            {CompromiseSignal.SUSPICIOUS_TRAFFIC: 0.5},
            {"detail": "low"},
        )
        self.assertEqual(len(events), 0)
        self.assertEqual(self.coordinator.get_expelled_count(), 0)

    def test_detect_above_threshold(self):
        cell = self.mesh.create("test", "owner", capabilities=["file:read"])
        self.mesh.admit(cell.cell_id, "agent_1")
        events = self.coordinator.detect(
            cell.cell_id,
            {CompromiseSignal.ANOMALOUS_CAPABILITY: 0.9},
            {"detail": "high"},
        )
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].severity, 0.9)
        self.assertTrue(self.coordinator.check_expelled(cell.cell_id))

    def test_detect_multiple_signals(self):
        cell = self.mesh.create("test", "owner")
        events = self.coordinator.detect(
            cell.cell_id,
            {
                CompromiseSignal.SUSPICIOUS_TRAFFIC: 0.8,
                CompromiseSignal.DUPLICATED_TOKEN: 0.85,
            },
        )
        self.assertEqual(len(events), 2)
        self.assertTrue(self.coordinator.check_expelled(cell.cell_id))

    def test_expel_manual(self):
        cell = self.mesh.create("test", "owner")
        record = self.coordinator.expel_cell(cell.cell_id, reason="manual test")
        self.assertIsNotNone(record)
        self.assertEqual(record.cell_id, cell.cell_id)
        self.assertTrue(self.coordinator.check_expelled(cell.cell_id))
        self.assertEqual(self.coordinator.get_compromised_count(), 1)

    def test_expel_already_expelled(self):
        cell = self.mesh.create("test", "owner")
        self.coordinator.expel_cell(cell.cell_id, reason="first")
        record = self.coordinator.expel_cell(cell.cell_id, reason="second")
        self.assertIsNone(record)
        self.assertEqual(self.coordinator.get_compromised_count(), 1)

    def test_expel_unknown_cell(self):
        record = self.coordinator.expel_cell("nonexistent", reason="test")
        self.assertIsNone(record)

    def test_check_expelled(self):
        cell = self.mesh.create("test", "owner")
        self.assertFalse(self.coordinator.check_expelled(cell.cell_id))
        self.coordinator.expel_cell(cell.cell_id, reason="test")
        self.assertTrue(self.coordinator.check_expelled(cell.cell_id))

    def test_get_events(self):
        cell = self.mesh.create("test", "owner")
        self.coordinator.detect(
            cell.cell_id,
            {CompromiseSignal.ANOMALOUS_CAPABILITY: 0.9},
        )
        events = self.coordinator.get_events(cell_id=cell.cell_id)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["cell_id"], cell.cell_id)

    def test_get_events_resolved_filter(self):
        cell = self.mesh.create("test", "owner")
        self.coordinator.detect(
            cell.cell_id,
            {CompromiseSignal.ANOMALOUS_CAPABILITY: 0.9},
        )
        events = self.coordinator.get_events(resolved=False)
        self.assertEqual(len(events), 1)

    def test_get_events_no_filter(self):
        cell = self.mesh.create("test", "owner")
        self.coordinator.detect(
            cell.cell_id,
            {CompromiseSignal.ANOMALOUS_CAPABILITY: 0.9},
        )
        events = self.coordinator.get_events()
        self.assertEqual(len(events), 1)

    def test_get_expulsions(self):
        cell = self.mesh.create("test", "owner")
        self.coordinator.expel_cell(cell.cell_id, reason="test expulsion")
        expulsions = self.coordinator.get_expulsions()
        self.assertEqual(len(expulsions), 1)
        self.assertEqual(expulsions[0]["reason"], "test expulsion")
        self.assertEqual(expulsions[0]["cell_id"], cell.cell_id)

    def test_add_rule(self):
        rule = DetectionRule(
            rule_id="rule_1",
            signal_type=CompromiseSignal.SUSPICIOUS_TRAFFIC,
            threshold=0.5,
            check=lambda x: True,
            description="Test",
        )
        self.coordinator.add_rule(rule)
        rules = self.coordinator._rules
        self.assertEqual(len(rules), 1)
        self.assertEqual(rules[0].rule_id, "rule_1")

    def test_severity_threshold_property(self):
        self.assertEqual(self.coordinator.severity_threshold, 0.7)

    def test_mesh_property(self):
        self.assertIs(self.coordinator.mesh, self.mesh)

    def test_compromised_count(self):
        self.assertEqual(self.coordinator.get_compromised_count(), 0)
        cell1 = self.mesh.create("c1", "o1")
        cell2 = self.mesh.create("c2", "o2")
        self.coordinator.expel_cell(cell1.cell_id, reason="c1")
        self.coordinator.detect(cell2.cell_id, {CompromiseSignal.ANOMALOUS_CAPABILITY: 0.9})
        self.assertEqual(self.coordinator.get_compromised_count(), 2)

    def test_expelled_count(self):
        self.assertEqual(self.coordinator.get_expelled_count(), 0)
        cell = self.mesh.create("test", "owner")
        self.coordinator.expel_cell(cell.cell_id, reason="test")
        self.assertEqual(self.coordinator.get_expelled_count(), 1)

    def test_expulsion_members_affected(self):
        cell = self.mesh.create("test", "owner", capabilities=["file:read"])
        self.mesh.admit(cell.cell_id, "agent_1")
        self.mesh.admit(cell.cell_id, "agent_2")
        self.mesh.admit(cell.cell_id, "agent_3")
        record = self.coordinator.expel_cell(cell.cell_id, reason="expulsion")
        self.assertEqual(record.members_affected, 3)

    def test_detect_no_members(self):
        cell = self.mesh.create("test", "owner")
        self.coordinator.detect(
            cell.cell_id,
            {CompromiseSignal.ANOMALOUS_CAPABILITY: 0.9},
        )
        expulsions = self.coordinator.get_expulsions()
        self.assertEqual(expulsions[0]["members_affected"], 0)

    def test_register_detected_events(self):
        cell = self.mesh.create("test", "owner")
        self.coordinator.detect(
            cell.cell_id,
            {CompromiseSignal.ANOMALOUS_CAPABILITY: 0.9},
        )
        events = self.coordinator.register_detected_events(cell.cell_id)
        self.assertEqual(len(events), 1)

    def test_register_detected_events_other_cell(self):
        cell1 = self.mesh.create("c1", "o1")
        cell2 = self.mesh.create("c2", "o2")
        self.coordinator.detect(cell1.cell_id, {CompromiseSignal.ANOMALOUS_CAPABILITY: 0.9})
        events = self.coordinator.register_detected_events(cell2.cell_id)
        self.assertEqual(len(events), 0)

    def test_detect_does_not_expel_below_threshold(self):
        cell = self.mesh.create("test", "owner")
        self.coordinator.detect(
            cell.cell_id,
            {CompromiseSignal.SUSPICIOUS_TRAFFIC: 0.3},
        )
        self.assertFalse(self.coordinator.check_expelled(cell.cell_id))

    def test_fully_signed_token_validation_flow(self):
        from thinkbox.governance.distributed.token import (
            ThresholdGovernanceTokenService,
            ThresholdTokenRequest,
        )

        svc = ThresholdGovernanceTokenService(
            signing_key="test",
            validator_ids=["v1", "v2"],
            threshold=2,
        )
        req = ThresholdTokenRequest(
            agent_id="agent_1",
            capabilities=["file:read"],
            threshold=2,
            validator_ids=["v1", "v2"],
        )
        token = svc.issue(req)
        svc.sign(token.token_value, "v1")
        self.assertFalse(svc.verify(token.token_value))
        svc.sign(token.token_value, "v2")
        verified = svc.verify(token.token_value)
        self.assertIsNotNone(verified)
        self.assertTrue(verified.valid)
