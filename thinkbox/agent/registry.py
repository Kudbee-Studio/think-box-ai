"""
KILO Cloud Agent Registry — Central agent registration, discovery, and health tracking.
"""

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Callable, Awaitable
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class AgentHealth(Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"
    UNKNOWN = "UNKNOWN"


class AgentState(Enum):
    SPAWNED = "SPAWNED"
    INITIALIZED = "INITIALIZED"
    IDLE = "IDLE"
    EXECUTING = "EXECUTING"
    CHECKPOINTED = "CHECKPOINTED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    TERMINATED = "TERMINATED"


@dataclass
class ResourceProfile:
    cpu_cores: float
    memory_mb: int
    gpu_required: bool = False
    gpu_type: str = ""
    gpu_count: int = 0
    network_egress: bool = False
    network_mbps: int = 100
    disk_mb: int = 1024
    max_duration_seconds: int = 3600


@dataclass
class AgentInfo:
    agent_id: str
    agent_type: str
    agent_version: str
    protocol_version: str
    capabilities: List[str]
    resource_profile: ResourceProfile
    governance_tier: str
    tenant_id: str
    metadata: Dict[str, str] = field(default_factory=dict)
    registered_at: float = field(default_factory=time.time)
    last_heartbeat: float = field(default_factory=time.time)
    health: AgentHealth = AgentHealth.UNKNOWN
    state: AgentState = AgentState.SPAWNED
    current_task_id: Optional[str] = None
    task_progress_percent: int = 0
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    available_capacity: float = 1.0  # 0.0 - 1.0
    endpoint: str = ""  # gRPC endpoint for direct communication

    def is_healthy(self) -> bool:
        return self.health == AgentHealth.HEALTHY

    def can_accept_task(self, required_capabilities: List[str]) -> bool:
        if not self.is_healthy():
            return False
        if self.state not in (AgentState.IDLE, AgentState.INITIALIZED):
            return False
        return all(cap in self.capabilities for cap in required_capabilities)


@dataclass
class RegistryEvent:
    event_type: str  # REGISTERED, DEREGISTERED, HEALTH_CHANGED, STATE_CHANGED
    agent_id: str
    timestamp: float
    data: Dict = field(default_factory=dict)


class AgentRegistry:
    """
    Central registry for agent registration, discovery, and health tracking.
    Supports TTL-based registration with automatic expiration.
    """

    def __init__(
        self,
        default_ttl_seconds: int = 300,
        cleanup_interval_seconds: int = 60,
    ):
        self._agents: Dict[str, AgentInfo] = {}
        self._default_ttl = default_ttl_seconds
        self._cleanup_interval = cleanup_interval_seconds
        self._subscribers: List[Callable[[RegistryEvent], Awaitable[None]]] = []
        self._cleanup_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()

    async def start(self):
        """Start the registry background tasks."""
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("AgentRegistry started")

    async def stop(self):
        """Stop the registry background tasks."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        logger.info("AgentRegistry stopped")

    def subscribe(self, callback: Callable[[RegistryEvent], Awaitable[None]]):
        """Subscribe to registry events."""
        self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable[[RegistryEvent], Awaitable[None]]):
        """Unsubscribe from registry events."""
        if callback in self._subscribers:
            self._subscribers.remove(callback)

    async def _emit_event(self, event: RegistryEvent):
        """Emit event to all subscribers."""
        for callback in self._subscribers:
            try:
                await callback(event)
            except Exception as e:
                logger.error(f"Registry subscriber error: {e}")

    async def register(self, agent: AgentInfo) -> str:
        """
        Register an agent. Returns the agent_id.
        If agent_id is empty, generates a new ULID.
        """
        async with self._lock:
            if not agent.agent_id:
                agent.agent_id = str(uuid.uuid4())
            
            agent.last_heartbeat = time.time()
            agent.registered_at = time.time()
            self._agents[agent.agent_id] = agent

            await self._emit_event(RegistryEvent(
                event_type="REGISTERED",
                agent_id=agent.agent_id,
                timestamp=time.time(),
                data={"agent_type": agent.agent_type, "tenant_id": agent.tenant_id}
            ))

            logger.info(f"Agent registered: {agent.agent_id} ({agent.agent_type})")
            return agent.agent_id

    async def deregister(self, agent_id: str) -> bool:
        """Deregister an agent."""
        async with self._lock:
            if agent_id not in self._agents:
                return False
            
            agent = self._agents.pop(agent_id)
            await self._emit_event(RegistryEvent(
                event_type="DEREGISTERED",
                agent_id=agent_id,
                timestamp=time.time(),
                data={"agent_type": agent.agent_type}
            ))
            logger.info(f"Agent deregistered: {agent_id}")
            return True

    async def heartbeat(
        self,
        agent_id: str,
        health: AgentHealth = AgentHealth.HEALTHY,
        state: Optional[AgentState] = None,
        current_task_id: Optional[str] = None,
        task_progress_percent: int = 0,
        cpu_percent: float = 0.0,
        memory_percent: float = 0.0,
        available_capacity: float = 1.0,
    ) -> bool:
        """Update agent heartbeat and health/status."""
        async with self._lock:
            if agent_id not in self._agents:
                return False
            
            agent = self._agents[agent_id]
            old_health = agent.health
            old_state = agent.state
            
            agent.last_heartbeat = time.time()
            agent.health = health
            if state:
                agent.state = state
            if current_task_id is not None:
                agent.current_task_id = current_task_id
            agent.task_progress_percent = task_progress_percent
            agent.cpu_percent = cpu_percent
            agent.memory_percent = memory_percent
            agent.available_capacity = available_capacity

            if old_health != health:
                await self._emit_event(RegistryEvent(
                    event_type="HEALTH_CHANGED",
                    agent_id=agent_id,
                    timestamp=time.time(),
                    data={"old": old_health.value, "new": health.value}
                ))
            
            if old_state != agent.state:
                await self._emit_event(RegistryEvent(
                    event_type="STATE_CHANGED",
                    agent_id=agent_id,
                    timestamp=time.time(),
                    data={"old": old_state.value, "new": agent.state.value}
                ))

            return True

    async def get_agent(self, agent_id: str) -> Optional[AgentInfo]:
        """Get agent by ID."""
        async with self._lock:
            return self._agents.get(agent_id)

    async def find_agents(
        self,
        capabilities: Optional[List[str]] = None,
        agent_type: Optional[str] = None,
        governance_tier: Optional[str] = None,
        tenant_id: Optional[str] = None,
        health: Optional[AgentHealth] = None,
        state: Optional[AgentState] = None,
        min_capacity: float = 0.0,
    ) -> List[AgentInfo]:
        """Find agents matching criteria."""
        async with self._lock:
            results = []
            for agent in self._agents.values():
                if tenant_id and agent.tenant_id != tenant_id:
                    continue
                if agent_type and agent.agent_type != agent_type:
                    continue
                if governance_tier and agent.governance_tier != governance_tier:
                    continue
                if health and agent.health != health:
                    continue
                if state and agent.state != state:
                    continue
                if agent.available_capacity < min_capacity:
                    continue
                if capabilities and not all(cap in agent.capabilities for cap in capabilities):
                    continue
                results.append(agent)
            return results

    async def select_best_agent(
        self,
        required_capabilities: List[str],
        task_spec: Dict,
        tenant_id: Optional[str] = None,
    ) -> Optional[AgentInfo]:
        """
        Select the best agent for a task based on capability match,
        available capacity, and affinity scoring.
        """
        candidates = await self.find_agents(
            capabilities=required_capabilities,
            tenant_id=tenant_id,
            health=AgentHealth.HEALTHY,
            state=AgentState.IDLE,
            min_capacity=0.1,
        )

        if not candidates:
            return None

        # Score candidates
        scored = []
        for agent in candidates:
            # Capacity score (0-1)
            capacity_score = agent.available_capacity
            
            # Affinity score based on preferred task types
            affinity_score = 0.0
            preferred = agent.metadata.get("preferred_task_types", "").split(",")
            task_type = task_spec.get("task_type", "")
            if task_type in preferred:
                affinity_score = 1.0
            
            # Latency score (inverse of avg latency, normalized)
            latency_ms = float(agent.metadata.get("avg_latency_ms", "1000"))
            latency_score = min(1.0, 1000.0 / max(latency_ms, 1.0))
            
            # Weighted score
            score = (
                capacity_score * 0.4 +
                affinity_score * 0.3 +
                latency_score * 0.3
            )
            
            # Add small jitter for fairness
            import random
            score += random.uniform(0, 0.05)
            
            scored.append((score, agent))

        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[0][1] if scored else None

    async def list_agents(self, tenant_id: Optional[str] = None) -> List[AgentInfo]:
        """List all agents, optionally filtered by tenant."""
        async with self._lock:
            if tenant_id:
                return [a for a in self._agents.values() if a.tenant_id == tenant_id]
            return list(self._agents.values())

    async def get_agent_count(self, tenant_id: Optional[str] = None) -> int:
        """Get count of registered agents."""
        async with self._lock:
            if tenant_id:
                return sum(1 for a in self._agents.values() if a.tenant_id == tenant_id)
            return len(self._agents)

    async def _cleanup_loop(self):
        """Periodically clean up expired agents."""
        while True:
            try:
                await asyncio.sleep(self._cleanup_interval)
                await self._cleanup_expired()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Registry cleanup error: {e}")

    async def _cleanup_expired(self):
        """Remove agents that haven't sent heartbeat within TTL."""
        async with self._lock:
            now = time.time()
            expired = [
                agent_id for agent_id, agent in self._agents.items()
                if now - agent.last_heartbeat > self._default_ttl
            ]
            
            for agent_id in expired:
                agent = self._agents.pop(agent_id)
                await self._emit_event(RegistryEvent(
                    event_type="EXPIRED",
                    agent_id=agent_id,
                    timestamp=now,
                    data={"agent_type": agent.agent_type, "last_heartbeat": agent.last_heartbeat}
                ))
                logger.warning(f"Agent expired (no heartbeat): {agent_id}")

    async def get_stats(self) -> Dict:
        """Get registry statistics."""
        async with self._lock:
            by_type: Dict[str, int] = {}
            by_health: Dict[str, int] = {}
            by_state: Dict[str, int] = {}
            by_tenant: Dict[str, int] = {}
            
            for agent in self._agents.values():
                by_type[agent.agent_type] = by_type.get(agent.agent_type, 0) + 1
                by_health[agent.health.value] = by_health.get(agent.health.value, 0) + 1
                by_state[agent.state.value] = by_state.get(agent.state.value, 0) + 1
                by_tenant[agent.tenant_id] = by_tenant.get(agent.tenant_id, 0) + 1
            
            return {
                "total_agents": len(self._agents),
                "by_type": by_type,
                "by_health": by_health,
                "by_state": by_state,
                "by_tenant": by_tenant,
            }


# Global registry instance
_global_registry: Optional[AgentRegistry] = None


def get_global_registry() -> AgentRegistry:
    """Get or create the global agent registry."""
    global _global_registry
    if _global_registry is None:
        _global_registry = AgentRegistry()
    return _global_registry


async def initialize_global_registry(
    default_ttl_seconds: int = 300,
    cleanup_interval_seconds: int = 60,
) -> AgentRegistry:
    """Initialize the global registry."""
    global _global_registry
    _global_registry = AgentRegistry(
        default_ttl_seconds=default_ttl_seconds,
        cleanup_interval_seconds=cleanup_interval_seconds,
    )
    await _global_registry.start()
    return _global_registry


async def shutdown_global_registry():
    """Shutdown the global registry."""
    global _global_registry
    if _global_registry:
        await _global_registry.stop()
        _global_registry = None