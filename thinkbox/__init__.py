"""ThinkBox AI — Core execution engine package.

Sub-packages:
  - legendary/: zero-to-one cognitive innovations (Phase 12 prefix)
  - production/: availability, reliability, observability
  - autonomous/: self-tuning, canary, chaos, migration
  - control fabric: identity, tokens, admission, workspaces, mesh, ledger
"""

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
from .production import (
    HealthCheckSystem,
    HealthStatus,
    MetricsCollector,
    GracefulShutdown,
    ConfigValidation,
    ValidatedConfig,
    ErrorRecovery,
    CircuitBreaker,
    RequestDeduplication,
    Tracing,
    Span,
    RateLimiter,
    TokenBucket,
    SlidingWindow,
    LoadBalancer,
    Backend,
    AlertManager,
    AlertSeverity,
    Alert,
)
from .identity import IdentityLedger, AgentIdentity
from .governance_token import GovernanceTokenService, GovernanceToken, TokenRequest
from .admission import AdmissionGate, AdmissionDecision
from .workspace import WorkspaceRegistry, WorkspaceStore, ThinkBox
from .handoff import ThinkBoxHandoff, HandoffRecord
from .occupancy import OccupancyMonitor, MeshCellManager, MeshCell
from .capacity import CapacityController, CapacityDecision
from .ledger import ActionLedger, LedgerEntry
from .thinktrace import ThinkTraceCapture, ThinkTrace
from .governed import GovernedEngine, GovernedEngineConfig
from .substrate import (
    detect_substrate,
    bind_think_box,
    SubstrateProbe,
    SubstrateReport,
    IsolationProbe,
    ThinkBoxVectorSync,
)
from .disruptor import DisruptorPass, DisruptorResult, DisruptorSuite
from .reasoning import (
    ReasoningNormalizer,
    ReasoningChunk,
    NormalizedCompletion,
    capture_completion,
)
from .burst import (
    BurstConfig,
    BurstBudget,
    BurstReport,
    BurstRunner,
    LiveVLLMClient,
    synthetic_model,
)
from .grounding import GroundingScorer, GroundingScore
from .factcards import FactCard, FactCardRegistry
from .harvest import HarvestReplay, HarvestReport, HarvestMetrics
from .verifier import (
    Verifier,
    EvalHarness,
    VerificationMetrics,
    VerificationReport,
    build_eval_fabric,
    standard_passes,
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
    "HealthCheckSystem",
    "HealthStatus",
    "MetricsCollector",
    "GracefulShutdown",
    "ConfigValidation",
    "ValidatedConfig",
    "ErrorRecovery",
    "CircuitBreaker",
    "RequestDeduplication",
    "Tracing",
    "Span",
    "RateLimiter",
    "TokenBucket",
    "SlidingWindow",
    "LoadBalancer",
    "Backend",
    "AlertManager",
    "AlertSeverity",
    "Alert",
    "IdentityLedger",
    "AgentIdentity",
    "GovernanceTokenService",
    "GovernanceToken",
    "TokenRequest",
    "AdmissionGate",
    "AdmissionDecision",
    "WorkspaceRegistry",
    "WorkspaceStore",
    "ThinkBox",
    "ThinkBoxHandoff",
    "HandoffRecord",
    "OccupancyMonitor",
    "MeshCellManager",
    "MeshCell",
    "CapacityController",
    "CapacityDecision",
    "ActionLedger",
    "LedgerEntry",
    "ThinkTraceCapture",
    "ThinkTrace",
    "GovernedEngine",
    "GovernedEngineConfig",
    "detect_substrate",
    "bind_think_box",
    "SubstrateProbe",
    "SubstrateReport",
    "IsolationProbe",
    "ThinkBoxVectorSync",
    "DisruptorPass",
    "DisruptorResult",
    "DisruptorSuite",
    "ReasoningNormalizer",
    "ReasoningChunk",
    "NormalizedCompletion",
    "capture_completion",
    "BurstConfig",
    "BurstBudget",
    "BurstReport",
    "BurstRunner",
    "LiveVLLMClient",
    "synthetic_model",
    "GroundingScorer",
    "GroundingScore",
    "FactCard",
    "FactCardRegistry",
    "HarvestReplay",
    "HarvestReport",
    "HarvestMetrics",
    "Verifier",
    "EvalHarness",
    "VerificationMetrics",
    "VerificationReport",
    "build_eval_fabric",
    "standard_passes",
]
