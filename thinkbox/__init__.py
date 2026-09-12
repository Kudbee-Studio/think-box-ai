"""ThinkBox AI — Core execution engine package."""

from .decomposer import TaskDecomposer, TaskNode, TaskGraph
from .model_client import AsyncModelClient, ModelConfig
from .swarm import AsyncWorkerPool, ExecutionResult, SpeculativeResult
from .autoscaler import DynamicAutoscaler, ScalerConfig, SystemMetrics
from .pruner import ContextPruner, PruneResult
from .git_engine import GitEngine, GitConfig, CommitReceipt
from .engine import ThinkBoxEngine, EngineConfig, TaskState, TaskEvent
from .legendary import (
    CausalReasoningEngine,
    CausalLink,
    TemporalMemory,
    MemorySnapshot,
    AgentEvolution,
    Genome,
    QuantumSuperposition,
    SuperposedPath,
    MetaCognition,
    ThoughtTrace,
    StigmergicSwarm,
    PheromoneTrail,
    ZeroKnowledgeProof,
    AffectiveComputing,
    EmotionalState,
    InterventionEngine,
    Hypothesis,
    InfiniteContext,
    CompressedChunk,
)

__all__ = [
    "TaskDecomposer",
    "TaskNode",
    "TaskGraph",
    "AsyncModelClient",
    "ModelConfig",
    "AsyncWorkerPool",
    "ExecutionResult",
    "SpeculativeResult",
    "DynamicAutoscaler",
    "ScalerConfig",
    "SystemMetrics",
    "ContextPruner",
    "PruneResult",
    "GitEngine",
    "GitConfig",
    "CommitReceipt",
    "ThinkBoxEngine",
    "EngineConfig",
    "TaskState",
    "TaskEvent",
    "CausalReasoningEngine",
    "CausalLink",
    "TemporalMemory",
    "MemorySnapshot",
    "AgentEvolution",
    "Genome",
    "QuantumSuperposition",
    "SuperposedPath",
    "MetaCognition",
    "ThoughtTrace",
    "StigmergicSwarm",
    "PheromoneTrail",
    "ZeroKnowledgeProof",
    "AffectiveComputing",
    "EmotionalState",
    "InterventionEngine",
    "Hypothesis",
    "InfiniteContext",
    "CompressedChunk",
]
