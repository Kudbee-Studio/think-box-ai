"""Tests for enterprise-grade swarm orchestration."""

import asyncio
import unittest
from unittest.mock import AsyncMock

from thinkbox.swarm_enterprise import (
    AdaptiveRateLimiter,
    CircuitBreaker,
    CircuitState,
    EnterpriseSwarmPool,
    ExecutionMetrics,
    TaskConfig,
    TaskPriority,
)


class TestCircuitBreaker(unittest.TestCase):
    """Test circuit breaker functionality."""
    
    def test_starts_in_closed_state(self):
        """Circuit breaker should start in closed state."""
        cb = CircuitBreaker()
        self.assertEqual(cb.state, CircuitState.CLOSED)
        self.assertTrue(cb.is_available())
    
    def test_opens_after_threshold_failures(self):
        """Circuit should open after failure threshold."""
        cb = CircuitBreaker(failure_threshold=3)
        
        for _ in range(3):
            cb.record_failure()
        
        self.assertEqual(cb.state, CircuitState.OPEN)
        self.assertFalse(cb.is_available())
    
    def test_success_resets_failures(self):
        """Success should decrement failure count."""
        cb = CircuitBreaker(failure_threshold=5)
        
        cb.record_failure()
        cb.record_failure()
        self.assertEqual(cb.failure_count, 2)
        
        cb.record_success()
        self.assertEqual(cb.failure_count, 1)
    
    def test_tracks_trips(self):
        """Circuit breaker should track trip count."""
        cb = CircuitBreaker(failure_threshold=1)
        
        cb.record_failure()
        self.assertEqual(cb.trips, 1)
        
        cb.record_failure()
        self.assertEqual(cb.trips, 2)


class TestAdaptiveRateLimiter(unittest.TestCase):
    """Test adaptive rate limiting."""
    
    def test_initializes_with_target_rate(self):
        """Rate limiter should initialize with target rate."""
        limiter = AdaptiveRateLimiter(initial_rate=100)
        self.assertEqual(limiter.current_rate, 100)
        self.assertEqual(limiter.target_rate, 100)
    
    def test_decreases_rate_on_low_success(self):
        """Rate should decrease when success rate is low."""
        limiter = AdaptiveRateLimiter(initial_rate=100)
        
        for _ in range(10):
            limiter.update_rate(0.5)
        
        self.assertLess(limiter.current_rate, 100)


class TestEnterpriseSwarmPool(unittest.IsolatedAsyncioTestCase):
    """Test enterprise swarm pool."""
    
    async def test_executes_single_task(self):
        """Pool should execute a single task."""
        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(return_value="success output")
        
        pool = EnterpriseSwarmPool(model_client=mock_client, max_workers=1)
        result = await pool.execute_task("task1", "test prompt")
        
        self.assertTrue(result.success)
        self.assertEqual(result.task_id, "task1")
        mock_client.generate.assert_called_once()
    
    async def test_metrics_tracking(self):
        """Pool should track execution metrics."""
        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(return_value="output")
        
        pool = EnterpriseSwarmPool(model_client=mock_client, max_workers=1)
        
        await pool.execute_batch([("t1", "p1"), ("t2", "p2")])
        metrics = pool.metrics
        
        self.assertEqual(metrics.total_tasks, 2)
        self.assertEqual(metrics.successful_tasks, 2)
        self.assertEqual(metrics.success_rate, 1.0)
    
    async def test_health_status(self):
        """Pool should report health status."""
        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(return_value="output")
        
        pool = EnterpriseSwarmPool(model_client=mock_client, max_workers=4)
        
        health = pool.get_health_status()
        
        self.assertIn("healthy", health)
        self.assertIn("circuit_breaker", health)
        self.assertIn("success_rate", health)


class TestTaskConfig(unittest.TestCase):
    """Test task configuration."""
    
    def test_defaults(self):
        """TaskConfig should have sensible defaults."""
        config = TaskConfig()
        
        self.assertEqual(config.max_retries, 3)
        self.assertEqual(config.timeout_ms, 120000)
        self.assertEqual(config.priority, TaskPriority.NORMAL)


class TestExecutionMetrics(unittest.TestCase):
    """Test execution metrics."""
    
    def test_creates_metrics(self):
        """ExecutionMetrics should capture execution details."""
        metric = ExecutionMetrics(
            task_id="task1",
            success=True,
            latency_ms=100.5,
            tokens_used=1024,
            attempt=1,
        )
        
        self.assertEqual(metric.task_id, "task1")
        self.assertTrue(metric.success)
        self.assertEqual(metric.latency_ms, 100.5)


if __name__ == "__main__":
    unittest.main()
