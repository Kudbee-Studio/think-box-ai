"""Worker inspection API (PR #199)."""

from __future__ import annotations

from typing import Any

from thinkbox.cloud_execution.worker_orchestrator import CloudExecutionWorker


def inspect_worker(worker: CloudExecutionWorker) -> dict[str, Any]:
    return worker.inspection_snapshot()
