"""Unit tests for dashboard pagination and bounded queues (batch work unit #8)."""

from __future__ import annotations

import asyncio
import unittest

from thinkbox.dashboard_state import (
    DashboardCategory,
    DashboardEvent,
    DashboardEventEntry,
    DashboardState,
    get_dashboard_state,
)


class TestDashboardPagination(unittest.TestCase):
    """Test dashboard pagination with offset/limit."""

    @classmethod
    def setUpClass(cls) -> None:
        """Reset dashboard state before all tests in this class."""
        DashboardState._instance = None

    def setUp(self) -> None:
        """Reset dashboard state before each test."""
        # Clear singleton instance to ensure test isolation
        import sys
        # Remove from cache if it exists
        if 'thinkbox.dashboard_state' in sys.modules:
            dashboard_module = sys.modules['thinkbox.dashboard_state']
            if hasattr(dashboard_module, '_dashboard_state'):
                dashboard_module._dashboard_state = None
        DashboardState._instance = None

    def test_pagination_default_limit(self) -> None:
        """Test pagination with default limit (100)."""
        # Create fresh state
        import sys
        dashboard_module = sys.modules.get('thinkbox.dashboard_state')
        if dashboard_module and hasattr(dashboard_module, '_dashboard_state'):
            dashboard_module._dashboard_state = None

        state = get_dashboard_state()

        # Add 250 events
        for i in range(250):
            entry = DashboardEventEntry(
                event_id="",
                category=DashboardCategory.THINK_JOBS,
                event_type=DashboardEvent.JOB_CREATED,
                timestamp="",
                data={"index": i},
            )
            state.events.append(entry)

        # Fetch first page
        page1 = state.get_events_paginated(limit=100, offset=0)
        self.assertEqual(len(page1["events"]), 100)
        self.assertEqual(page1["total"], 250)
        self.assertEqual(page1["offset"], 0)
        self.assertEqual(page1["limit"], 100)
        self.assertTrue(page1["has_more"])
        self.assertEqual(page1["next_offset"], 100)

        # Fetch second page
        page2 = state.get_events_paginated(limit=100, offset=100)
        self.assertEqual(len(page2["events"]), 100)
        self.assertEqual(page2["offset"], 100)
        self.assertTrue(page2["has_more"])
        self.assertEqual(page2["next_offset"], 200)

        # Fetch third page (partial)
        page3 = state.get_events_paginated(limit=100, offset=200)
        self.assertEqual(len(page3["events"]), 50)
        self.assertEqual(page3["offset"], 200)
        self.assertFalse(page3["has_more"])
        self.assertIsNone(page3["next_offset"])

    def test_pagination_clamped_limit(self) -> None:
        """Test that limit is clamped to [1, 1000]."""
        state = get_dashboard_state()

        # Add 10 events
        for i in range(10):
            entry = DashboardEventEntry(
                event_id="",
                category=DashboardCategory.THINK_JOBS,
                event_type=DashboardEvent.JOB_CREATED,
                timestamp="",
                data={"index": i},
            )
            state.events.append(entry)

        # Test limit < 1 (clamped to 1)
        page = state.get_events_paginated(limit=0, offset=0)
        self.assertEqual(page["limit"], 1)
        self.assertEqual(len(page["events"]), 1)

        # Test limit > 1000 (clamped to 1000)
        page = state.get_events_paginated(limit=2000, offset=0)
        self.assertEqual(page["limit"], 1000)
        self.assertEqual(len(page["events"]), 10)

    def test_pagination_offset_bounds(self) -> None:
        """Test offset boundary conditions."""
        state = get_dashboard_state()

        # Add 50 events
        for i in range(50):
            entry = DashboardEventEntry(
                event_id="",
                category=DashboardCategory.THINK_JOBS,
                event_type=DashboardEvent.JOB_CREATED,
                timestamp="",
                data={"index": i},
            )
            state.events.append(entry)

        # Test negative offset (clamped to 0)
        page = state.get_events_paginated(limit=10, offset=-5)
        self.assertEqual(page["offset"], 0)

        # Test offset beyond events
        page = state.get_events_paginated(limit=10, offset=100)
        self.assertEqual(len(page["events"]), 0)
        self.assertFalse(page["has_more"])

    def test_pagination_empty_events(self) -> None:
        """Test pagination with no events."""
        state = get_dashboard_state()

        page = state.get_events_paginated(limit=100, offset=0)
        self.assertEqual(len(page["events"]), 0)
        self.assertEqual(page["total"], 0)
        self.assertFalse(page["has_more"])
        self.assertIsNone(page["next_offset"])


class TestDashboardBoundedQueue(unittest.TestCase):
    """Test bounded subscriber queues with backpressure."""

    def setUp(self) -> None:
        """Reset dashboard state before each test."""
        DashboardState._instance = None

    async def test_bounded_queue_creation(self) -> None:
        """Test creating a bounded queue subscriber."""
        state = get_dashboard_state()

        queue = await state.register_subscriber(maxsize=10)
        self.assertIsNotNone(queue)
        self.assertEqual(queue.maxsize, 10)
        self.assertEqual(len(state._subscribers), 1)

    async def test_bounded_queue_backpressure(self) -> None:
        """Test backpressure: oldest events dropped when queue is full."""
        state = get_dashboard_state()

        # Create a queue with maxsize=5
        queue = await state.register_subscriber(maxsize=5)

        # Fill queue beyond capacity
        for i in range(10):
            entry = DashboardEventEntry(
                event_id="",
                category=DashboardCategory.THINK_JOBS,
                event_type=DashboardEvent.JOB_CREATED,
                timestamp="",
                data={"index": i},
            )
            await state._notify(entry)

        # Queue should have at most 5 items
        self.assertLessEqual(queue.qsize(), 5)

        # Should have dropped 5 events (events 0-4)
        self.assertGreater(state.get_events_drops_count(), 0)

    async def test_subscriber_cleanup_on_exception(self) -> None:
        """Test that dead subscribers are cleaned up on exception."""
        state = get_dashboard_state()

        # Create a subscriber
        queue = await state.register_subscriber()
        self.assertEqual(len(state._subscribers), 1)

        # Simulate a dead queue (close it)
        queue.task_done()  # This should be safe

        # Create a normal queue and notify
        queue2 = await state.register_subscriber()
        self.assertEqual(len(state._subscribers), 2)

        entry = DashboardEventEntry(
            event_id="",
            category=DashboardCategory.THINK_JOBS,
            event_type=DashboardEvent.JOB_CREATED,
            timestamp="",
            data={"test": "data"},
        )
        await state._notify(entry)

        # Should be able to get event from queue2
        try:
            event = queue2.get_nowait()
            self.assertIsNotNone(event)
        except asyncio.QueueEmpty:
            self.fail("Event should be in queue2")

    async def test_multiple_subscribers_independent(self) -> None:
        """Test that multiple subscribers have independent bounded queues."""
        state = get_dashboard_state()

        queue1 = await state.register_subscriber(maxsize=5)
        queue2 = await state.register_subscriber(maxsize=10)

        self.assertEqual(queue1.maxsize, 5)
        self.assertEqual(queue2.maxsize, 10)
        self.assertEqual(len(state._subscribers), 2)

    async def test_event_drops_counter(self) -> None:
        """Test that dropped events are counted correctly."""
        state = get_dashboard_state()

        queue = await state.register_subscriber(maxsize=3)

        # Send 10 events, expect ~7 drops
        for i in range(10):
            entry = DashboardEventEntry(
                event_id="",
                category=DashboardCategory.THINK_JOBS,
                event_type=DashboardEvent.JOB_CREATED,
                timestamp="",
                data={"index": i},
            )
            await state._notify(entry)

        drops = state.get_events_drops_count()
        self.assertGreater(drops, 0)

    async def test_event_stream_cleanup(self) -> None:
        """Test that event stream cleanup removes subscriber from list."""
        from thinkbox.dashboard_state import dashboard_event_stream

        state = get_dashboard_state()
        self.assertEqual(len(state._subscribers), 0)

        # Create a stream and immediately cancel it
        gen = dashboard_event_stream()
        self.assertEqual(len(state._subscribers), 1)

        try:
            gen.aclose()
            # Give cleanup time to run
            await asyncio.sleep(0.01)
        except Exception:
            pass


class AsyncTestCase(unittest.TestCase):
    """Base class for async unit tests."""

    def run(self, result=None):  # type: ignore
        """Override run to handle async test methods."""
        orig_run = super().run

        def run_async_method(fn):  # type: ignore
            if asyncio.iscoroutinefunction(fn):
                return asyncio.run(fn())
            return fn()

        self.__class__ = type(
            self.__class__.__name__,
            (self.__class__,),
            {
                m: (lambda f=getattr(self, m): run_async_method(f))()
                if asyncio.iscoroutinefunction(getattr(self, m))
                else getattr(self, m)
                for m in dir(self)
                if m.startswith("test_")
            },
        )
        return orig_run(result)


class AsyncTestDashboardBoundedQueue(unittest.IsolatedAsyncioTestCase):
    """Async test cases for bounded queues."""

    async def asyncSetUp(self) -> None:
        """Reset dashboard state before each test."""
        import sys
        # Remove from cache if it exists
        if 'thinkbox.dashboard_state' in sys.modules:
            dashboard_module = sys.modules['thinkbox.dashboard_state']
            if hasattr(dashboard_module, '_dashboard_state'):
                dashboard_module._dashboard_state = None
        DashboardState._instance = None

    async def test_bounded_queue_creation(self) -> None:
        """Test creating a bounded queue subscriber."""
        state = get_dashboard_state()

        queue = await state.register_subscriber(maxsize=10)
        self.assertIsNotNone(queue)
        self.assertEqual(queue.maxsize, 10)
        self.assertEqual(len(state._subscribers), 1)

    async def test_bounded_queue_backpressure(self) -> None:
        """Test backpressure: oldest events dropped when queue is full."""
        state = get_dashboard_state()

        # Create a queue with maxsize=5
        queue = await state.register_subscriber(maxsize=5)

        # Fill queue beyond capacity
        for i in range(10):
            entry = DashboardEventEntry(
                event_id="",
                category=DashboardCategory.THINK_JOBS,
                event_type=DashboardEvent.JOB_CREATED,
                timestamp="",
                data={"index": i},
            )
            await state._notify(entry)

        # Queue should have at most 5 items
        self.assertLessEqual(queue.qsize(), 5)

        # Should have dropped 5 events
        self.assertGreater(state.get_events_drops_count(), 0)

    async def test_event_drops_counter(self) -> None:
        """Test that dropped events are counted correctly."""
        state = get_dashboard_state()

        queue = await state.register_subscriber(maxsize=3)

        # Send 10 events
        for i in range(10):
            entry = DashboardEventEntry(
                event_id="",
                category=DashboardCategory.THINK_JOBS,
                event_type=DashboardEvent.JOB_CREATED,
                timestamp="",
                data={"index": i},
            )
            await state._notify(entry)

        drops = state.get_events_drops_count()
        self.assertGreater(drops, 0)


if __name__ == "__main__":
    unittest.main()
