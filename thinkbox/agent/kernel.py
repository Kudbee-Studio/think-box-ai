"""
KILO Cloud Agent Kernel — Base agent implementation with identity and lifecycle.
"""

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum
import logging

from .registry import AgentRegistry, ResourceProfile, get_global_registry
from .scheduler_client import SchedulerClient
from .governance_client import GovernanceClient
from .telemetry import TelemetryEmitter
from .orchestration_client import OrchestrationClient

logger = logging.getLogger(__name__)


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
class ResourceProfileConfig:
    cpu_cores: float = 1.0
    memory_mb: int = 512
    gpu_required: bool = False
    gpu_type: str = ""
    gpu_count: int = 0
    network_egress: bool = True
    network_mbps: int = 100
    disk_mb: int = 1024
    max_duration_seconds: int = 3600


@dataclass
class AgentConfig:
    agent_id: str = ""
    agent_type: str = "TASK_AGENT"
    agent_version: str = "1.0.0"
    protocol_version: str = "1.0"
    capabilities: List[str] = field(default_factory=list)
    resource_profile: ResourceProfileConfig = field(default_factory=ResourceProfileConfig)
    governance_tier: str = "GOVERNED"
    tenant_id: str = "default"
    metadata: Dict[str, str] = field(default_factory=dict)
    scheduler_endpoint: str = "localhost:50051"
    governance_endpoint: str = "localhost:50052"
    orchestration_endpoint: str = "localhost:50053"
    telemetry_endpoint: str = "localhost:4317"


@dataclass
class InitResult:
    success: bool
    agent_id: str
    error: Optional[str] = None


@dataclass
class ShutdownResult:
    success: bool
    error: Optional[str] = None


class LifecycleManager:
    """Manages agent lifecycle state transitions with governance checkpoints."""

    VALID_TRANSITIONS = {
        AgentState.SPAWNED: [AgentState.INITIALIZED, AgentState.TERMINATED],
        AgentState.INITIALIZED: [AgentState.IDLE, AgentState.EXECUTING, AgentState.TERMINATED],
        AgentState.IDLE: [AgentState.EXECUTING, AgentState.TERMINATED],
        AgentState.EXECUTING: [AgentState.CHECKPOINTED, AgentState.COMPLETED, 
                               AgentState.FAILED, AgentState.CANCELLED, AgentState.TERMINATED],
        AgentState.CHECKPOINTED: [AgentState.EXECUTING, AgentState.TERMINATED],
        AgentState.COMPLETED: [AgentState.IDLE, AgentState.TERMINATED],
        AgentState.FAILED: [AgentState.IDLE, AgentState.TERMINATED],
        AgentState.CANCELLED: [AgentState.IDLE, AgentState.TERMINATED],
        AgentState.TERMINATED: [],
    }

    GOVERNANCE_CHECKPOINTS = {
        (AgentState.SPAWNED, AgentState.INITIALIZED): "pre_spawn_admission",
        (AgentState.INITIALIZED, AgentState.IDLE): "capability_verification",
        (AgentState.IDLE, AgentState.EXECUTING): "task_admission",
        (AgentState.EXECUTING, AgentState.COMPLETED): "result_validation",
        (AgentState.EXECUTING, AgentState.FAILED): "error_classification",
        (AgentState.EXECUTING, AgentState.CANCELLED): "cancellation_audit",
        (AgentState.CHECKPOINTED, AgentState.EXECUTING): "state_integrity",
        (AgentState.COMPLETED, AgentState.IDLE): None,
        (AgentState.FAILED, AgentState.IDLE): None,
        (AgentState.CANCELLED, AgentState.IDLE): None,
        (AgentState.TERMINATED, None): "resource_release",
    }

    def __init__(self, agent, governance_client: GovernanceClient):
        self.agent = agent
        self.governance = governance_client
        self._state = AgentState.SPAWNED
        self._transition_history: List[Dict] = []

    @property
    def state(self) -> AgentState:
        return self._state

    async def transition(self, new_state: AgentState) -> bool:
        """Execute a state transition with governance checkpoint."""
        if new_state not in self.VALID_TRANSITIONS.get(self._state, []):
            logger.error(f"Invalid transition: {self._state} -> {new_state}")
            return False

        # Execute governance checkpoint if required
        checkpoint = self.GOVERNANCE_CHECKPOINTS.get((self._state, new_state))
        if checkpoint:
            success = await self._execute_checkpoint(checkpoint, new_state)
            if not success:
                logger.error(f"Governance checkpoint failed: {checkpoint}")
                return False

        old_state = self._state
        self._state = new_state
        
        # Record transition
        self._transition_history.append({
            "from": old_state.value,
            "to": new_state.value,
            "timestamp": time.time(),
            "checkpoint": checkpoint,
        })

        # Emit telemetry
        await self.agent.telemetry.emit_lifecycle_event(old_state, new_state)

        logger.info(f"Agent {self.agent.config.agent_id} transitioned: {old_state.value} -> {new_state.value}")
        return True

    async def _execute_checkpoint(self, checkpoint: str, target_state: AgentState) -> bool:
        """Execute a governance checkpoint."""
        try:
            if checkpoint == "pre_spawn_admission":
                # Request admission for agent spawn
                return await self.governance.check_admission(
                    action_type="AGENT_SPAWN",
                    action_spec={"agent_type": self.agent.config.agent_type},
                )
            elif checkpoint == "capability_verification":
                # Verify declared capabilities match actual
                return True  # Simplified
            elif checkpoint == "task_admission":
                # Check task admission
                return await self.governance.check_admission(
                    action_type="TASK_EXECUTE",
                    action_spec={"task_id": self.agent.current_task_id},
                )
            elif checkpoint == "result_validation":
                # Validate result before completion
                return True
            elif checkpoint == "error_classification":
                # Classify error for retry/termination decision
                return True
            elif checkpoint == "cancellation_audit":
                # Audit cancellation
                return True
            elif checkpoint == "state_integrity":
                # Verify checkpoint integrity
                return True
            elif checkpoint == "resource_release":
                # Verify all resources released
                return True
        except Exception as e:
            logger.error(f"Checkpoint {checkpoint} error: {e}")
            return False
        return True

    def get_history(self) -> List[Dict]:
        return self._transition_history


class AgentKernel:
    """
    Core agent kernel — manages identity, lifecycle, and platform integrations.
    """

    def __init__(self, config: AgentConfig):
        self.config = config
        if not self.config.agent_id:
            self.config.agent_id = str(uuid.uuid4())
        
        # Platform clients (initialized on demand)
        self._scheduler: Optional[SchedulerClient] = None
        self._governance: Optional[GovernanceClient] = None
        self._telemetry: Optional[TelemetryEmitter] = None
        self._orchestration: Optional[OrchestrationClient] = None
        self._registry: Optional[AgentRegistry] = None

        # Orchestration state
        self._orchestration_allocation_id: Optional[str] = None
        self._config_watch_task: Optional[asyncio.Task] = None

        # Lifecycle
        self.lifecycle = LifecycleManager(self, self.governance)
        
        # Runtime state
        self.current_task_id: Optional[str] = None
        self._initialized = False
        self._shutdown = False

    @property
    def scheduler(self) -> SchedulerClient:
        if self._scheduler is None:
            self._scheduler = SchedulerClient(self.config.scheduler_endpoint, self.config.agent_id)
        return self._scheduler

    @property
    def governance(self) -> GovernanceClient:
        if self._governance is None:
            self._governance = GovernanceClient(self.config.governance_endpoint, self.config.agent_id, self.config.tenant_id)
        return self._governance

    @property
    def telemetry(self) -> TelemetryEmitter:
        if self._telemetry is None:
            self._telemetry = TelemetryEmitter(
                self.config.agent_id,
                self.config.agent_type,
                self.config.tenant_id,
                self.config.telemetry_endpoint,
            )
        return self._telemetry

    @property
    def orchestration(self) -> OrchestrationClient:
        if self._orchestration is None:
            self._orchestration = OrchestrationClient(
                self.config.orchestration_endpoint,
                self.config.agent_id,
                self.config.tenant_id,
            )
        return self._orchestration

    @property
    def registry(self) -> AgentRegistry:
        if self._registry is None:
            self._registry = get_global_registry()
        return self._registry

    async def _inject_required_secrets(self):
        """Inject required secrets; fail-closed if any are missing."""
        required_secrets = self.config.metadata.get(
            "required_secrets", []
        )
        if not required_secrets:
            return
        response = await self.orchestration.inject_secrets(
            [{"name": s} for s in required_secrets],
        )
        injected_names = {h.name for h in response.handles}
        missing = [
            s for s in required_secrets if s not in injected_names
        ]
        if missing:
            raise RuntimeError(
                f"Required secrets injection failed: {missing}"
            )

    async def _watch_config_loop(self):
        """Background task: watch config changes."""
        try:
            async for config_value in self.orchestration.watch_config(
                "agent.config"
            ):
                logger.info(
                    f"Config updated: {config_value.key} "
                    f"= {config_value.value}"
                )
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Config watch error: {e}")

    def get_config(self, key: str, default: Any = None) -> Any:
        """Get a cached config value."""
        return self.orchestration.get_config_cache().get(
            key, default
        )

    def watch_config(self, key: str):
        """Watch a config key (delegates to OrchestrationClient)."""
        return self.orchestration.watch_config(key)

    async def initialize(self) -> InitResult:
        """Initialize the agent kernel and all platform connections."""
        try:
            # Transition to INITIALIZING
            await self.lifecycle.transition(AgentState.INITIALIZED)
            
            # Connect to platform services
            await self.scheduler.connect()
            await self.governance.connect()
            await self.telemetry.start()
            await self.orchestration.connect()

            # Orchestration: request capacity before proceeding
            _profile = self.config.resource_profile
            if isinstance(_profile, dict):
                _profile_dict = _profile
            else:
                _profile_dict = vars(_profile)
            capacity = await self.orchestration.request_capacity(
                _profile_dict,
                priority="NORMAL",
            )
            if not capacity.granted:
                raise RuntimeError(
                    f"Capacity request denied: {capacity.reason}"
                )
            self._orchestration_allocation_id = capacity.allocation_id

            # Orchestration: discover services as needed
            await self.orchestration.discover_services(
                "compute", namespace="default",
            )

            # Orchestration: inject secrets (fail-closed if required keys missing)
            await self._inject_required_secrets()

            # Orchestration: start config watch
            self._config_watch_task = asyncio.create_task(
                self._watch_config_loop()
            )

            # Register with agent registry
            from .registry import AgentInfo
            agent_info = AgentInfo(
                agent_id=self.config.agent_id,
                agent_type=self.config.agent_type,
                agent_version=self.config.agent_version,
                protocol_version=self.config.protocol_version,
                capabilities=self.config.capabilities,
                resource_profile=self.config.resource_profile,
                governance_tier=self.config.governance_tier,
                tenant_id=self.config.tenant_id,
                metadata=self.config.metadata,
            )
            await self.registry.register(agent_info)
            
            # Request initial governance token
            await self.governance.request_token(action_type="AGENT_INIT", ttl_seconds=3600)
            
            self._initialized = True
            
            # Transition to IDLE (ready for work)
            await self.lifecycle.transition(AgentState.IDLE)
            
            logger.info(f"Agent {self.config.agent_id} initialized successfully")
            return InitResult(success=True, agent_id=self.config.agent_id)
            
        except Exception as e:
            logger.error(f"Agent initialization failed: {e}")
            if self._orchestration_allocation_id:
                try:
                    await self.orchestration.release_capacity(
                        self._orchestration_allocation_id, reason="INIT_FAILED"
                    )
                except Exception:
                    pass
                self._orchestration_allocation_id = None
            await self.lifecycle.transition(AgentState.TERMINATED)
            return InitResult(success=False, agent_id=self.config.agent_id, error=str(e))

    async def shutdown(self, reason: str = "NORMAL") -> ShutdownResult:
        """Gracefully shut down the agent."""
        try:
            # Stop accepting new work
            await self.lifecycle.transition(AgentState.TERMINATED)

            # Flush telemetry
            await self.telemetry.flush()

            # Deregister from registry
            await self.registry.deregister(self.config.agent_id)

            # Close platform connections
            await self.scheduler.close()
            await self.governance.close()
            await self.telemetry.stop()
            await self.orchestration.close()

            self._shutdown = True
            logger.info(f"Agent {self.config.agent_id} shut down: {reason}")
            return ShutdownResult(success=True)

        except Exception as e:
            logger.error(f"Agent shutdown error: {e}")
            return ShutdownResult(success=False, error=str(e))
        finally:
            if self._config_watch_task:
                self._config_watch_task.cancel()
                try:
                    await self._config_watch_task
                except asyncio.CancelledError:
                    pass
                self._config_watch_task = None
            if self._orchestration_allocation_id:
                try:
                    await self.orchestration.release_capacity(
                        self._orchestration_allocation_id, reason=reason
                    )
                except Exception:
                    pass
                self._orchestration_allocation_id = None

    async def checkpoint(self) -> bool:
        """Create a checkpoint of current execution state."""
        if self.lifecycle.state != AgentState.EXECUTING:
            return False
        
        await self.lifecycle.transition(AgentState.CHECKPOINTED)
        # Actual checkpoint logic would go here
        await self.lifecycle.transition(AgentState.EXECUTING)
        return True

    async def restore(self, checkpoint_id: str) -> bool:
        """Restore from a checkpoint."""
        await self.lifecycle.transition(AgentState.CHECKPOINTED)
        # Actual restore logic would go here
        await self.lifecycle.transition(AgentState.EXECUTING)
        return True

    @property
    def is_healthy(self) -> bool:
        return self._initialized and not self._shutdown

    @property
    def state(self) -> AgentState:
        return self.lifecycle.state