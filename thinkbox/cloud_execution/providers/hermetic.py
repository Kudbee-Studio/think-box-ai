"""Deterministic hermetic execution provider for tests (PR #197)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from thinkbox.cloud_execution.errors import CloudExecutionError
from thinkbox.cloud_execution.heartbeat import WorkerHeartbeat
from thinkbox.cloud_execution.job import ExecutionJob
from thinkbox.cloud_execution.provider import CloudExecutionProvider, ProviderRunResult
from thinkbox.cloud_execution.resources import ResourceLimits
from thinkbox.cloud_execution.workspace import WorkspaceBinding

PROVIDER_NAME = "hermetic_local"


class HermeticCloudExecutionProvider(CloudExecutionProvider):
    """In-process provider — no network, no cloud accounts."""

    def __init__(self, scenario: str = "success") -> None:
        self._scenario = scenario
        self._available = True

    @property
    def name(self) -> str:
        return PROVIDER_NAME

    def is_available(self) -> bool:
        return self._available

    def set_available(self, available: bool) -> None:
        self._available = available

    def run(
        self,
        job: ExecutionJob,
        limits: ResourceLimits,
        workspace: WorkspaceBinding,
    ) -> ProviderRunResult:
        now = datetime.now(timezone.utc).isoformat()
        heartbeat = WorkerHeartbeat(
            worker_id=f"worker_{job.execution_id}",
            last_beat_at=now,
            interval_s=1.0,
            timeout_s=max(limits.wall_clock_timeout_s, 2.0),
        )
        scenario = str(job.metadata.get("hermetic_scenario", self._scenario))
        if scenario == "unavailable":
            raise CloudExecutionError(
                error_type="ProviderRunFailed",
                context={"reason": "simulated unavailable"},
            )
        if scenario == "timeout":
            heartbeat.last_beat_at = "1970-01-01T00:00:00+00:00"
            return ProviderRunResult(
                success=False,
                exit_code=124,
                summary="simulated timeout",
                heartbeat=heartbeat,
                metadata={"scenario": scenario},
            )
        if scenario == "cancel":
            return ProviderRunResult(
                success=False,
                exit_code=130,
                summary="simulated cancellation",
                heartbeat=heartbeat,
                metadata={"scenario": scenario},
            )
        if scenario == "fail":
            return ProviderRunResult(
                success=False,
                exit_code=1,
                summary="simulated failure",
                heartbeat=heartbeat,
                metadata={"scenario": scenario},
            )
        if scenario == "stale_heartbeat":
            heartbeat.last_beat_at = "1970-01-01T00:00:00+00:00"
            heartbeat.timeout_s = 1.0
            heartbeat.interval_s = 0.5
            return ProviderRunResult(
                success=False,
                exit_code=2,
                summary="stale heartbeat",
                heartbeat=heartbeat,
                metadata={"scenario": scenario},
            )
        artifact = f"artifact://hermetic/{job.job_id}/result.txt"
        return ProviderRunResult(
            success=True,
            exit_code=0,
            summary=f"hermetic ok: {job.intent[:80]}",
            artifact_refs=[artifact],
            heartbeat=heartbeat,
            metadata={"scenario": "success", "workspace": workspace.workspace_id},
        )
