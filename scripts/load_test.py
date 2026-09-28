#!/usr/bin/env python3
"""Enterprise load testing suite.

Comprehensive load testing with configurable workloads, metrics collection,
and performance profiling for enterprise systems.
"""

import asyncio
import time
import json
import argparse
from dataclasses import dataclass, asdict
from typing import Optional, Callable
from datetime import datetime, timezone
from enum import Enum

try:
    from thinkbox.async_http import AsyncHttpClient, HttpError
except ImportError:
    class AsyncHttpClient:
        async def post(self, *args, **kwargs):
            raise NotImplementedError()

    class HttpError(Exception):
        pass


class LoadPattern(Enum):
    """Load testing pattern."""

    CONSTANT = "constant"
    RAMP = "ramp"
    SPIKE = "spike"
    WAVE = "wave"


@dataclass
class LoadTestConfig:
    """Load test configuration."""

    target_url: str
    pattern: LoadPattern = LoadPattern.CONSTANT
    duration_seconds: int = 60
    requests_per_second: float = 10.0
    max_concurrent: int = 50
    ramp_up_seconds: int = 10
    spike_multiplier: float = 5.0
    spike_duration_seconds: int = 5
    payload_size_bytes: int = 1000
    request_timeout_seconds: int = 30
    auth_token: Optional[str] = None


@dataclass
class RequestMetrics:
    """Metrics for a single request."""

    request_id: int
    status_code: int
    latency_ms: float
    timestamp: str
    error: Optional[str] = None
    success: bool = True


@dataclass
class LoadTestResult:
    """Results of a load test."""

    total_requests: int
    successful_requests: int
    failed_requests: int
    min_latency_ms: float
    max_latency_ms: float
    mean_latency_ms: float
    median_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    throughput_rps: float
    errors_by_code: dict[str, int]
    test_duration_seconds: float
    timestamp: str


class LoadTester:
    """Enterprise load tester."""

    def __init__(self, config: LoadTestConfig) -> None:
        self.config = config
        self.client = AsyncHttpClient()
        self.metrics: list[RequestMetrics] = []
        self.start_time = 0.0
        self.request_counter = 0

    async def run(self) -> LoadTestResult:
        """Run load test."""
        self.start_time = time.time()
        self.request_counter = 0

        print(f"🚀 Starting load test: {self.config.pattern.value} pattern")
        print(f"   Target: {self.config.target_url}")
        print(f"   Duration: {self.config.duration_seconds}s")
        print(f"   Requests/sec: {self.config.requests_per_second}")
        print(f"   Max concurrent: {self.config.max_concurrent}")

        # Create tasks based on pattern
        if self.config.pattern == LoadPattern.CONSTANT:
            await self._run_constant_load()
        elif self.config.pattern == LoadPattern.RAMP:
            await self._run_ramp_load()
        elif self.config.pattern == LoadPattern.SPIKE:
            await self._run_spike_load()
        elif self.config.pattern == LoadPattern.WAVE:
            await self._run_wave_load()

        return self._calculate_results()

    async def _run_constant_load(self) -> None:
        """Run constant load pattern."""
        end_time = self.start_time + self.config.duration_seconds
        semaphore = asyncio.Semaphore(self.config.max_concurrent)

        async def rate_limited_request():
            async with semaphore:
                await self._send_request()

        tasks = []
        while time.time() < end_time:
            tasks.append(asyncio.create_task(rate_limited_request()))
            await asyncio.sleep(1.0 / self.config.requests_per_second)

            # Complete tasks periodically
            if len(tasks) > 1000:
                await asyncio.gather(*tasks, return_exceptions=True)
                tasks = []

        await asyncio.gather(*tasks, return_exceptions=True)

    async def _run_ramp_load(self) -> None:
        """Run ramp-up load pattern."""
        semaphore = asyncio.Semaphore(self.config.max_concurrent)
        ramp_step = self.config.requests_per_second / self.config.ramp_up_seconds
        current_rps = 1.0

        async def rate_limited_request():
            async with semaphore:
                await self._send_request()

        tasks = []
        end_time = self.start_time + self.config.duration_seconds

        while time.time() < end_time:
            if time.time() - self.start_time < self.config.ramp_up_seconds:
                current_rps = min(
                    self.config.requests_per_second,
                    current_rps + ramp_step
                )

            tasks.append(asyncio.create_task(rate_limited_request()))
            await asyncio.sleep(1.0 / current_rps)

            if len(tasks) > 1000:
                await asyncio.gather(*tasks, return_exceptions=True)
                tasks = []

        await asyncio.gather(*tasks, return_exceptions=True)

    async def _run_spike_load(self) -> None:
        """Run spike load pattern."""
        semaphore = asyncio.Semaphore(self.config.max_concurrent)
        spike_start = self.start_time + (self.config.duration_seconds // 2)
        spike_end = spike_start + self.config.spike_duration_seconds

        async def rate_limited_request():
            async with semaphore:
                await self._send_request()

        tasks = []
        end_time = self.start_time + self.config.duration_seconds

        while time.time() < end_time:
            now = time.time()
            current_rps = self.config.requests_per_second

            if spike_start <= now < spike_end:
                current_rps *= self.config.spike_multiplier

            tasks.append(asyncio.create_task(rate_limited_request()))
            await asyncio.sleep(1.0 / current_rps)

            if len(tasks) > 1000:
                await asyncio.gather(*tasks, return_exceptions=True)
                tasks = []

        await asyncio.gather(*tasks, return_exceptions=True)

    async def _run_wave_load(self) -> None:
        """Run wave load pattern."""
        semaphore = asyncio.Semaphore(self.config.max_concurrent)
        wave_period = 10.0  # 10 second wave cycle

        async def rate_limited_request():
            async with semaphore:
                await self._send_request()

        tasks = []
        end_time = self.start_time + self.config.duration_seconds

        while time.time() < end_time:
            elapsed = time.time() - self.start_time
            wave_phase = (elapsed % wave_period) / wave_period
            # Sine wave between 0.5x and 1.5x base rate
            multiplier = 1.0 + 0.5 * (2.0 * (wave_phase - 0.5))
            current_rps = self.config.requests_per_second * multiplier

            tasks.append(asyncio.create_task(rate_limited_request()))
            await asyncio.sleep(1.0 / current_rps)

            if len(tasks) > 1000:
                await asyncio.gather(*tasks, return_exceptions=True)
                tasks = []

        await asyncio.gather(*tasks, return_exceptions=True)

    async def _send_request(self) -> None:
        """Send a single request."""
        self.request_counter += 1
        request_id = self.request_counter
        request_start = time.time()

        try:
            headers = {"Content-Type": "application/json"}
            if self.config.auth_token:
                headers["Authorization"] = f"Bearer {self.config.auth_token}"

            payload = {"test": "load_test", "request_id": request_id}
            body = json.dumps(payload)

            response = await self.client.post(
                self.config.target_url,
                headers=headers,
                body=body,
                timeout=self.config.request_timeout_seconds,
            )

            latency_ms = (time.time() - request_start) * 1000
            metrics = RequestMetrics(
                request_id=request_id,
                status_code=response.status_code,
                latency_ms=latency_ms,
                timestamp=datetime.now(timezone.utc).isoformat(),
                success=200 <= response.status_code < 300,
            )

        except HttpError as e:
            latency_ms = (time.time() - request_start) * 1000
            metrics = RequestMetrics(
                request_id=request_id,
                status_code=0,
                latency_ms=latency_ms,
                timestamp=datetime.now(timezone.utc).isoformat(),
                error=str(e),
                success=False,
            )
        except Exception as e:
            latency_ms = (time.time() - request_start) * 1000
            metrics = RequestMetrics(
                request_id=request_id,
                status_code=0,
                latency_ms=latency_ms,
                timestamp=datetime.now(timezone.utc).isoformat(),
                error=f"Unexpected error: {str(e)}",
                success=False,
            )

        self.metrics.append(metrics)

        if request_id % 100 == 0:
            success_rate = sum(1 for m in self.metrics if m.success) / len(self.metrics) * 100
            print(f"  ✓ Sent {request_id} requests ({success_rate:.1f}% success)")

    def _calculate_results(self) -> LoadTestResult:
        """Calculate test results."""
        test_duration = time.time() - self.start_time

        successful = [m for m in self.metrics if m.success]
        failed = [m for m in self.metrics if not m.success]

        latencies = [m.latency_ms for m in successful]
        latencies.sort()

        errors_by_code: dict[str, int] = {}
        for m in failed:
            code = str(m.status_code if m.status_code else "error")
            errors_by_code[code] = errors_by_code.get(code, 0) + 1

        def percentile(data: list[float], p: float) -> float:
            if not data:
                return 0.0
            idx = int(len(data) * (p / 100))
            return data[min(idx, len(data) - 1)]

        result = LoadTestResult(
            total_requests=len(self.metrics),
            successful_requests=len(successful),
            failed_requests=len(failed),
            min_latency_ms=min(latencies) if latencies else 0,
            max_latency_ms=max(latencies) if latencies else 0,
            mean_latency_ms=sum(latencies) / len(latencies) if latencies else 0,
            median_latency_ms=percentile(latencies, 50),
            p95_latency_ms=percentile(latencies, 95),
            p99_latency_ms=percentile(latencies, 99),
            throughput_rps=len(self.metrics) / test_duration,
            errors_by_code=errors_by_code,
            test_duration_seconds=test_duration,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        return result


async def main() -> None:
    """Run load test."""
    parser = argparse.ArgumentParser(description="Enterprise load testing")
    parser.add_argument("--url", required=True, help="Target URL")
    parser.add_argument("--pattern", default="constant", choices=["constant", "ramp", "spike", "wave"])
    parser.add_argument("--duration", type=int, default=60, help="Test duration in seconds")
    parser.add_argument("--rps", type=float, default=10.0, help="Requests per second")
    parser.add_argument("--max-concurrent", type=int, default=50, help="Max concurrent requests")
    parser.add_argument("--token", help="Authorization token")
    parser.add_argument("--output", help="Output JSON file")

    args = parser.parse_args()

    config = LoadTestConfig(
        target_url=args.url,
        pattern=LoadPattern(args.pattern),
        duration_seconds=args.duration,
        requests_per_second=args.rps,
        max_concurrent=args.max_concurrent,
        auth_token=args.token,
    )

    tester = LoadTester(config)
    result = await tester.run()

    # Print results
    print("\n📊 Load Test Results")
    print("=" * 60)
    print(f"Total Requests:     {result.total_requests}")
    print(f"Successful:         {result.successful_requests} ({result.successful_requests/result.total_requests*100:.1f}%)")
    print(f"Failed:             {result.failed_requests}")
    print(f"Throughput:         {result.throughput_rps:.2f} req/s")
    print(f"Test Duration:      {result.test_duration_seconds:.2f}s")
    print("\n⏱️  Latency Metrics")
    print("=" * 60)
    print(f"Min:                {result.min_latency_ms:.2f}ms")
    print(f"Max:                {result.max_latency_ms:.2f}ms")
    print(f"Mean:               {result.mean_latency_ms:.2f}ms")
    print(f"Median:             {result.median_latency_ms:.2f}ms")
    print(f"P95:                {result.p95_latency_ms:.2f}ms")
    print(f"P99:                {result.p99_latency_ms:.2f}ms")

    if result.errors_by_code:
        print("\n⚠️  Errors by Status Code")
        print("=" * 60)
        for code, count in sorted(result.errors_by_code.items()):
            print(f"{code}: {count}")

    # Save results
    if args.output:
        with open(args.output, "w") as f:
            json.dump(asdict(result), f, indent=2)
        print(f"\n✅ Results saved to {args.output}")


if __name__ == "__main__":
    asyncio.run(main())
