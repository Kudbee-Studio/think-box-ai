"""
KILO Distributed Governance — Raft-based Distributed Admission Gate.

Implements a cluster-wide admission gate using Raft consensus for linearizable decisions.
"""

import asyncio
import time
import hashlib
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Awaitable
from enum import Enum
from collections import deque

logger = logging.getLogger(__name__)


class RaftState(Enum):
    FOLLOWER = "FOLLOWER"
    CANDIDATE = "CANDIDATE"
    LEADER = "LEADER"


@dataclass
class LogEntry:
    term: int
    index: int
    command: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)
    applied: bool = False


@dataclass
class VoteRequest:
    term: int
    candidate_id: str
    last_log_index: int
    last_log_term: int


@dataclass
class VoteResponse:
    term: int
    vote_granted: bool


@dataclass
class AppendEntriesRequest:
    term: int
    leader_id: str
    prev_log_index: int
    prev_log_term: int
    entries: List[LogEntry]
    leader_commit: int


@dataclass
class AppendEntriesResponse:
    term: int
    success: bool
    match_index: int = 0


@dataclass
class AdmissionRequest:
    request_id: str
    agent_id: str
    task_id: Optional[str]
    action_type: str
    action_spec: Dict[str, Any]
    governance_token: Optional[str]
    tenant_id: str
    timestamp: str


@dataclass
class AdmissionDecision:
    decision_id: str
    allowed: bool
    reason: str
    conditions: List[Dict[str, Any]]
    expires_at: Optional[str]
    governance_token: Optional[str]
    term: int
    index: int


class DistributedAdmissionGate:
    """
    Raft-based distributed admission gate.
    
    Provides linearizable admission decisions across a cluster of nodes.
    All admission requests go through Raft log replication for consistency.
    """

    def __init__(
        self,
        node_id: str,
        cluster_nodes: List[str],
        policy_evaluator: Callable[[Dict[str, Any]], Awaitable[bool]],
        election_timeout_min: float = 1.5,
        election_timeout_max: float = 3.0,
        heartbeat_interval: float = 0.5,
    ):
        self.node_id = node_id
        self.cluster_nodes = cluster_nodes
        self.policy_evaluator = policy_evaluator
        self.election_timeout_min = election_timeout_min
        self.election_timeout_max = election_timeout_max
        self.heartbeat_interval = heartbeat_interval

        # Raft state
        self.state = RaftState.FOLLOWER
        self.current_term = 0
        self.voted_for: Optional[str] = None
        self.log: List[LogEntry] = []
        self.commit_index = 0
        self.last_applied = 0

        # Leader state
        self.next_index: Dict[str, int] = {}
        self.match_index: Dict[str, int] = {}

        # Timing
        self.last_contact = time.time()
        self.election_deadline = self._random_election_timeout()

        # Admission queue
        self._pending_requests: deque = deque()
        self._decision_futures: Dict[str, asyncio.Future] = {}

        # Background tasks
        self._running = False
        self._raft_task: Optional[asyncio.Task] = None
        self._apply_task: Optional[asyncio.Task] = None

    def _random_election_timeout(self) -> float:
        import random
        return time.time() + random.uniform(self.election_timeout_min, self.election_timeout_max)

    async def start(self):
        """Start the Raft node."""
        self._running = True
        self._raft_task = asyncio.create_task(self._raft_loop())
        self._apply_task = asyncio.create_task(self._apply_loop())
        logger.info(f"DistributedAdmissionGate {self.node_id} started as {self.state.value}")

    async def stop(self):
        """Stop the Raft node."""
        self._running = False
        if self._raft_task:
            self._raft_task.cancel()
        if self._apply_task:
            self._apply_task.cancel()
        logger.info(f"DistributedAdmissionGate {self.node_id} stopped")

    async def check_admission(self, request: AdmissionRequest) -> AdmissionDecision:
        """
        Submit admission request to Raft cluster.
        
        Only leader can process requests; followers redirect.
        """
        if self.state != RaftState.LEADER:
            # Redirect to leader (in real impl, would forward RPC)
            leader_id = self._get_leader_id()
            raise RedirectToLeaderError(leader_id)

        # Create log entry for admission request
        entry = LogEntry(
            term=self.current_term,
            index=len(self.log),
            command={
                "type": "admission_request",
                "request": {
                    "request_id": request.request_id,
                    "agent_id": request.agent_id,
                    "task_id": request.task_id,
                    "action_type": request.action_type,
                    "action_spec": request.action_spec,
                    "governance_token": request.governance_token,
                    "tenant_id": request.tenant_id,
                    "timestamp": request.timestamp,
                }
            }
        )

        self.log.append(entry)
        
        # Create future for decision
        future = asyncio.Future()
        self._decision_futures[request.request_id] = future

        # Replicate to followers (simplified - real impl uses RPC)
        await self._replicate_log()

        # Wait for commitment and decision
        try:
            decision = await asyncio.wait_for(future, timeout=10.0)
            return decision
        except asyncio.TimeoutError:
            logger.error(f"Admission request {request.request_id} timed out")
            return AdmissionDecision(
                decision_id=request.request_id,
                allowed=False,
                reason="Admission timeout",
                conditions=[],
                expires_at=None,
                governance_token=None,
                term=self.current_term,
                index=entry.index,
            )

    async def _replicate_log(self):
        """Replicate log entries to followers."""
        # In real implementation, this would send AppendEntries RPCs
        # to all followers and wait for quorum
        # For now, simulate local commit
        self.commit_index = len(self.log) - 1

    async def _apply_loop(self):
        """Apply committed log entries to state machine."""
        while self._running:
            try:
                while self.last_applied < self.commit_index:
                    self.last_applied += 1
                    entry = self.log[self.last_applied]
                    await self._apply_entry(entry)
                await asyncio.sleep(0.1)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Apply loop error: {e}")
                await asyncio.sleep(1)

    async def _apply_entry(self, entry: LogEntry):
        """Apply a committed log entry."""
        if entry.command.get("type") == "admission_request":
            req_data = entry.command["request"]
            request_id = req_data["request_id"]
            
            # Evaluate policy
            try:
                allowed = await self.policy_evaluator({
                    "action_type": req_data["action_type"],
                    "agent_id": req_data["agent_id"],
                    "task_id": req_data.get("task_id"),
                    "action_spec": req_data["action_spec"],
                    "tenant_id": req_data["tenant_id"],
                    "governance_token": req_data.get("governance_token"),
                })
                
                decision = AdmissionDecision(
                    decision_id=request_id,
                    allowed=allowed,
                    reason="Policy allow" if allowed else "Policy deny",
                    conditions=[],
                    expires_at=None,
                    governance_token=self._issue_token(req_data) if allowed else None,
                    term=entry.term,
                    index=entry.index,
                )
            except Exception as e:
                logger.error(f"Policy evaluation error: {e}")
                decision = AdmissionDecision(
                    decision_id=request_id,
                    allowed=False,
                    reason=f"Evaluation error: {e}",
                    conditions=[],
                    expires_at=None,
                    governance_token=None,
                    term=entry.term,
                    index=entry.index,
                )

            # Resolve future
            if request_id in self._decision_futures:
                self._decision_futures[request_id].set_result(decision)
                del self._decision_futures[request_id]

    def _issue_token(self, req_data: Dict[str, Any]) -> str:
        """Issue governance token (simplified)."""
        import jwt
        payload = {
            "agent_id": req_data["agent_id"],
            "task_id": req_data.get("task_id"),
            "action_type": req_data["action_type"],
            "exp": int(time.time()) + 300,
            "nonce": hashlib.sha256(f"{req_data['request_id']}{time.time()}".encode()).hexdigest()[:16],
        }
        return jwt.encode(payload, "secret", algorithm="HS256")

    def _get_leader_id(self) -> Optional[str]:
        """Get current leader ID."""
        # In real impl, would track leader from Raft
        return None

    async def _raft_loop(self):
        """Main Raft loop for leader election and heartbeats."""
        while self._running:
            try:
                if self.state == RaftState.LEADER:
                    await self._send_heartbeats()
                    await asyncio.sleep(self.heartbeat_interval)
                else:
                    await self._check_election_timeout()
                    await asyncio.sleep(0.1)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Raft loop error: {e}")
                await asyncio.sleep(1)

    async def _send_heartbeats(self):
        """Send heartbeats to all followers."""
        # In real impl, send AppendEntries with empty entries
        pass

    async def _check_election_timeout(self):
        """Check if election timeout has passed."""
        if time.time() > self.election_deadline:
            await self._start_election()

    async def _start_election(self):
        """Start leader election."""
        self.state = RaftState.CANDIDATE
        self.current_term += 1
        self.voted_for = self.node_id
        self.election_deadline = self._random_election_timeout()

        # Request votes from other nodes
        votes = 1  # Vote for self
        for node_id in self.cluster_nodes:
            if node_id == self.node_id:
                continue
            # In real impl, send RequestVote RPC
            # vote = await self._request_vote(node_id)
            # if vote.vote_granted:
            #     votes += 1

        # Simplified: become leader if we're the only node or first
        if votes > len(self.cluster_nodes) // 2:
            await self._become_leader()

    async def _become_leader(self):
        """Become leader."""
        self.state = RaftState.LEADER
        self.next_index = {nid: len(self.log) for nid in self.cluster_nodes if nid != self.node_id}
        self.match_index = {nid: 0 for nid in self.cluster_nodes if nid != self.node_id}
        logger.info(f"Node {self.node_id} became leader for term {self.current_term}")


class RedirectToLeaderError(Exception):
    def __init__(self, leader_id: Optional[str]):
        self.leader_id = leader_id
        super().__init__(f"Redirect to leader: {leader_id}")


# ============================================================
# Factory and Configuration
# ============================================================

@dataclass
class DistributedAdmissionConfig:
    node_id: str
    cluster_nodes: List[str]
    election_timeout_min: float = 1.5
    election_timeout_max: float = 3.0
    heartbeat_interval: float = 0.5


async def create_distributed_admission_gate(
    config: DistributedAdmissionConfig,
    policy_evaluator: Callable[[Dict[str, Any]], Awaitable[bool]],
) -> DistributedAdmissionGate:
    """Create and start a distributed admission gate."""
    gate = DistributedAdmissionGate(
        node_id=config.node_id,
        cluster_nodes=config.cluster_nodes,
        policy_evaluator=policy_evaluator,
        election_timeout_min=config.election_timeout_min,
        election_timeout_max=config.election_timeout_max,
        heartbeat_interval=config.heartbeat_interval,
    )
    await gate.start()
    return gate