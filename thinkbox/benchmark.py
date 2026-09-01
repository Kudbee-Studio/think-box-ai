"""High-Throughput Benchmarking & Load Testing for ThinkBox AI.

Stress-tests parallel execution under high concurrency, captures system metrics,
and generates markdown reports.
"""

from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from thinkbox.engine import ThinkBoxEngine, EngineConfig
from thinkbox.autoscaler import DynamicAutoscaler, ScalerConfig
from thinkbox.session import create_session, get_session_sync
from backend.audit_storage import record_audit


@dataclass
class BenchmarkResult:
    worker_count: int
    total_tasks: int
    successful_tasks: int
    failed_tasks: int
    total_time_ms: float
    tokens_per_second: float
    avg_latency_ms: float
    ttft_ms: float
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    vram_percent: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "worker_count": self.worker_count,
            "total_tasks": self.total_tasks,
            "successful_tasks": self.successful_tasks,
            "failed_tasks": self.failed_tasks,
            "total_time_ms": round(self.total_time_ms, 2),
            "tokens_per_second": round(self.tokens_per_second, 2),
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "ttft_ms": round(self.ttft_ms, 2),
            "cpu_percent": round(self.cpu_percent, 1),
            "memory_percent": round(self.memory_percent, 1),
            "vram_percent": round(self.vram_percent, 1),
        }


@dataclass
class BenchmarkSuite:
    results: list[BenchmarkResult] = field(default_factory=list)
    timestamp: str = ""
    system_info: dict[str, Any] = field(default_factory=dict)


def _collect_system_metrics() -> dict[str, float]:
    metrics = {"cpu_percent": 0.0, "memory_percent": 0.0, "vram_percent": 0.0}

    try:
        import psutil
        metrics["cpu_percent"] = psutil.cpu_percent(interval=0.1)
        metrics["memory_percent"] = psutil.virtual_memory().percent
    except ImportError:
        pass

    try:
        import subprocess
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used,memory.total",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            parts = result.stdout.strip().split(",")
            if len(parts) >= 2:
                used = float(parts[0].strip())
                total = float(parts[1].strip())
                if total > 0:
                    metrics["vram_percent"] = (used / total) * 100
    except Exception:
        pass

    return metrics


async def run_single_benchmark(worker_count: int, num_tasks: int = 50) -> BenchmarkResult:
    config = EngineConfig()
    config.scaler_config.default_workers = worker_count
    config.scaler_config.max_workers = worker_count
    config.scaler_config.min_workers = worker_count
    config.speculative = False

    engine = ThinkBoxEngine(config)
    session = create_session(environment="benchmark", model_backend="Ollama", actor="benchmark")

    sync = get_session_sync()
    if sync.enabled:
        await sync.upsert(session, status="BENCHMARKING")

    system_metrics = _collect_system_metrics()

    start = time.monotonic()
    first_token_time = None

    async def run_tasks():
        nonlocal first_token_time
        tasks = []
        for i in range(num_tasks):
            task_prompt = f"Task {i}: Generate a short response"
            tasks.append(engine.swarm.execute_task(f"bench_{i}", task_prompt))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        return results

    results = await run_tasks()
    elapsed = (time.monotonic() - start) * 1000

    successful = sum(1 for r in results if not isinstance(r, Exception) and r.success)
    failed = len(results) - successful

    total_tokens = sum(
        r.tokens_used for r in results
        if not isinstance(r, Exception)
    )

    tokens_per_second = (total_tokens / (elapsed / 1000)) if elapsed > 0 else 0
    avg_latency = elapsed / num_tasks if num_tasks > 0 else 0

    if sync.enabled:
        await sync.upsert(session, status="COMPLETED")

    return BenchmarkResult(
        worker_count=worker_count,
        total_tasks=num_tasks,
        successful_tasks=successful,
        failed_tasks=failed,
        total_time_ms=elapsed,
        tokens_per_second=tokens_per_second,
        avg_latency_ms=avg_latency,
        ttft_ms=first_token_time or 0,
        cpu_percent=system_metrics["cpu_percent"],
        memory_percent=system_metrics["memory_percent"],
        vram_percent=system_metrics["vram_percent"],
    )


async def run_benchmark_suite(
    worker_counts: list[int] | None = None,
    tasks_per_run: int = 50,
) -> BenchmarkSuite:
    if worker_counts is None:
        worker_counts = [16, 64, 128, 256, 512]

    suite = BenchmarkSuite(
        timestamp=datetime.now(timezone.utc).isoformat(),
        system_info=_get_system_info(),
    )

    for count in worker_counts:
        result = await run_single_benchmark(count, tasks_per_run)
        suite.results.append(result)

    return suite


def _get_system_info() -> dict[str, Any]:
    info = {
        "platform": os.uname().sysname if hasattr(os, "uname") else "unknown",
        "python_version": os.sys.version,
        "cpu_count": os.cpu_count(),
    }

    try:
        import psutil
        mem = psutil.virtual_memory()
        info["total_memory_gb"] = round(mem.total / (1024**3), 2)
    except ImportError:
        pass

    return info


def generate_markdown_report(suite: BenchmarkSuite) -> str:
    lines = [
        "# ThinkBox High-Throughput Benchmark Report",
        "",
        f"**Timestamp:** {suite.timestamp}",
        f"**System:** {suite.system_info.get('platform', 'unknown')}",
        f"**CPU Cores:** {suite.system_info.get('cpu_count', 'unknown')}",
        f"**Memory:** {suite.system_info.get('total_memory_gb', 'unknown')} GB",
        "",
        "## Results Summary",
        "",
        "| Workers | Tasks | Success | Failed | Time (ms) | TPS | Avg Latency (ms) | CPU % | RAM % | VRAM % |",
        "|---------|-------|---------|--------|-----------|-----|------------------|-------|-------|--------|",
    ]

    for r in suite.results:
        lines.append(
            f"| {r.worker_count} | {r.total_tasks} | {r.successful_tasks} | {r.failed_tasks} "
            f"| {r.total_time_ms:.0f} | {r.tokens_per_second:.1f} | {r.avg_latency_ms:.1f} "
            f"| {r.cpu_percent:.0f} | {r.memory_percent:.0f} | {r.vram_percent:.0f} |"
        )

    if suite.results:
        best = max(suite.results, key=lambda r: r.tokens_per_second)
        lines.extend([
            "",
            "## Optimal Configuration",
            "",
            f"**Best Worker Count:** {best.worker_count}",
            f"**Peak TPS:** {best.tokens_per_second:.1f}",
            f"**Average Latency:** {best.avg_latency_ms:.1f}ms",
            f"**Success Rate:** {best.successful_tasks}/{best.total_tasks} ({best.successful_tasks/best.total_tasks*100:.0f}%)",
        ])

    lines.append("")
    return "\n".join(lines)


def save_report(suite: BenchmarkSuite, output_path: str = "BENCHMARK.md") -> None:
    report = generate_markdown_report(suite)
    Path(output_path).write_text(report)


async def main() -> None:
    print("Starting ThinkBox Benchmark Suite...")
    suite = await run_benchmark_suite()
    save_report(suite)
    print(f"Report saved to BENCHMARK.md")
    print(f"Results: {len(suite.results)} configurations tested")


if __name__ == "__main__":
    asyncio.run(main())
