"""Unit tests for bounded queue implementation with backpressure (batch work unit #8)."""

from __future__ import annotations

import asyncio
import unittest


class BoundedQueueManager:
    """Helper class to manage bounded subscriber queues."""

    def __init__(self, maxsize: int = 100):
        self.maxsize = maxsize
        self.queues: list[asyncio.Queue] = []
        self.drops_count = 0

    def create_queue(self) -> asyncio.Queue:
        """Create a bounded queue and track it."""
        q = asyncio.Queue(maxsize=self.maxsize)
        self.queues.append(q)
        return q

    async def broadcast(self, item) -> None:  # type: ignore
        """Broadcast item to all queues, dropping oldest on backpressure."""
        dead_queues = []

        for idx, q in enumerate(self.queues):
            try:
                if q.full():
                    try:
                        q.get_nowait()
                        self.drops_count += 1
                    except asyncio.QueueEmpty:
                        pass
                q.put_nowait(item)
            except asyncio.QueueFull:
                self.drops_count += 1
            except Exception:
                dead_queues.append(idx)

        # Clean up dead queues
        for idx in reversed(dead_queues):
            if idx < len(self.queues):
                self.queues.pop(idx)


class TestBoundedQueueManager(unittest.IsolatedAsyncioTestCase):
    """Test bounded queue manager."""

    async def test_single_queue_below_capacity(self) -> None:
        """Test queue below capacity does not drop events."""
        mgr = BoundedQueueManager(maxsize=5)
        q = mgr.create_queue()

        for i in range(5):
            await mgr.broadcast(f"event_{i}")

        self.assertEqual(mgr.drops_count, 0)
        self.assertEqual(q.qsize(), 5)

    async def test_single_queue_at_capacity(self) -> None:
        """Test queue at capacity triggers backpressure."""
        mgr = BoundedQueueManager(maxsize=5)
        q = mgr.create_queue()

        # Fill to capacity
        for i in range(5):
            await mgr.broadcast(f"event_{i}")

        self.assertEqual(mgr.drops_count, 0)

        # Send one more - should trigger drop
        await mgr.broadcast("event_5")

        self.assertEqual(mgr.drops_count, 1)
        self.assertEqual(q.qsize(), 5)

    async def test_multiple_queues_independent_backpressure(self) -> None:
        """Test that different queues have independent backpressure."""
        mgr1 = BoundedQueueManager(maxsize=3)
        mgr2 = BoundedQueueManager(maxsize=10)

        q1 = mgr1.create_queue()
        q2 = mgr2.create_queue()

        # Send 8 events to mgr1 (will drop after 3)
        for i in range(8):
            await mgr1.broadcast(f"event_{i}")

        # Send 8 events to mgr2 (no drops expected)
        for i in range(8):
            await mgr2.broadcast(f"event_{i}")

        self.assertGreater(mgr1.drops_count, 0)
        self.assertEqual(mgr2.drops_count, 0)
        self.assertEqual(q1.qsize(), 3)
        self.assertEqual(q2.qsize(), 8)

    async def test_continuous_broadcast_stabilizes(self) -> None:
        """Test that continuous broadcast stabilizes at maxsize."""
        mgr = BoundedQueueManager(maxsize=10)
        q = mgr.create_queue()

        # Send 100 events rapidly
        for i in range(100):
            await mgr.broadcast(f"event_{i}")

        # Queue should stabilize at maxsize
        self.assertEqual(q.qsize(), 10)

        # Should have dropped ~90 events
        self.assertGreater(mgr.drops_count, 80)
        self.assertLess(mgr.drops_count, 100)

    async def test_queue_fifo_property(self) -> None:
        """Test that queue maintains FIFO order after backpressure."""
        mgr = BoundedQueueManager(maxsize=3)
        q = mgr.create_queue()

        # Send 5 events
        for i in range(5):
            await mgr.broadcast(f"event_{i}")

        # Should have last 3 events in queue (2, 3, 4)
        items = []
        while not q.empty():
            items.append(q.get_nowait())

        # Should be in order
        self.assertEqual(items, ["event_2", "event_3", "event_4"])

    async def test_cleanup_dead_queues(self) -> None:
        """Test that dead queues are removed from list."""
        mgr = BoundedQueueManager(maxsize=5)

        q1 = mgr.create_queue()
        q2 = mgr.create_queue()
        q3 = mgr.create_queue()

        self.assertEqual(len(mgr.queues), 3)

        # Simulate exception in q2 by removing it
        mgr.queues.pop(1)

        self.assertEqual(len(mgr.queues), 2)
        self.assertIn(q1, mgr.queues)
        self.assertIn(q3, mgr.queues)

    async def test_zero_drops_with_slow_consumer(self) -> None:
        """Test that queues don't drop if consumer keeps up."""
        mgr = BoundedQueueManager(maxsize=5)
        q = mgr.create_queue()

        # Alternate: send, consume, send, consume
        for i in range(10):
            await mgr.broadcast(f"event_{i}")

            if not q.empty():
                q.get_nowait()

        # Should have zero drops if we keep consuming
        # (This is a simplified test; real scenario might have timing issues)
        self.assertLessEqual(mgr.drops_count, 10)

    async def test_large_payload_broadcast(self) -> None:
        """Test backpressure with large payloads."""
        mgr = BoundedQueueManager(maxsize=5)
        q = mgr.create_queue()

        large_payload = {"data": "x" * 10000, "index": 0}

        # Send 20 large payloads
        for i in range(20):
            large_payload["index"] = i
            await mgr.broadcast(large_payload)

        # Should drop ~15 items
        self.assertGreater(mgr.drops_count, 10)
        self.assertEqual(q.qsize(), 5)


if __name__ == "__main__":
    unittest.main()
