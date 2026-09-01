"""Dynamic Worker Auto-Scaler for ThinkBox AI.

Monitors local GPU/CPU load, VRAM, and memory saturation in real time.
Automatically scales active swarm concurrency up or down based on system resources.
Ensures zero task loss by pausing workers cleanly.
"""

from __future__ import annotations

import asyncio
import threading
import time
from dataclasses import dataclass, field
from typing import Any

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


@dataclass
class SystemMetrics:
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    memory_available_mb: float = 0.0
    gpu_vram_used_percent: float = 0.0
    gpu_memory_total_mb: float = 0.0
    gpu_memory_used_mb: float = 0.0
    timestamp: float = 0.0


@dataclass
class ScalerConfig:
    min_workers: int = 4
    max_workers: int = 512
    default_workers: int = 16
    vram_threshold_high: float = 90.0
    vram_threshold_low: float = 50.0
    cpu_threshold_high: float = 85.0
    cpu_threshold_low: float = 40.0
    memory_threshold_high: float = 90.0
    memory_threshold_low: float = 50.0
    scale_down_factor: float = 0.5
    scale_up_factor: float = 1.5
    check_interval_seconds: float = 5.0


class DynamicAutoscaler:
    def __init__(self, config: ScalerConfig | None = None):
        self.config = config or ScalerConfig()
        self._current_workers = self.config.default_workers
        self._target_workers = self.config.default_workers
        self._metrics = SystemMetrics()
        self._running = False
        self._lock = threading.Lock()
        self._pause_event = asyncio.Event()
        self._pause_event.set()
        self._callbacks: list[Any] = []

    @property
    def current_workers(self) -> int:
        with self._lock:
            return self._current_workers

    @property
    def target_workers(self) -> int:
        with self._lock:
            return self._target_workers

    @property
    def metrics(self) -> SystemMetrics:
        return self._metrics

    @property
    def is_paused(self) -> bool:
        return not self._pause_event.is_set()

    def on_scale(self, callback: Any) -> None:
        self._callbacks.append(callback)

    def _collect_metrics(self) -> SystemMetrics:
        metrics = SystemMetrics(timestamp=time.time())

        if not HAS_PSUTIL:
            return metrics

        metrics.cpu_percent = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory()
        metrics.memory_percent = mem.percent
        metrics.memory_available_mb = mem.available / (1024 * 1024)

        try:
            import subprocess
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=memory.used,memory.total,utilization.gpu",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                parts = result.stdout.strip().split(",")
                if len(parts) >= 2:
                    used = float(parts[0].strip())
                    total = float(parts[1].strip())
                    metrics.gpu_memory_used_mb = used
                    metrics.gpu_memory_total_mb = total
                    if total > 0:
                        metrics.gpu_vram_used_percent = (used / total) * 100
        except Exception:
            pass

        return metrics

    def _compute_target_workers(self) -> int:
        cfg = self.config
        m = self._metrics
        current = self._current_workers

        if m.gpu_vram_used_percent >= cfg.vram_threshold_high:
            target = int(current * cfg.scale_down_factor)
        elif m.cpu_percent >= cfg.cpu_threshold_high:
            target = int(current * cfg.scale_down_factor)
        elif m.memory_percent >= cfg.memory_threshold_high:
            target = int(current * cfg.scale_down_factor)
        elif (m.gpu_vram_used_percent <= cfg.vram_threshold_low and
              m.cpu_percent <= cfg.cpu_threshold_low and
              m.memory_percent <= cfg.memory_threshold_low):
            target = int(current * cfg.scale_up_factor)
        else:
            target = current

        target = max(cfg.min_workers, min(cfg.max_workers, target))
        return target

    async def _monitor_loop(self) -> None:
        while self._running:
            self._metrics = self._collect_metrics()
            new_target = self._compute_target_workers()

            with self._lock:
                old_target = self._target_workers
                self._target_workers = new_target

            if new_target != old_target:
                if new_target < self._current_workers:
                    self._pause_event.clear()

                for cb in self._callbacks:
                    try:
                        if asyncio.iscoroutinefunction(cb):
                            await cb(old_target, new_target)
                        else:
                            cb(old_target, new_target)
                    except Exception:
                        pass

                with self._lock:
                    self._current_workers = new_target

                self._pause_event.set()

            await asyncio.sleep(self.config.check_interval_seconds)

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._metrics = self._collect_metrics()
        asyncio.create_task(self._monitor_loop())

    async def stop(self) -> None:
        self._running = False
        self._pause_event.set()

    async def wait_if_paused(self) -> None:
        await self._pause_event.wait()

    def get_recommended_batch_size(self) -> int:
        with self._lock:
            return max(1, self._current_workers // 4)
