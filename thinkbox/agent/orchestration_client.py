"""
KILO Cloud Agent — Orchestration Client

Handles capacity requests, service discovery, config watch, and secret injection
via the OrchestrationService gRPC endpoint.
"""

from __future__ import annotations

import asyncio
import time
import logging
from typing import List, Optional, Dict, Any, AsyncIterator

logger = logging.getLogger(__name__)

try:
    import grpc
    from google.protobuf import empty_pb2
except ImportError:
    grpc = None
    empty_pb2 = None

try:
    from .protocol import orchestration_pb2, orchestration_pb2_grpc
except ImportError:
    orchestration_pb2 = None
    orchestration_pb2_grpc = None

logger = logging.getLogger(__name__)


class OrchestrationClient:
    """Client for communicating with the Orchestration Service."""

    def __init__(self, endpoint: str, agent_id: str, tenant_id: str):
        self.endpoint = endpoint
        self.agent_id = agent_id
        self.tenant_id = tenant_id
        self._channel: Optional[grpc.aio.Channel] = None
        self._stub: Optional[orchestration_pb2_grpc.OrchestrationServiceStub] = None
        self._connected = False
        self._watch_config_task: Optional[asyncio.Task] = None
        self._watch_secret_task: Optional[asyncio.Task] = None
        self._config_cache: Dict[str, Any] = {}
        self._config_version: int = 0

    async def connect(self):
        """Establish gRPC connection to orchestration service."""
        if grpc is None or orchestration_pb2 is None or orchestration_pb2_grpc is None:
            raise RuntimeError(
                "grpc and protobuf dependencies are required for OrchestrationClient. "
                "Install grpcio and generate protocol buffers."
            )
        self._channel = grpc.aio.insecure_channel(self.endpoint)
        self._stub = orchestration_pb2_grpc.OrchestrationServiceStub(self._channel)

        try:
            await asyncio.wait_for(self._channel.channel_ready(), timeout=10.0)
            self._connected = True
            logger.info(f"Orchestration client connected to {self.endpoint}")
        except asyncio.TimeoutError:
            logger.error(f"Orchestration connection timeout: {self.endpoint}")
            raise

    async def close(self):
        """Close gRPC connection and cancel background tasks."""
        if self._watch_config_task:
            self._watch_config_task.cancel()
            self._watch_config_task = None
        if self._watch_secret_task:
            self._watch_secret_task.cancel()
            self._watch_secret_task = None
        if self._channel:
            await self._channel.close()
        self._connected = False
        logger.info(f"Orchestration client disconnected from {self.endpoint}")

    # ============================================================
    # Capacity Management
    # ============================================================

    async def request_capacity(
        self,
        resource_profile: Dict[str, Any],
        duration_hint_seconds: int = 3600,
        priority: str = "NORMAL",
        placement_constraints: Optional[Dict[str, Any]] = None,
        required_capabilities: Optional[List[str]] = None,
    ) -> orchestration_pb2.CapacityResponse:
        """Request compute capacity for an agent task."""
        if not self._connected:
            logger.warning("Orchestration not connected, capacity request denied")
            return orchestration_pb2.CapacityResponse(
                request_id="",
                granted=False,
                reason="Orchestration service unavailable",
            )

        request = orchestration_pb2.CapacityRequest(
            request_id=str(time.time_ns()),
            agent_id=self.agent_id,
            tenant_id=self.tenant_id,
            resource_profile=orchestration_pb2.ResourceProfile(
                cpu_cores=resource_profile.get("cpu_cores", 1.0),
                memory_mb=resource_profile.get("memory_mb", 512),
                gpu_required=resource_profile.get("gpu_required", False),
                gpu_type=resource_profile.get("gpu_type", ""),
                gpu_count=resource_profile.get("gpu_count", 0),
                network_egress=resource_profile.get("network_egress", True),
                network_mbps=resource_profile.get("network_mbps", 100),
                disk_mb=resource_profile.get("disk_mb", 1024),
                max_duration_seconds=resource_profile.get("max_duration_seconds", 3600),
            ),
            duration_hint_seconds=duration_hint_seconds,
            priority=orchestration_pb2.CapacityRequest.Priority.Value(priority),
            constraints=self._build_placement_constraints(placement_constraints or {}),
            required_capabilities=required_capabilities or [],
        )

        try:
            response = await self._stub.RequestCapacity(request)
            logger.info(
                f"Capacity request {request.request_id}: "
                f"granted={response.granted}, allocation={response.allocation_id}"
            )
            return response
        except Exception as e:
            logger.error(f"Capacity request error: {e}")
            return orchestration_pb2.CapacityResponse(
                request_id=request.request_id,
                granted=False,
                reason=f"Capacity request failed: {e}",
            )

    async def release_capacity(
        self,
        allocation_id: str,
        reason: str = "NORMAL",
    ) -> bool:
        """Release previously allocated capacity."""
        if not self._connected:
            return False

        request = orchestration_pb2.ReleaseRequest(
            allocation_id=allocation_id,
            agent_id=self.agent_id,
            reason=reason,
        )

        try:
            await self._stub.ReleaseCapacity(request)
            logger.info(f"Capacity released: {allocation_id}")
            return True
        except Exception as e:
            logger.error(f"Capacity release error: {e}")
            return False

    # ============================================================
    # Service Discovery
    # ============================================================

    async def discover_services(
        self,
        service_name: str,
        namespace: str = "",
        tags: Optional[Dict[str, str]] = None,
        health: str = "HEALTHY",
    ) -> orchestration_pb2.ServiceDiscoveryResponse:
        """Discover service endpoints by name and tags."""
        if not self._connected:
            return orchestration_pb2.ServiceDiscoveryResponse(
                endpoints=[],
                reason="Orchestration service unavailable",
            )

        request = orchestration_pb2.ServiceQuery(
            service_name=service_name,
            namespace=namespace,
            tags=tags or {},
            health=health,
        )

        try:
            response = await self._stub.DiscoverServices(request)
            logger.info(
                f"Service discovery: {service_name} → "
                f"{len(response.endpoints)} endpoints"
            )
            return response
        except Exception as e:
            logger.error(f"Service discovery error: {e}")
            return orchestration_pb2.ServiceDiscoveryResponse(
                endpoints=[],
                reason=f"Service discovery failed: {e}",
            )

    # ============================================================
    # Configuration Watch
    # ============================================================

    async def watch_config(
        self,
        key: str,
        current_version: int = 0,
    ) -> AsyncIterator[orchestration_pb2.ConfigValue]:
        """Watch for configuration changes (server-streaming)."""
        if not self._connected:
            return

        request = orchestration_pb2.ConfigWatchRequest(
            key=key,
            current_version=str(current_version),
        )

        try:
            async for config_value in self._stub.WatchConfig(request):
                self._config_cache[config_value.key] = config_value.value
                self._config_version = config_value.version
                yield config_value
        except Exception as e:
            logger.error(f"Config watch error: {e}")
            return

    def get_config_cache(self) -> Dict[str, Any]:
        """Return current configuration cache."""
        return dict(self._config_cache)

    def get_config_version(self) -> int:
        """Return last seen config version."""
        return self._config_version

    # ============================================================
    # Secret Injection
    # ============================================================

    async def inject_secrets(
        self,
        secrets: List[Dict[str, Any]],
        injection_method: str = "ENV_FILE",
        rotation_policy: str = "auto",
    ) -> orchestration_pb2.SecretInjectionResponse:
        """Inject secrets into the agent runtime."""
        if not self._connected:
            return orchestration_pb2.SecretInjectionResponse(
                handles=[],
                reason="Orchestration service unavailable",
            )

        secret_specs = []
        for s in secrets:
            secret_specs.append(
                orchestration_pb2.SecretSpec(
                    name=s.get("name", ""),
                    path=s.get("path", ""),
                    version=s.get("version", ""),
                    format=orchestration_pb2.SecretSpec.Format.Value(
                        s.get("format", "ENV")
                    ),
                    mount_path=s.get("mount_path", ""),
                )
            )

        request = orchestration_pb2.SecretInjectionSpec(
            request_id=str(time.time_ns()),
            agent_id=self.agent_id,
            secrets=secret_specs,
            injection_method=orchestration_pb2.SecretInjectionSpec.InjectionMethod.Value(
                injection_method
            ),
            rotation_policy=rotation_policy,
        )

        try:
            response = await self._stub.InjectSecrets(request)
            logger.info(
                f"Secret injection: {len(response.handles)} secrets injected"
            )
            return response
        except Exception as e:
            logger.error(f"Secret injection error: {e}")
            return orchestration_pb2.SecretInjectionResponse(
                handles=[],
                reason=f"Secret injection failed: {e}",
            )

    async def watch_secret_rotation(
        self,
    ) -> AsyncIterator[orchestration_pb2.SecretRotationEvent]:
        """Watch for secret rotation events (server-streaming)."""
        if not self._connected:
            return

        try:
            async for event in self._stub.WatchSecretRotation(
                empty_pb2.Empty(),
            ):
                logger.info(
                    f"Secret rotation: {event.secret_name} → v{event.new_version}"
                )
                yield event
        except Exception as e:
            logger.error(f"Secret rotation watch error: {e}")
            return

    # ============================================================
    # Helpers
    # ============================================================

    def _build_placement_constraints(
        self, data: Dict[str, Any]
    ) -> orchestration_pb2.PlacementConstraints:
        return orchestration_pb2.PlacementConstraints(
            zone=data.get("zone", ""),
            region=data.get("region", ""),
            provider=data.get("provider", ""),
            instance_types=data.get("instance_types", []),
            require_gpu=data.get("require_gpu", False),
            gpu_types=data.get("gpu_types", []),
            tenancy=data.get("tenancy", "shared"),
            compliance=data.get("compliance", []),
            data_residency=data.get("data_residency", ""),
        )

    @property
    def connected(self) -> bool:
        return self._connected
