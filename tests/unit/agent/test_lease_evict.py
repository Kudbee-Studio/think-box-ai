"""Tests for lease expiry → durable eviction receipt."""

import unittest
from datetime import datetime, timezone, timedelta
from thinkbox.agent.control_plane.store import ActionReceiptStore
from thinkbox.agent.control_plane.lease_evict import Lease, LeaseEvictor


class TestLeaseEvictor(unittest.TestCase):
    def setUp(self) -> None:
        self.store = ActionReceiptStore(":memory:")

    def tearDown(self) -> None:
        self.store.close()

    def test_active_lease_not_expired(self) -> None:
        future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        lease = Lease(agent_id="a1", lease_id="lease-1", expires_at=future)
        evictor = LeaseEvictor(self.store)
        evictor.register_lease(lease)
        active = evictor.active_leases()
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0].lease_id, "lease-1")

    def test_expired_lease_detected(self) -> None:
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        lease = Lease(agent_id="a2", lease_id="lease-2", expires_at=past)
        evictor = LeaseEvictor(self.store)
        evictor.register_lease(lease)
        evictions = evictor.check_expired()
        self.assertEqual(len(evictions), 1)
        self.assertEqual(evictions[0]["lease_id"], "lease-2")

    def test_expired_lease_writes_receipt(self) -> None:
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        lease = Lease(agent_id="a3", lease_id="lease-3", expires_at=past)
        evictor = LeaseEvictor(self.store)
        evictor.register_lease(lease)
        evictor.check_expired()
        self.assertEqual(self.store.count(), 1)
        self.assertTrue(self.store.verify())

    def test_active_lease_after_expiry_cleaned(self) -> None:
        future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        lease = Lease(agent_id="a4", lease_id="lease-4", expires_at=future)
        evictor = LeaseEvictor(self.store)
        evictor.register_lease(lease)
        evictions = evictor.check_expired()
        self.assertEqual(len(evictions), 0)
        active = evictor.active_leases()
        self.assertEqual(len(active), 1)

    def test_mixed_expired_and_active(self) -> None:
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        evictor = LeaseEvictor(self.store)
        evictor.register_lease(Lease(agent_id="a5", lease_id="l1", expires_at=past))
        evictor.register_lease(Lease(agent_id="a6", lease_id="l2", expires_at=future))
        evictions = evictor.check_expired()
        self.assertEqual(len(evictions), 1)
        active = evictor.active_leases()
        self.assertEqual(len(active), 1)

    def test_eviction_receipt_has_agent_id(self) -> None:
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        lease = Lease(agent_id="a7", lease_id="lease-7", expires_at=past)
        evictor = LeaseEvictor(self.store)
        evictor.register_lease(lease)
        evictor.check_expired()
        with self.store._lock:
            row = self.store._conn.execute(
                "SELECT metadata FROM receipts"
            ).fetchone()
        self.assertIsNotNone(row)
        meta = row[0] if row[0] else "{}"
        import json
        parsed = json.loads(meta) if isinstance(meta, str) else meta
        self.assertEqual(parsed["agent_id"], "a7")
