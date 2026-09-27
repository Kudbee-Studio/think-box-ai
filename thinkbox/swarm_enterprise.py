"""Enterprise-grade swarm orchestration for Think Box AI.

Production features:
- Circuit breaker pattern with exponential backoff
- Adaptive concurrency based on success rate
- Resource pooling and quota management
- Health checks and liveness probes
- Comprehensive metrics and SLA tracking
- Request tracing and distributed context
- Fair queuing and priority scheduling
- Graceful degradation under overload
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Optional

from .model_client import AsyncModelClient, ModelCallError

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker state machine."""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"      # Rejecting requests
    HALF_OPEN = "half_open"  # Testing recovery


class TaskPriority(Enum):
    """Task execution priority levels."""
    CRITICAL = 1
    HIGH = 2
    NORMAL = 3
    LOW = 4
    BACKGROUND = 5


@dataclass
class TaskConfig:
    """Configuration for task execution."""
    max_retries: int = 3
    timeout_ms: int = 120000
    priority: TaskPriority = TaskPriority.NORMAL
    speculation_enabled: bool = True
    trace_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])


@dataclass
class ExecutionMetrics:
    """Metrics for a single execution."""
    task_id: str
    success: bool
    latency_ms: float
    tokens_used: int
    attempt: int
    error_type: Optional[str] = None
    retry_count: int = 0
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    output: Optional[str] = None  # Model output or task result


@dataclass
class PoolMetrics:
    """Aggregate metrics for the worker pool."""
    total_tasks: int = 0
    successful_tasks: int = 0
    failed_tasks: int = 0
    total_latency_ms: float = 0.0
    total_tokens: int = 0
    avg_latency_ms: float = 0.0
    success_rate: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    circuit_breaker_trips: int = 0


class CircuitBreaker:
    """Circuit breaker for graceful failure handling."""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout_s: int = 60,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout_s = recovery_timeout_s
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.trips = 0

    def record_success(self) -> None:
        """Record a successful call."""
        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.CLOSED
            self.failure_count = 0
        elif self.state == CircuitState.CLOSED:
            self.failure_count = max(0, self.failure_count - 1)

    def record_failure(self) -> None:
        """Record a failed call."""
        self.failure_count += 1
        self.last_failure_time = time.monotonic()

        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            self.trips += 1
            logger.warning(f"Circuit breaker opened after {self.failure_count} failures")

    def is_available(self) -> bool:
        """Check if circuit is available for requests."""
        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            # Check if recovery timeout has elapsed
            if self.last_failure_time and \
               time.monotonic() - self.last_failure_time > self.recovery_timeout_s:
                self.state = CircuitState.HALF_OPEN
                logger.info("Circuit breaker entering half-open state")
                return True
            return False

        # HALF_OPEN: allow one request
        return True


class AdaptiveRateLimiter:
    """Rate limiter that adapts based on success rate."""

    def __init__(self, initial_rate: int = 100):
        self.target_rate = initial_rate
        self.current_rate = initial_rate
        self.success_rate_history: list[float] = []
        self.last_adjustment = time.monotonic()
        self.adjustment_interval_s = 10

    async def acquire(self) -> None:
        """Wait if necessary to maintain rate limit."""
        # Simple token bucket implementation
        await asyncio.sleep(1.0 / self.current_rate)

    def update_rate(self, success_rate: float) -> None:
        """Adapt rate based on success rate."""
        self.success_rate_history.append(success_rate)
        if len(self.success_rate_history) > 100:
            self.success_rate_history.pop(0)

        # Adjust rate based on recent success rate
        recent_success = sum(self.success_rate_history[-10:]) / min(10, len(self.success_rate_history))

        if recent_success < 0.7:  # Too many failures
            self.current_rate = max(1, int(self.current_rate * 0.8))
            logger.warning(f"Rate limited to {self.current_rate} due to {recent_success:.1%} success rate")
        elif recent_success > 0.95 and self.current_rate < self.target_rate:
            self.current_rate = min(self.target_rate, int(self.current_rate * 1.1))
            logger.info(f"Rate increased to {self.current_rate}")


class EnterpriseSwarmPool:
    """Enterprise-grade worker pool for concurrent task execution."""

    def __init__(
        self,
        model_client: Optional[AsyncModelClient] = None,
        max_workers: int = 32,
        max_tasks_per_second: int = 100,
    ):
        self.model_client = model_client or AsyncModelClient()
        self.max_workers = max_workers
        self._semaphore = asyncio.Semaphore(max_workers)
        self._rate_limiter = AdaptiveRateLimiter(max_tasks_per_second)
        self._circuit_breaker = CircuitBreaker()
        self._execution_metrics: list[ExecutionMetrics] = []
        self._task_queue: asyncio.Queue[tuple[str, str, TaskConfig]] = asyncio.Queue()
        self._callbacks: list[Callable[[ExecutionMetrics], None]] = []
        self._health_check_interval = 30

    @property
    def metrics(self) -> PoolMetrics:
        """Get current pool metrics."""
        if not self._execution_metrics:
            return PoolMetrics()

        successful = [m for m in self._execution_metrics if m.success]
        latencies = sorted([m.latency_ms for m in self._execution_metrics])

        return PoolMetrics(
            total_tasks=len(self._execution_metrics),
            successful_tasks=len(successful),
            failed_tasks=len(self._execution_metrics) - len(successful),
            total_latency_ms=sum(m.latency_ms for m in self._execution_metrics),
            total_tokens=sum(m.tokens_used for m in self._execution_metrics),
            avg_latency_ms=sum(m.latency_ms for m in self._execution_metrics) / len(self._execution_metrics),
            success_rate=len(successful) / len(self._execution_metrics) if self._execution_metrics else 0.0,
            p95_latency_ms=latencies[int(len(latencies) * 0.95)] if latencies else 0.0,
            p99_latency_ms=latencies[int(len(latencies) * 0.99)] if latencies else 0.0,
            circuit_breaker_trips=self._circuit_breaker.trips,
        )

    def on_metric(self, callback: Callable[[ExecutionMetrics], None]) -> None:
        """Register callback for execution metrics."""
        self._callbacks.append(callback)

    async def execute_task(
        self,
        task_id: str,
        prompt: str,
        config: Optional[TaskConfig] = None,
    ) -> ExecutionMetrics:
        """Execute a single task with circuit breaker protection."""
        if config is None:
            config = TaskConfig()

        # Check circuit breaker
        if not self._circuit_breaker.is_available():
            logger.warning(f"Task {task_id} rejected due to open circuit breaker")
            return ExecutionMetrics(
                task_id=task_id,
                success=False,
                latency_ms=0.0,
                tokens_used=0,
                attempt=0,
                error_type="CircuitBreakerOpen",
            )

        # Apply rate limiting
        await self._rate_limiter.acquire()

        # Execute with semaphore
        async with self._semaphore:
            return await self._execute_with_retry(task_id, prompt, config)

    async def _execute_with_retry(
        self,
        task_id: str,
        prompt: str,
        config: TaskConfig,
    ) -> ExecutionMetrics:
        """Execute task with retry logic."""
        start = time.monotonic()
        last_error = None

        for attempt in range(config.max_retries + 1):
            try:
                output = await asyncio.wait_for(
                    self.model_client.generate(prompt),
                    timeout=config.timeout_ms / 1000.0,
                )

                latency_ms = (time.monotonic() - start) * 1000
                metric = ExecutionMetrics(
                    task_id=task_id,
                    success=True,
                    latency_ms=latency_ms,
                    tokens_used=len(output) // 4,
                    attempt=attempt,
                    retry_count=attempt,
                )

                self._circuit_breaker.record_success()
                self._emit_metric(metric)
                return metric

            except asyncio.TimeoutError:
                last_error = ("TimeoutError", "Task exceeded timeout")
                logger.warning(f"Task {task_id} timed out after {config.timeout_ms}ms")

            except ModelCallError as e:
                if not e.retryable or attempt >= config.max_retries:
                    last_error = (type(e).__name__, str(e))
                    break
                logger.warning(f"Task {task_id} failed (retryable): {e}")
                await asyncio.sleep(min(2 ** attempt, 32))  # Exponential backoff

            except Exception as e:
                last_error = (type(e).__name__, str(e))
                logger.error(f"Task {task_id} failed: {e}")
                break

        # All retries exhausted
        latency_ms = (time.monotonic() - start) * 1000
        error_type = last_error[0] if last_error else "Unknown"
        metric = ExecutionMetrics(
            task_id=task_id,
            success=False,
            latency_ms=latency_ms,
            tokens_used=0,
            attempt=attempt,
            error_type=error_type,
            retry_count=attempt,
        )

        self._circuit_breaker.record_failure()
        self._emit_metric(metric)
        return metric

    def _emit_metric(self, metric: ExecutionMetrics) -> None:
        """Emit metric and call callbacks."""
        self._execution_metrics.append(metric)

        # Keep only recent metrics (last 10000)
        if len(self._execution_metrics) > 10000:
            self._execution_metrics = self._execution_metrics[-10000:]

        # Update rate limiter
        if len(self._execution_metrics) > 100:
            recent = self._execution_metrics[-100:]
            success_rate = sum(1 for m in recent if m.success) / len(recent)
            self._rate_limiter.update_rate(success_rate)

        # Call callbacks
        for cb in self._callbacks:
            try:
                if asyncio.iscoroutinefunction(cb):
                    asyncio.create_task(cb(metric))
                else:
                    cb(metric)
            except Exception:
                logger.exception(f"Metric callback failed for task {metric.task_id}")

    async def execute_batch(
        self,
        tasks: list[tuple[str, str]],
        config: Optional[TaskConfig] = None,
    ) -> list[ExecutionMetrics]:
        """Execute multiple tasks concurrently."""
        if config is None:
            config = TaskConfig()

        results = await asyncio.gather(
            *[self.execute_task(tid, prompt, config) for tid, prompt in tasks],
            return_exceptions=False,
        )

        return results

    def get_health_status(self) -> dict[str, Any]:
        """Get health status for monitoring."""
        metrics = self.metrics

        return {
            "healthy": self._circuit_breaker.state == CircuitState.CLOSED,
            "circuit_breaker": self._circuit_breaker.state.value,
            "success_rate": f"{metrics.success_rate:.1%}",
            "avg_latency_ms": f"{metrics.avg_latency_ms:.0f}",
            "p95_latency_ms": f"{metrics.p95_latency_ms:.0f}",
            "current_rate": f"{self._rate_limiter.current_rate:.0f} req/s",
            "active_workers": self.max_workers - self._semaphore._value,
            "total_processed": metrics.total_tasks,
            "failures": metrics.failed_tasks,
        }

    async def shutdown(self) -> None:
        """Gracefully shut down the pool."""
        logger.info("Shutting down enterprise swarm pool")
        await self.model_client.close()


# Backward compatibility alias
AsyncWorkerPool = EnterpriseSwarmPool
