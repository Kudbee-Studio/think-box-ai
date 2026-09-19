"""
KILO Cloud Agent — Base Agent Classes

Base implementations for different agent categories.
"""

import asyncio
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Awaitable
from enum import Enum
import logging

from .kernel import AgentKernel, AgentConfig, AgentState
from .registry import AgentRegistry, AgentInfo, ResourceProfile, AgentHealth, AgentState as RegistryAgentState, get_global_registry

logger = logging.getLogger(__name__)


class TaskOutcome(Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    TIMEOUT = "TIMEOUT"


@dataclass
class TaskSpec:
    task_id: str
    task_type: str
    spec: Dict[str, Any]
    priority: int = 0
    deadline: Optional[float] = None  # Unix timestamp
    governance_token: Optional[str] = None
    experiment_id: Optional[str] = None
    think_box_id: Optional[str] = None
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class TaskResult:
    task_id: str
    outcome: TaskOutcome
    completed_at: float
    duration_ms: int
    resource_usage: Dict[str, Any]
    result_ref: Optional[str] = None
    error: Optional[Dict[str, Any]] = None
    governance: Optional[Dict[str, Any]] = None
    verification: Optional[Dict[str, Any]] = None


class BaseAgent(ABC):
    """Abstract base class for all agent types."""

    def __init__(self, config: AgentConfig):
        self.kernel = AgentKernel(config)
        self.registry: Optional[AgentRegistry] = None
        self._task_handlers: Dict[str, Callable[[TaskSpec], Awaitable[TaskResult]]] = {}
        self._running = False
        self._current_task: Optional[TaskSpec] = None

    @abstractmethod
    async def handle_task(self, task: TaskSpec) -> TaskResult:
        """Handle a task. Must be implemented by subclasses."""
        pass

    async def register_task_handler(self, task_type: str, handler: Callable[[TaskSpec], Awaitable[TaskResult]]):
        """Register a handler for a specific task type."""
        self._task_handlers[task_type] = handler

    async def start(self):
        """Start the agent."""
        await self.kernel.initialize()
        self.registry = get_global_registry()
        
        # Register with registry
        agent_info = AgentInfo(
            agent_id=self.kernel.config.agent_id,
            agent_type=self.kernel.config.agent_type,
            agent_version=self.kernel.config.agent_version,
            protocol_version=self.kernel.config.protocol_version,
            capabilities=self.kernel.config.capabilities,
            resource_profile=ResourceProfile(**self.kernel.config.resource_profile.__dict__),
            governance_tier=self.kernel.config.governance_tier,
            tenant_id=self.kernel.config.tenant_id,
            metadata=self.kernel.config.metadata,
        )
        await self.registry.register(agent_info)
        
        self._running = True
        logger.info(f"Agent {self.kernel.config.agent_id} started")

    async def stop(self):
        """Stop the agent."""
        self._running = False
        if self.registry:
            await self.registry.deregister(self.kernel.config.agent_id)
        await self.kernel.shutdown("STOPPED")
        logger.info(f"Agent {self.kernel.config.agent_id} stopped")

    async def run_loop(self):
        """Main agent loop - pull work, execute, report."""
        while self._running:
            try:
                # Pull work from scheduler
                work = await self.kernel.scheduler.pull_work(max_tasks=1)
                
                if not work.tasks:
                    # No work available, wait before next pull
                    await asyncio.sleep(work.next_pull_after_seconds or 5)
                    continue
                
                for task_assignment in work.tasks:
                    await self._execute_task(task_assignment)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Agent loop error: {e}")
                await asyncio.sleep(5)  # Backoff on error

    async def _execute_task(self, task_assignment):
        """Execute a single task assignment."""
        task = TaskSpec(
            task_id=task_assignment.task_id,
            task_type=task_assignment.task_type,
            spec=task_assignment.task_spec,
            priority=task_assignment.priority,
            deadline=task_assignment.deadline,
            governance_token=task_assignment.governance_token,
            experiment_id=task_assignment.experiment_id,
            think_box_id=task_assignment.think_box_id,
            metadata=task_assignment.metadata,
        )
        
        self._current_task = task
        start_time = time.time()
        
        # Update registry state
        if self.registry:
            await self.registry.heartbeat(
                self.kernel.config.agent_id,
                state=RegistryAgentState.EXECUTING,
                current_task_id=task.task_id,
                task_progress_percent=0,
            )
        
        try:
            # Execute task
            result = await self.handle_task(task)
            
            # Report outcome
            await self.kernel.scheduler.report_outcome(
                task_id=task.task_id,
                outcome=result.outcome.value,
                completed_at=result.completed_at,
                duration_ms=result.duration_ms,
                resource_usage=result.resource_usage,
                result_ref=result.result_ref,
                error=result.error,
                governance=result.governance,
                verification=result.verification,
            )
            
        except Exception as e:
            logger.error(f"Task execution failed: {e}")
            # Report failure
            await self.kernel.scheduler.report_outcome(
                task_id=task.task_id,
                outcome=TaskOutcome.FAILED.value,
                completed_at=time.time(),
                duration_ms=int((time.time() - start_time) * 1000),
                resource_usage={},
                error={"error_code": "EXECUTION_ERROR", "message": str(e), "retryable": False},
            )
        finally:
            self._current_task = None
            # Update registry state
            if self.registry:
                await self.registry.heartbeat(
                    self.kernel.config.agent_id,
                    state=RegistryAgentState.IDLE,
                    current_task_id=None,
                    task_progress_percent=0,
                )


class TaskAgent(BaseAgent):
    """
    TASK_AGENT — Single-task execution (stateless, idempotent, short-lived).
    
    Characteristics:
    - Stateless, idempotent
    - Short-lived (< 5 min typical)
    - High concurrency (100s per host)
    - Low resource profile
    """
    
    AGENT_TYPE = "TASK_AGENT"
    
    def __init__(self, config: AgentConfig):
        config.agent_type = self.AGENT_TYPE
        super().__init__(config)
        
        # Register default handlers
        self.register_task_handler("generic", self._handle_generic_task)
    
    async def handle_task(self, task: TaskSpec) -> TaskResult:
        """Route task to appropriate handler."""
        handler = self._task_handlers.get(task.task_type, self._task_handlers.get("generic"))
        if not handler:
            return TaskResult(
                task_id=task.task_id,
                outcome=TaskOutcome.FAILED,
                completed_at=time.time(),
                duration_ms=0,
                resource_usage={},
                error={"error_code": "NO_HANDLER", "message": f"No handler for task type: {task.task_type}", "retryable": False},
            )
        
        return await handler(task)
    
    async def _handle_generic_task(self, task: TaskSpec) -> TaskResult:
        """Default generic task handler."""
        start_time = time.time()
        
        # Simulate work
        await asyncio.sleep(0.1)
        
        return TaskResult(
            task_id=task.task_id,
            outcome=TaskOutcome.SUCCESS,
            completed_at=time.time(),
            duration_ms=int((time.time() - start_time) * 1000),
            resource_usage={"cpu_seconds": 0.1, "memory_peak_mb": 10},
            result_ref=f"memory://results/{task.task_id}",
        )


class WorkflowAgent(BaseAgent):
    """
    WORKFLOW_AGENT — Multi-step workflow orchestration with DAG execution.
    
    Characteristics:
    - Stateful, maintains workflow context
    - Manages DAG execution with dependencies
    - Medium concurrency (10s per host)
    - Medium resource profile
    """
    
    AGENT_TYPE = "WORKFLOW_AGENT"
    
    def __init__(self, config: AgentConfig):
        config.agent_type = self.AGENT_TYPE
        super().__init__(config)
        
        self._workflows: Dict[str, "WorkflowExecution"] = {}
    
    async def handle_task(self, task: TaskSpec) -> TaskResult:
        """Execute a workflow task."""
        # Check if this is a workflow definition or a step execution
        if task.task_type == "workflow_definition":
            return await self._execute_workflow(task)
        elif task.task_type == "workflow_step":
            return await self._execute_workflow_step(task)
        else:
            return await super().handle_task(task)
    
    async def _execute_workflow(self, task: TaskSpec) -> TaskResult:
        """Execute a full workflow from definition."""
        # Implementation would parse workflow DAG and execute steps
        # For now, return success
        return TaskResult(
            task_id=task.task_id,
            outcome=TaskOutcome.SUCCESS,
            completed_at=time.time(),
            duration_ms=100,
            resource_usage={"cpu_seconds": 1.0, "memory_peak_mb": 100},
            result_ref=f"memory://workflow/{task.task_id}",
        )
    
    async def _execute_workflow_step(self, task: TaskSpec) -> TaskResult:
        """Execute a single workflow step."""
        return TaskResult(
            task_id=task.task_id,
            outcome=TaskOutcome.SUCCESS,
            completed_at=time.time(),
            duration_ms=50,
            resource_usage={"cpu_seconds": 0.5, "memory_peak_mb": 50},
            result_ref=f"memory://step/{task.task_id}",
        )


class BatchAgent(BaseAgent):
    """
    BATCH_AGENT — High-throughput batch processing of many similar tasks.
    
    Characteristics:
    - Optimized for throughput
    - Minimal per-task overhead
    - Very high concurrency (1000s per host via work stealing)
    - High CPU, variable memory, GPU optional
    """
    
    AGENT_TYPE = "BATCH_AGENT"
    
    def __init__(self, config: AgentConfig):
        config.agent_type = self.AGENT_TYPE
        super().__init__(config)
        
        self._batch_queue: asyncio.Queue = asyncio.Queue()
        self._batch_size = 100
        self._batch_timeout = 1.0  # seconds
    
    async def handle_task(self, task: TaskSpec) -> TaskResult:
        """Add task to batch queue for processing."""
        # For batch agents, tasks are queued and processed in batches
        await self._batch_queue.put(task)
        
        # Return immediately - actual processing happens in background
        return TaskResult(
            task_id=task.task_id,
            outcome=TaskOutcome.SUCCESS,
            completed_at=time.time(),
            duration_ms=1,
            resource_usage={},
            result_ref=f"batch://queued/{task.task_id}",
        )
    
    async def run_batch_loop(self):
        """Background loop to process batched tasks."""
        while self._running:
            batch = []
            try:
                # Collect batch
                while len(batch) < self._batch_size:
                    try:
                        task = await asyncio.wait_for(
                            self._batch_queue.get(),
                            timeout=self._batch_timeout
                        )
                        batch.append(task)
                    except asyncio.TimeoutError:
                        break
                
                if batch:
                    await self._process_batch(batch)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Batch processing error: {e}")
                await asyncio.sleep(1)
    
    async def _process_batch(self, batch: List[TaskSpec]):
        """Process a batch of tasks."""
        # Execute all tasks in batch
        results = await asyncio.gather(
            *[self._execute_single_task(task) for task in batch],
            return_exceptions=True
        )
        
        # Report outcomes
        for task, result in zip(batch, results):
            if isinstance(result, Exception):
                await self.kernel.scheduler.report_outcome(
                    task_id=task.task_id,
                    outcome=TaskOutcome.FAILED.value,
                    completed_at=time.time(),
                    duration_ms=0,
                    resource_usage={},
                    error={"error_code": "BATCH_ERROR", "message": str(result), "retryable": False},
                )
            else:
                await self.kernel.scheduler.report_outcome(
                    task_id=task.task_id,
                    outcome=result.outcome.value,
                    completed_at=result.completed_at,
                    duration_ms=result.duration_ms,
                    resource_usage=result.resource_usage,
                    result_ref=result.result_ref,
                )
    
    async def _execute_single_task(self, task: TaskSpec) -> TaskResult:
        """Execute a single task within a batch."""
        handler = self._task_handlers.get(task.task_type, self._task_handlers.get("generic"))
        if handler:
            return await handler(task)
        
        return TaskResult(
            task_id=task.task_id,
            outcome=TaskOutcome.FAILED,
            completed_at=time.time(),
            duration_ms=0,
            resource_usage={},
            error={"error_code": "NO_HANDLER", "message": f"No handler for task type: {task.task_type}", "retryable": False},
        )


class StreamAgent(BaseAgent):
    """
    STREAM_AGENT — Continuous processing of unbounded data streams.
    
    Characteristics:
    - Long-running
    - Exactly-once semantics
    - Backpressure handling
    - Low concurrency (1 per stream partition)
    """
    
    AGENT_TYPE = "STREAM_AGENT"
    
    def __init__(self, config: AgentConfig):
        config.agent_type = self.AGENT_TYPE
        super().__init__(config)
        
        self._stream_sources: Dict[str, Any] = {}
        self._stream_sinks: Dict[str, Any] = {}
    
    async def handle_task(self, task: TaskSpec) -> TaskResult:
        """Handle stream management tasks."""
        if task.task_type == "stream_start":
            return await self._start_stream(task)
        elif task.task_type == "stream_stop":
            return await self._stop_stream(task)
        elif task.task_type == "stream_process":
            return await self._process_stream_item(task)
        else:
            return await super().handle_task(task)
    
    async def _start_stream(self, task: TaskSpec) -> TaskResult:
        """Start a stream processing job."""
        stream_id = task.spec.get("stream_id")
        source_config = task.spec.get("source")
        sink_config = task.spec.get("sink")
        
        # Initialize stream processing
        self._stream_sources[stream_id] = source_config
        self._stream_sinks[stream_id] = sink_config
        
        return TaskResult(
            task_id=task.task_id,
            outcome=TaskOutcome.SUCCESS,
            completed_at=time.time(),
            duration_ms=10,
            resource_usage={},
            result_ref=f"stream://{stream_id}/started",
        )
    
    async def _stop_stream(self, task: TaskSpec) -> TaskResult:
        """Stop a stream processing job."""
        stream_id = task.spec.get("stream_id")
        
        self._stream_sources.pop(stream_id, None)
        self._stream_sinks.pop(stream_id, None)
        
        return TaskResult(
            task_id=task.task_id,
            outcome=TaskOutcome.SUCCESS,
            completed_at=time.time(),
            duration_ms=5,
            resource_usage={},
            result_ref=f"stream://{stream_id}/stopped",
        )
    
    async def _process_stream_item(self, task: TaskSpec) -> TaskResult:
        """Process a single stream item."""
        return TaskResult(
            task_id=task.task_id,
            outcome=TaskOutcome.SUCCESS,
            completed_at=time.time(),
            duration_ms=1,
            resource_usage={},
            result_ref=f"stream://item/{task.task_id}",
        )