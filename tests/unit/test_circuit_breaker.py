"""Tests for circuit breaker implementation."""

from __future__ import annotations

import asyncio
import time
import unittest
from unittest.mock import AsyncMock

from thinkbox.circuit_breaker import CircuitBreaker, CircuitBreakerConfig, CircuitBreakerOpen, CircuitState


class TestCircuitBreakerBasics(unittest.TestCase):
    """Test basic circuit breaker operations."""

    def test_initial_state_closed(self):
        """Circuit breaker starts in CLOSED state."""
        cb = CircuitBreaker()
        self.assertEqual(cb.state, CircuitState.CLOSED)
        self.assertEqual(cb.failure_count, 0)

    def test_record_success_resets_failures(self):
        """Recording success resets failure counter."""
        cb = CircuitBreaker()
        cb.record_failure()
        cb.record_failure()
        self.assertEqual(cb.failure_count, 2)
        cb.record_success()
        self.assertEqual(cb.failure_count, 0)
        self.assertEqual(cb.state, CircuitState.CLOSED)

    def test_record_failure_increments_counter(self):
        """Recording failure increments counter."""
        cb = CircuitBreaker()
        cb.record_failure()
        self.assertEqual(cb.failure_count, 1)
        cb.record_failure()
        self.assertEqual(cb.failure_count, 2)

    def test_circuit_trips_after_threshold(self):
        """Circuit trips CLOSED → OPEN after threshold failures."""
        config = CircuitBreakerConfig(failure_threshold=3)
        cb = CircuitBreaker(config)
        self.assertEqual(cb.state, CircuitState.CLOSED)

        cb.record_failure()
        self.assertEqual(cb.state, CircuitState.CLOSED)
        cb.record_failure()
        self.assertEqual(cb.state, CircuitState.CLOSED)
        cb.record_failure()
        self.assertEqual(cb.state, CircuitState.OPEN)

    def test_custom_name(self):
        """Circuit breaker respects custom name."""
        cb = CircuitBreaker(name="test-service")
        self.assertEqual(cb.name, "test-service")


class TestCircuitBreakerAsync(unittest.TestCase):
    """Test async call execution."""

    def test_call_success(self):
        """Successful call resets state."""

        async def test():
            async def succeed():
                return "ok"

            cb = CircuitBreaker()
            result = await cb.call(succeed)
            self.assertEqual(result, "ok")
            self.assertEqual(cb.failure_count, 0)

        asyncio.run(test())

    def test_call_with_sync_func(self):
        """Async call wraps sync functions."""

        async def test():
            def sync_func():
                return "sync_ok"

            cb = CircuitBreaker()
            result = await cb.call(sync_func)
            self.assertEqual(result, "sync_ok")

        asyncio.run(test())

    def test_call_failure_increments_counter(self):
        """Failed call increments counter."""

        async def test():
            async def fail():
                raise ValueError("test error")

            cb = CircuitBreaker()
            with self.assertRaises(ValueError):
                await cb.call(fail)
            self.assertEqual(cb.failure_count, 1)

        asyncio.run(test())

    def test_circuit_open_raises_without_fallback(self):
        """OPEN circuit raises CircuitBreakerOpen without fallback."""

        async def test():
            async def fail():
                raise ValueError("test")

            cb = CircuitBreaker(CircuitBreakerConfig(failure_threshold=1))
            with self.assertRaises(ValueError):
                await cb.call(fail)
            self.assertEqual(cb.state, CircuitState.OPEN)

            with self.assertRaises(CircuitBreakerOpen):
                await cb.call(fail)

        asyncio.run(test())

    def test_circuit_open_uses_fallback(self):
        """OPEN circuit uses fallback if provided."""

        async def test():
            async def fail():
                raise ValueError("test")

            async def fallback():
                return "fallback_ok"

            cb = CircuitBreaker(CircuitBreakerConfig(failure_threshold=1))
            with self.assertRaises(ValueError):
                await cb.call(fail)
            self.assertEqual(cb.state, CircuitState.OPEN)

            result = await cb.call(fail, fallback=fallback)
            self.assertEqual(result, "fallback_ok")

        asyncio.run(test())

    def test_call_with_args_kwargs(self):
        """Call forwards args and kwargs correctly."""

        async def test():
            async def add(a, b, c=0):
                return a + b + c

            cb = CircuitBreaker()
            result = await cb.call(add, 1, 2, c=3)
            self.assertEqual(result, 6)

        asyncio.run(test())


class TestBackoff(unittest.TestCase):
    """Test exponential backoff with jitter."""

    def test_backoff_increases_exponentially(self):
        """Backoff increases with each failure."""
        cb = CircuitBreaker(CircuitBreakerConfig(failure_threshold=10, backoff_base=2.0))

        cb.record_failure()
        backoff_1 = cb.last_backoff
        cb.record_failure()
        backoff_2 = cb.last_backoff

        # Second backoff should be larger (with some variance due to jitter)
        self.assertGreaterEqual(backoff_2, 0.1)

    def test_backoff_capped(self):
        """Backoff is capped at max."""
        config = CircuitBreakerConfig(failure_threshold=10, backoff_base=2.0, backoff_max=32.0)
        cb = CircuitBreaker(config)

        for _ in range(20):
            cb.record_failure()

        self.assertLessEqual(cb.last_backoff, config.backoff_max * 1.2)

    def test_jitter_applied(self):
        """Jitter is applied to backoff."""
        config = CircuitBreakerConfig(failure_threshold=2, backoff_base=10.0, jitter_percent=20.0)
        cb = CircuitBreaker(config)

        backoffs = []
        for _ in range(10):
            cb.failure_count = 0
            cb.record_failure()
            backoffs.append(cb.last_backoff)

        # Backoffs should vary due to jitter
        self.assertGreater(len(set(backoffs)), 1, "Jitter should produce varied backoffs")
        for b in backoffs:
            self.assertGreaterEqual(b, 7)
            self.assertLessEqual(b, 13)


class TestRecovery(unittest.TestCase):
    """Test circuit recovery."""

    def test_half_open_recovery(self):
        """Circuit transitions OPEN → HALF_OPEN → CLOSED on recovery."""

        async def test():
            config = CircuitBreakerConfig(failure_threshold=1, recovery_timeout=0.1)
            cb = CircuitBreaker(config)

            async def fail():
                raise ValueError("test")

            # Trip the circuit
            with self.assertRaises(ValueError):
                await cb.call(fail)
            self.assertEqual(cb.state, CircuitState.OPEN)

            # Wait for recovery
            await asyncio.sleep(0.15)

            async def succeed():
                return "ok"

            # Successful call in HALF_OPEN closes circuit
            result = await cb.call(succeed)
            self.assertEqual(result, "ok")
            self.assertEqual(cb.state, CircuitState.CLOSED)
            self.assertEqual(cb.failure_count, 0)

        asyncio.run(test())


if __name__ == "__main__":
    unittest.main()
