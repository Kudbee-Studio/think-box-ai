"""Integration tests for Box pool functionality.

Tests round-robin allocation, circuit breaker, health checking, and persistence.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from thinkbox.substrate import (
    BoxPool,
    BoxPoolError,
    BoxHealthChecker,
    BoxHealthStatus,
    BoxEndpoint,
)
from thinkbox.box_assignment_store import BoxAssignmentStore


class TestBoxEndpoint(unittest.TestCase):
    """Tests for BoxEndpoint dataclass."""
    
    def test_box_endpoint_creation(self) -> None:
        endpoint = BoxEndpoint(url="http://box1.example.com:8000")
        self.assertEqual(endpoint.url, "http://box1.example.com:8000")
        self.assertEqual(endpoint.name, "box1.example.com")
        self.assertEqual(endpoint.status, BoxHealthStatus.HEALTHY)
        self.assertEqual(endpoint.consecutive_failures, 0)
    
    def test_box_endpoint_to_dict(self) -> None:
        endpoint = BoxEndpoint(url="http://box1.example.com:8000", name="box-1")
        endpoint.total_requests = 100
        endpoint.successful_requests = 95
        data = endpoint.to_dict()
        self.assertEqual(data["url"], "http://box1.example.com:8000")
        self.assertEqual(data["name"], "box-1")
        self.assertAlmostEqual(data["success_rate"], 0.95)
    
    def test_box_endpoint_hostname_extraction(self) -> None:
        cases = [
            ("http://localhost:8000", "localhost"),
            ("https://box.example.com:443", "box.example.com"),
            ("http://192.168.1.100:8000", "192.168.1.100"),
            ("invalid-url", "invalid-url"),
        ]
        for url, expected_host in cases:
            endpoint = BoxEndpoint(url=url)
            self.assertEqual(endpoint.name, expected_host)


class TestBoxHealthChecker(unittest.TestCase):
    """Tests for BoxHealthChecker."""
    
    def setUp(self) -> None:
        self.checker = BoxHealthChecker()
    
    def test_register_endpoint(self) -> None:
        self.checker.register("http://box1.example.com:8000", name="box-1")
        endpoints = self.checker.all_endpoints()
        self.assertEqual(len(endpoints), 1)
        self.assertEqual(endpoints[0].url, "http://box1.example.com:8000")
    
    def test_record_success_resets_failures(self) -> None:
        self.checker.register("http://box1.example.com:8000")
        endpoint = self.checker.get_endpoint("http://box1.example.com:8000")
        
        # Simulate some failures
        endpoint.consecutive_failures = 2
        endpoint.status = BoxHealthStatus.DEGRADED
        
        # Record success should reset failures
        self.checker.record_success("http://box1.example.com:8000")
        endpoint = self.checker.get_endpoint("http://box1.example.com:8000")
        self.assertEqual(endpoint.consecutive_failures, 0)
        self.assertEqual(endpoint.total_requests, 1)
        self.assertEqual(endpoint.successful_requests, 1)
    
    def test_record_failure_increments_counter(self) -> None:
        self.checker.register("http://box1.example.com:8000")
        
        self.checker.record_failure("http://box1.example.com:8000")
        endpoint = self.checker.get_endpoint("http://box1.example.com:8000")
        self.assertEqual(endpoint.consecutive_failures, 1)
        self.assertEqual(endpoint.total_requests, 1)
        self.assertEqual(endpoint.successful_requests, 0)
    
    def test_healthy_endpoints_filtering(self) -> None:
        self.checker.register("http://box1.example.com:8000")
        self.checker.register("http://box2.example.com:8000")
        self.checker.register("http://box3.example.com:8000")
        
        # Mark one as degraded
        ep2 = self.checker.get_endpoint("http://box2.example.com:8000")
        ep2.status = BoxHealthStatus.DEGRADED
        
        # Mark one as unhealthy
        ep3 = self.checker.get_endpoint("http://box3.example.com:8000")
        ep3.status = BoxHealthStatus.UNHEALTHY
        
        healthy = self.checker.healthy_endpoints()
        self.assertEqual(len(healthy), 1)
        self.assertEqual(healthy[0].url, "http://box1.example.com:8000")
        
        available = self.checker.available_endpoints()
        self.assertEqual(len(available), 2)


class TestBoxPool(unittest.TestCase):
    """Tests for BoxPool."""
    
    def setUp(self) -> None:
        self.pool = BoxPool(box_urls=[
            "http://box1.example.com:8000",
            "http://box2.example.com:8000",
            "http://box3.example.com:8000",
        ])
    
    def test_pool_initialization(self) -> None:
        endpoints = self.pool.enumerate_boxes()
        self.assertEqual(len(endpoints), 3)
    
    def test_round_robin_allocation(self) -> None:
        # Allocate agents in sequence
        agents = [f"agent-{i}" for i in range(9)]
        assignments = {}
        for agent_id in agents:
            box_url = self.pool.allocate(agent_id)
            assignments[agent_id] = box_url
        
        # Should distribute across 3 boxes
        box_counts = {}
        for box_url in assignments.values():
            box_counts[box_url] = box_counts.get(box_url, 0) + 1
        
        self.assertEqual(len(box_counts), 3)
        # 9 agents / 3 boxes = 3 per box
        for count in box_counts.values():
            self.assertEqual(count, 3)
    
    def test_allocation_persistence(self) -> None:
        agent_id = "test-agent"
        box_url = self.pool.allocate(agent_id)
        
        # Should return same assignment
        assignment = self.pool.get_assignment(agent_id)
        self.assertEqual(assignment, box_url)
    
    def test_allocation_release(self) -> None:
        agent_id = "test-agent"
        self.pool.allocate(agent_id)
        
        self.assertIsNotNone(self.pool.get_assignment(agent_id))
        
        self.pool.release(agent_id)
        self.assertIsNone(self.pool.get_assignment(agent_id))
    
    def test_pool_status(self) -> None:
        self.pool.allocate("agent-1")
        self.pool.allocate("agent-2")
        
        status = self.pool.get_status()
        self.assertEqual(status["total_endpoints"], 3)
        self.assertEqual(status["active_allocations"], 2)
    
    def test_failover_on_unhealthy_box(self) -> None:
        # Mark first box as unhealthy
        ep1 = self.pool._health_checker.get_endpoint("http://box1.example.com:8000")
        ep1.status = BoxHealthStatus.UNHEALTHY
        
        # Allocate should skip unhealthy box
        allocations = set()
        for i in range(6):
            agent_id = f"agent-{i}"
            box_url = self.pool.allocate(agent_id)
            allocations.add(box_url)
        
        # Should only use healthy boxes 2 and 3
        self.assertNotIn("http://box1.example.com:8000", allocations)
        self.assertEqual(len(allocations), 2)
    
    def test_record_success_and_failure(self) -> None:
        agent_id = "test-agent"
        self.pool.allocate(agent_id)
        
        self.pool.record_success(agent_id)
        endpoint = self.pool._health_checker.get_endpoint(
            self.pool.get_assignment(agent_id)
        )
        self.assertEqual(endpoint.successful_requests, 1)
        
        self.pool.record_failure(agent_id)
        self.assertEqual(endpoint.total_requests, 2)
        self.assertEqual(endpoint.consecutive_failures, 1)


class TestBoxAssignmentStore(unittest.TestCase):
    """Tests for BoxAssignmentStore."""
    
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store_path = Path(self.temp_dir.name) / "assignments.json"
        self.store = BoxAssignmentStore(str(self.store_path))
    
    def tearDown(self) -> None:
        self.temp_dir.cleanup()
    
    def test_set_and_get_assignment(self) -> None:
        self.store.set_assignment("agent-1", "http://box1.example.com:8000")
        
        assignment = self.store.get_assignment("agent-1")
        self.assertEqual(assignment, "http://box1.example.com:8000")
    
    def test_persistence(self) -> None:
        self.store.set_assignment("agent-1", "http://box1.example.com:8000")
        self.store.set_assignment("agent-2", "http://box2.example.com:8000")
        
        # Create new store instance (should load from disk)
        store2 = BoxAssignmentStore(str(self.store_path))
        self.assertEqual(store2.get_assignment("agent-1"), "http://box1.example.com:8000")
        self.assertEqual(store2.get_assignment("agent-2"), "http://box2.example.com:8000")
    
    def test_remove_assignment(self) -> None:
        self.store.set_assignment("agent-1", "http://box1.example.com:8000")
        
        self.assertIsNotNone(self.store.get_assignment("agent-1"))
        
        self.store.remove_assignment("agent-1")
        self.assertIsNone(self.store.get_assignment("agent-1"))
    
    def test_clear_all(self) -> None:
        self.store.set_assignment("agent-1", "http://box1.example.com:8000")
        self.store.set_assignment("agent-2", "http://box2.example.com:8000")
        
        self.store.clear_all()
        
        assignments = self.store.get_all_assignments()
        self.assertEqual(len(assignments), 0)
    
    def test_get_all_assignments(self) -> None:
        self.store.set_assignment("agent-1", "http://box1.example.com:8000")
        self.store.set_assignment("agent-2", "http://box2.example.com:8000")
        
        assignments = self.store.get_all_assignments()
        self.assertEqual(len(assignments), 2)
        self.assertEqual(assignments["agent-1"], "http://box1.example.com:8000")
        self.assertEqual(assignments["agent-2"], "http://box2.example.com:8000")
    
    def test_store_status(self) -> None:
        self.store.set_assignment("agent-1", "http://box1.example.com:8000")
        
        status = self.store.get_status()
        self.assertEqual(status["assignment_count"], 1)
        self.assertIn("agent-1", status["assignments"])


class TestBoxPoolIntegration(unittest.TestCase):
    """Integration tests for Box pool with concurrent allocations."""
    
    def test_concurrent_allocations(self) -> None:
        """Test concurrent allocation from multiple threads."""
        import threading
        
        pool = BoxPool(box_urls=[
            "http://box1.example.com:8000",
            "http://box2.example.com:8000",
        ])
        
        results = []
        lock = threading.Lock()
        
        def allocate_agent(agent_id: str) -> None:
            box_url = pool.allocate(agent_id)
            with lock:
                results.append((agent_id, box_url))
        
        # Create 10 concurrent allocation threads
        threads = []
        for i in range(10):
            thread = threading.Thread(target=allocate_agent, args=(f"agent-{i}",))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Verify all agents were allocated
        self.assertEqual(len(results), 10)
        
        # Verify assignments are distributed across boxes
        box_counts = {}
        for _, box_url in results:
            box_counts[box_url] = box_counts.get(box_url, 0) + 1
        
        # Should be distributed across 2 boxes
        self.assertEqual(len(box_counts), 2)
    
    def test_circuit_breaker_in_action(self) -> None:
        """Test circuit breaker preventing continued failures."""
        pool = BoxPool(box_urls=[
            "http://box1.example.com:8000",
            "http://box2.example.com:8000",
        ])
        
        # Simulate consecutive failures on box1
        box1_url = "http://box1.example.com:8000"
        
        # Record 3 consecutive failures (circuit breaker threshold)
        for _ in range(3):
            pool._health_checker.record_failure(box1_url)
        
        # Box1 should now be unhealthy
        endpoint = pool._health_checker.get_endpoint(box1_url)
        self.assertEqual(endpoint.status, BoxHealthStatus.UNHEALTHY)
        
        # Future allocations should avoid box1
        allocations = set()
        for i in range(4):
            agent_id = f"agent-{i}"
            box_url = pool.allocate(agent_id)
            allocations.add(box_url)
        
        # Should not use box1
        self.assertNotIn(box1_url, allocations)


if __name__ == "__main__":
    unittest.main()
