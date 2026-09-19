"""
KILO Cloud Agent — Scheduler Client

Handles work pull, heartbeat, capacity reporting, and outcome reporting to the governed scheduler.
"""

import asyncio
import time
import grpc
from typing import List, Optional, Dict, Any
import logging

from .protocol import scheduler_pb2, scheduler_pb2_grpc
from .kernel import AgentConfig

logger = logging.getLogger(__name__)


class SchedulerClient:
    """Client for communicating with the Governed Scheduler."""

    def __init__(self, endpoint: str, agent_id: str):
        self.endpoint = endpoint
        self.agent_id = agent_id
        self._channel: Optional[grpc.aio.Channel] = None
        self._stub: Optional[scheduler_pb2_grpc.SchedulerServiceStub] = None
        self._connected = False
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._capacity_task: Optional[asyncio.Task] = None
        self._sequence = 0

    async def connect(self):
        """Establish gRPC connection to scheduler."""
        self._channel = grpc.aio.insecure_channel(self.endpoint)
        self._stub = scheduler_pb2_grpc.SchedulerServiceStub(self._channel)
        
        # Wait for connection
        try:
            await asyncio.wait_for(self._channel.channel_ready(), timeout=10.0)
            self._connected = True
            logger.info(f"Scheduler client connected to {self.endpoint}")
        except asyncio.TimeoutError:
            logger.error(f"Scheduler connection timeout: {self.endpoint}")
            raise

    async def close(self):
        """Close gRPC connection."""
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        if self._capacity_task:
            self._capacity_task.cancel()
        if self._channel:
            await self._channel.close()
        self._connected = False

    async def register_agent(self, config: AgentConfig) -> bool:
        """Register this agent with the scheduler."""
        request = scheduler_pb2.AgentRegistration(
            agent_id=self.agent_id,
            agent_type=config.agent_type,
            agent_version=config.agent_version,
            protocol_version=config.protocol_version,
            capabilities=config.capabilities,
            resource_profile=scheduler_pb2.ResourceProfile(
                cpu_cores=config.resource_profile.cpu_cores,
                memory_mb=config.resource_profile.memory_mb,
                gpu_required=config.resource_profile.gpu_required,
                gpu_type=config.resource_profile.gpu_type,
                gpu_count=config.resource_profile.gpu_count,
                network_egress=config.resource_profile.network_egress,
                network_mbps=config.resource_profile.network_mbps,
                disk_mb=config.resource_profile.disk_mb,
                max_duration_seconds=config.resource_profile.max_duration_seconds,
            ),
            governance_tier=config.governance_tier,
            tenant_id=config.tenant_id,
            metadata=config.metadata,
        )
        
        response = await self._stub.RegisterAgent(request)
        return response.accepted

    async def pull_work(
        self,
        max_tasks: int = 1,
        accept_timeout_seconds: int = 30,
        preferred_task_types: Optional[List[str]] = None,
    ) -> scheduler_pb2.PullWorkResponse:
        """Pull work from scheduler (long-polling)."""
        request = scheduler_pb2.PullWorkRequest(
            agent_id=self.agent_id,
            max_tasks=max_tasks,
            accept_timeout_seconds=accept_timeout_seconds,
            preferred_task_types=preferred_task_types or [],
        )
        
        return await self._stub.PullWork(request)

    async def report_outcome(
        self,
        task_id: str,
        outcome: str,
        completed_at: float,
        duration_ms: int,
        resource_usage: Dict[str, Any],
        result_ref: str = "",
        error: Optional[Dict[str, Any]] = None,
        governance: Optional[Dict[str, Any]] = None,
        verification: Optional[Dict[str, Any]] = None,
    ):
        """Report task outcome to scheduler."""
        # Map outcome string to enum
        outcome_map = {
            "SUCCESS": scheduler_pb2.TaskOutcome.SUCCESS,
            "FAILED": scheduler_pb2.TaskOutcome.FAILED,
            "CANCELLED": scheduler_pb2.TaskOutcome.CANCELLED,
            "TIMEOUT": scheduler_pb2.TaskOutcome.TIMEOUT,
        }
        
        report = scheduler_pb2.TaskOutcomeReport(
            task_id=task_id,
            agent_id=self.agent_id,
            outcome=outcome_map.get(outcome, scheduler_pb2.TaskOutcome.FAILED),
            completed_at=str(completed_at),
            duration_ms=duration_ms,
            resource_usage=scheduler_pb2.ResourceUsage(
                cpu_seconds=resource_usage.get("cpu_seconds", 0),
                memory_peak_mb=resource_usage.get("memory_peak_mb", 0),
                gpu_seconds=resource_usage.get("gpu_seconds", 0),
                network_egress_mb=resource_usage.get("network_egress_mb", 0),
            ),
            result_ref=result_ref,
            error=scheduler_pb2.TaskError(
                error_code=error.get("error_code", "") if error else "",
                message=error.get("message", "") if error else "",
                context=error.get("context", {}) if error else {},
                retryable=error.get("retryable", False) if error else False,
            ) if error else None,
            governance=scheduler_pb2.GovernanceSummary(
                admission_decisions=governance.get("admission_decisions", 0) if governance else 0,
                approvals_requested=governance.get("approvals_requested", 0) if governance else 0,
                approvals_granted=governance.get("approvals_granted", 0) if governance else 0,
                tokens_used=governance.get("tokens_used", 0) if governance else 0,
            ) if governance else None,
            verification=scheduler_pb2.VerificationSummary(
                verified=verification.get("verified", False) if verification else False,
                verification_id=verification.get("verification_id", "") if verification else "",
                policy_version=verification.get("policy_version", "") if verification else "",
            ) if verification else None,
        )
        
        await self._stub.ReportOutcome(report)

    async def heartbeat(
        self,
        status: str,
        current_task_id: Optional[str] = None,
        task_progress_percent: int = 0,
        cpu_percent: float = 0.0,
        memory_percent: float = 0.0,
        disk_percent: float = 0.0,
        gpu_percent: float = 0.0,
        network_connections: int = 0,
    ) -> scheduler_pb2.HeartbeatResponse:
        """Send heartbeat to scheduler."""
        self._sequence += 1
        
        request = scheduler_pb2.Heartbeat(
            agent_id=self.agent_id,
            sequence=self._sequence,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            status=scheduler_pb2.AgentStatus.Value(status),
            current_task_id=current_task_id or "",
            task_progress_percent=task_progress_percent,
            resource_snapshot=scheduler_pb2.ResourceSnapshot(
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                disk_percent=disk_percent,
                gpu_percent=gpu_percent,
                network_connections=network_connections,
            ),
        )
        
        return await self._stub.Heartbeat(request)

    async def report_capacity(
        self,
        cpu_cores_available: float,
        cpu_cores_total: float,
        memory_mb_available: int,
        memory_mb_total: int,
        gpu_available: bool,
        network_mbps_available: int,
        disk_mb_available: int,
        disk_mb_total: int,
        max_concurrent_tasks: int,
        current_tasks: int,
        health_status: str = "HEALTHY",
        checks_passing: int = 0,
        checks_warning: int = 0,
        checks_failing: int = 0,
        preferred_task_types: Optional[List[str]] = None,
        avoid_task_types: Optional[List[str]] = None,
        max_task_duration_seconds: int = 3600,
    ):
        """Report capacity to scheduler."""
        request = scheduler_pb2.CapacityReport(
            agent_id=self.agent_id,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            capacity=scheduler_pb2.ResourceCapacity(
                cpu_cores_available=cpu_cores_available,
                cpu_cores_total=cpu_cores_total,
                memory_mb_available=memory_mb_available,
                memory_mb_total=memory_mb_total,
                gpu_available=gpu_available,
                network_mbps_available=network_mbps_available,
                disk_mb_available=disk_mb_available,
                disk_mb_total=disk_mb_total,
                max_concurrent_tasks=max_concurrent_tasks,
                current_tasks=current_tasks,
            ),
            health=scheduler_pb2.HealthStatus(
                status=scheduler_pb2.HealthStatus.Status.Value(health_status),
                checks_passing=checks_passing,
                checks_warning=checks_warning,
                checks_failing=checks_failing,
            ),
            preferences=scheduler_pb2.AgentPreferences(
                preferred_task_types=preferred_task_types or [],
                avoid_task_types=avoid_task_types or [],
                max_task_duration_seconds=max_task_duration_seconds,
            ),
        )
        
        await self._stub.ReportCapacity(request)

    async def health_check(self, service: str = "") -> scheduler_pb2.HealthCheckResponse:
        """Check scheduler health."""
        request = scheduler_pb2.HealthCheckRequest(service=service)
        return await self._stub.HealthCheck(request)

    async def start_heartbeat_loop(
        self,
        get_status_callback,
        get_resource_snapshot_callback,
        interval_seconds: int = 10,
    ):
        """Start periodic heartbeat loop."""
        async def _heartbeat_loop():
            while self._connected:
                try:
                    status, current_task_id, progress = get_status_callback()
                    cpu, mem, disk, gpu, net = get_resource_snapshot_callback()
                    
                    await self.heartbeat(
                        status=status,
                        current_task_id=current_task_id,
                        task_progress_percent=progress,
                        cpu_percent=cpu,
                        memory_percent=mem,
                        disk_percent=disk,
                        gpu_percent=gpu,
                        network_connections=net,
                    )
                except Exception as e:
                    logger.error(f"Heartbeat error: {e}")
                
                await asyncio.sleep(interval_seconds)
        
        self._heartbeat_task = asyncio.create_task(_heartbeat_loop())

    async def start_capacity_report_loop(
        self,
        get_capacity_callback,
        interval_seconds: int = 30,
    ):
        """Start periodic capacity reporting loop."""
        async def _capacity_loop():
            while self._connected:
                try:
                    capacity_data = get_capacity_callback()
                    await self.report_capacity(**capacity_data)
                except Exception as e:
                    logger.error(f"Capacity report error: {e}")
                
                await asyncio.sleep(interval_seconds)
        
        self._capacity_task = asyncio.create_task(_capacity_loop())

    @property
    def connected(self) -> bool:
        return self._connected