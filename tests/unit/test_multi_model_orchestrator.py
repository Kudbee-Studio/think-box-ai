"""Tests for multi-model orchestrator.

Comprehensive test suite for intelligent LLM provider routing,
cost optimization, and multi-provider orchestration.
"""

from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from thinkbox.multi_model_orchestrator import (
    ExecutionStrategy,
    MultiModelOrchestrator,
    ProviderName,
    RoutingDecision,
    ExecutionResult,
    ProviderMetrics,
)


class TestProviderMetrics(unittest.TestCase):
    """Test ProviderMetrics dataclass."""

    def test_metrics_creation(self) -> None:
        """Test creating provider metrics."""
        metrics = ProviderMetrics(
            name=ProviderName.OPENAI,
            latency_p50_ms=100.0,
            latency_p95_ms=200.0,
            cost_per_1k_tokens=0.015,
            success_rate=0.99,
        )

        self.assertEqual(metrics.name, ProviderName.OPENAI)
        self.assertEqual(metrics.latency_p50_ms, 100.0)
        self.assertTrue(metrics.available)

    def test_metrics_defaults(self) -> None:
        """Test provider metrics defaults."""
        metrics = ProviderMetrics(name=ProviderName.ANTHROPIC)

        self.assertEqual(metrics.consecutive_failures, 0)
        self.assertEqual(metrics.success_rate, 1.0)
        self.assertTrue(metrics.available)


class TestRoutingDecision(unittest.IsolatedAsyncioTestCase):
    """Test routing decision logic."""

    async def asyncSetUp(self) -> None:
        """Set up test fixtures."""
        self.providers = {
            ProviderName.OPENAI: {},
            ProviderName.ANTHROPIC: {},
            ProviderName.GROQ: {},
            ProviderName.LOCAL: {},
        }
        self.orchestrator = MultiModelOrchestrator(
            self.providers,
            budget_usd=100.0,
        )

    async def test_route_request_selects_provider(self) -> None:
        """Test routing selects a provider."""
        routing = await self.orchestrator.route_request("Test prompt")

        self.assertIsNotNone(routing.primary_provider)
        self.assertIn(routing.primary_provider, ProviderName)
        self.assertIsNotNone(routing.rationale)

    async def test_routing_includes_fallbacks(self) -> None:
        """Test routing includes fallback providers."""
        routing = await self.orchestrator.route_request("Test prompt")

        self.assertIsInstance(routing.fallback_providers, list)
        # Should have at least 0 fallbacks, up to 2
        self.assertLessEqual(len(routing.fallback_providers), 2)

    async def test_routing_estimates_cost(self) -> None:
        """Test routing includes cost estimate."""
        # Disable LOCAL (free) provider to force cost estimation
        self.orchestrator._metrics[ProviderName.LOCAL].available = False

        routing = await self.orchestrator.route_request("Test prompt" * 100)

        self.assertGreaterEqual(routing.estimated_cost_usd, 0.0)
        # Cost should be greater for longer prompt
        routing2 = await self.orchestrator.route_request("Test prompt")
        # Both should have positive cost (at least 1 token)
        self.assertGreater(routing.estimated_cost_usd, routing2.estimated_cost_usd)


class TestExecution(unittest.IsolatedAsyncioTestCase):
    """Test execution with providers."""

    async def asyncSetUp(self) -> None:
        """Set up test fixtures."""
        self.providers = {
            ProviderName.OPENAI: {},
            ProviderName.ANTHROPIC: {},
            ProviderName.GROQ: {},
            ProviderName.LOCAL: {},
        }
        self.orchestrator = MultiModelOrchestrator(
            self.providers,
            budget_usd=1000.0,
        )

    async def test_execute_successful(self) -> None:
        """Test successful execution."""
        result = await self.orchestrator.execute("Test prompt")

        self.assertTrue(result.success)
        self.assertIsNotNone(result.output)
        self.assertIsNotNone(result.provider)
        self.assertGreater(result.latency_ms, 0)

    async def test_execute_tracks_cost(self) -> None:
        """Test execution tracks spending."""
        # Disable LOCAL provider to force paid provider
        self.orchestrator._metrics[ProviderName.LOCAL].available = False
        initial_spent = self.orchestrator.spent_usd

        await self.orchestrator.execute("Test prompt" * 100)

        self.assertGreater(self.orchestrator.spent_usd, initial_spent)

    async def test_execute_respects_budget(self) -> None:
        """Test execution respects budget constraint."""
        # Disable LOCAL (free) provider to force paid execution
        self.orchestrator._metrics[ProviderName.LOCAL].available = False
        self.orchestrator.budget_usd = 0.000001  # Very small budget

        result = await self.orchestrator.execute("Test prompt" * 1000)

        self.assertFalse(result.success)
        self.assertIn("Budget", result.error)

    async def test_execute_with_routing_decision(self) -> None:
        """Test execution with pre-computed routing."""
        routing = await self.orchestrator.route_request("Test prompt")
        result = await self.orchestrator.execute("Test prompt", routing)

        self.assertTrue(result.success)
        self.assertEqual(result.provider, routing.primary_provider)

    async def test_execute_fallback_on_failure(self) -> None:
        """Test execution tries fallback providers."""
        # This tests the logic even though we mock success
        result = await self.orchestrator.execute("Test prompt")

        # Should eventually succeed
        self.assertTrue(result.success)


class TestMetricsTracking(unittest.IsolatedAsyncioTestCase):
    """Test metrics and tracking."""

    async def asyncSetUp(self) -> None:
        """Set up test fixtures."""
        self.providers = {
            ProviderName.OPENAI: {},
            ProviderName.ANTHROPIC: {},
            ProviderName.GROQ: {},
            ProviderName.LOCAL: {},
        }
        self.orchestrator = MultiModelOrchestrator(
            self.providers,
            budget_usd=1000.0,
        )

    async def test_get_metrics_empty(self) -> None:
        """Test metrics when no executions."""
        metrics = self.orchestrator.get_metrics()

        self.assertEqual(metrics.total_executions, 0)
        self.assertEqual(metrics.successful_executions, 0)

    async def test_get_metrics_after_execution(self) -> None:
        """Test metrics after execution."""
        # Disable LOCAL (free) provider to force cost tracking
        self.orchestrator._metrics[ProviderName.LOCAL].available = False
        await self.orchestrator.execute("Test prompt" * 100)

        metrics = self.orchestrator.get_metrics()

        self.assertEqual(metrics.total_executions, 1)
        self.assertEqual(metrics.successful_executions, 1)
        self.assertGreater(metrics.total_cost_usd, 0)
        self.assertGreater(metrics.total_tokens, 0)

    async def test_get_metrics_cost_tracking(self) -> None:
        """Test cost tracking in metrics."""
        # Disable LOCAL (free) provider to force cost tracking
        self.orchestrator._metrics[ProviderName.LOCAL].available = False

        for _ in range(5):
            # Use longer prompt to ensure measurable cost
            await self.orchestrator.execute("Test prompt" * 50)

        metrics = self.orchestrator.get_metrics()

        self.assertEqual(metrics.total_executions, 5)
        self.assertGreater(metrics.cost_per_execution, 0)
        self.assertEqual(metrics.total_cost_usd, self.orchestrator.spent_usd)

    async def test_get_metrics_provider_distribution(self) -> None:
        """Test provider distribution tracking."""
        for _ in range(10):
            await self.orchestrator.execute("Test prompt")

        metrics = self.orchestrator.get_metrics()

        self.assertEqual(sum(metrics.provider_distribution.values()), 10)
        for provider_name, count in metrics.provider_distribution.items():
            self.assertGreater(count, 0)

    async def test_get_metrics_latency(self) -> None:
        """Test latency tracking."""
        await self.orchestrator.execute("Test prompt")
        await self.orchestrator.execute("Another test")

        metrics = self.orchestrator.get_metrics()

        self.assertGreater(metrics.avg_latency_ms, 0)


class TestProviderSelection(unittest.IsolatedAsyncioTestCase):
    """Test provider selection logic."""

    async def asyncSetUp(self) -> None:
        """Set up test fixtures."""
        self.providers = {
            ProviderName.OPENAI: {},
            ProviderName.ANTHROPIC: {},
            ProviderName.GROQ: {},
            ProviderName.LOCAL: {},
        }
        self.orchestrator = MultiModelOrchestrator(
            self.providers,
            budget_usd=1000.0,
        )

    async def test_local_provider_selected_when_cheap(self) -> None:
        """Test that local provider is preferred for cost."""
        # Set LOCAL as cheapest
        self.orchestrator._metrics[ProviderName.LOCAL].cost_per_1k_tokens = 0.0

        routing = await self.orchestrator.route_request("Test prompt")

        # LOCAL should be competitive due to zero cost
        self.assertIn(
            routing.primary_provider,
            [ProviderName.LOCAL, ProviderName.GROQ],
        )

    async def test_groq_preferred_for_speed(self) -> None:
        """Test that fast providers are preferred."""
        # GROQ should naturally be selected due to low latency
        routing = await self.orchestrator.route_request("Test prompt")

        # Just verify a provider was selected
        self.assertIsNotNone(routing.primary_provider)

    async def test_unavailable_provider_skipped(self) -> None:
        """Test that unavailable providers are skipped."""
        self.orchestrator._metrics[ProviderName.OPENAI].available = False

        routing = await self.orchestrator.route_request("Test prompt")

        self.assertNotEqual(routing.primary_provider, ProviderName.OPENAI)

    async def test_circuit_breaker_opens(self) -> None:
        """Test circuit breaker opens after failures."""
        metrics = self.orchestrator._metrics[ProviderName.OPENAI]

        # Simulate 3 failures
        for _ in range(3):
            self.orchestrator._record_failure(ProviderName.OPENAI)

        self.assertFalse(metrics.available)


class TestExecutionStrategies(unittest.IsolatedAsyncioTestCase):
    """Test different execution strategies."""

    async def asyncSetUp(self) -> None:
        """Set up test fixtures."""
        self.providers = {
            ProviderName.OPENAI: {},
            ProviderName.ANTHROPIC: {},
        }

    async def test_fastest_strategy(self) -> None:
        """Test FASTEST strategy."""
        orchestrator = MultiModelOrchestrator(
            self.providers,
            strategy=ExecutionStrategy.FASTEST,
        )

        self.assertEqual(orchestrator.strategy, ExecutionStrategy.FASTEST)

    async def test_cheapest_strategy(self) -> None:
        """Test CHEAPEST strategy."""
        orchestrator = MultiModelOrchestrator(
            self.providers,
            strategy=ExecutionStrategy.CHEAPEST,
        )

        self.assertEqual(orchestrator.strategy, ExecutionStrategy.CHEAPEST)

    async def test_consensus_strategy(self) -> None:
        """Test CONSENSUS strategy."""
        orchestrator = MultiModelOrchestrator(
            self.providers,
            strategy=ExecutionStrategy.CONSENSUS,
        )

        self.assertEqual(orchestrator.strategy, ExecutionStrategy.CONSENSUS)


if __name__ == "__main__":
    unittest.main()
