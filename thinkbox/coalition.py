"""ThinkBox Coalition Protocol — Multi-agent shared memory and collaboration.

Features:
1. AgentCoalitionProtocol — CRDT-based shared memory pool
2. TaskDelegationMarket — Reputation-token bidding system
3. SharedContextBus — Real-time pub/sub message bus
4. AgentCapabilityRegistry — Dynamic specialization discovery
5. CoalitionGovernance — Democratic protocol upgrade voting
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable


class CRDTOperationType(str, Enum):
    SET = "set"
    DELETE = "delete"
    MERGE = "merge"
    INCREMENT = "increment"


@dataclass
class CRDTRecord:
    key: str
    value: Any
    timestamp: float
    vector_clock: dict[str, int]
    operation: CRDTOperationType
    agent_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "value": self.value,
            "timestamp": self.timestamp,
            "vector_clock": self.vector_clock,
            "operation": self.operation.value,
            "agent_id": self.agent_id,
        }


class CrdtSharedMemory:
    def __init__(self) -> None:
        self._store: dict[str, CRDTRecord] = {}
        self._lock = threading.Lock()
        self._subscribers: list[Callable[[CRDTRecord], None]] = []

    def set(self, key: str, value: Any, agent_id: str, vector_clock: dict[str, int] | None = None) -> CRDTRecord:
        with self._lock:
            vc = vector_clock or {agent_id: int(time.time() * 1000)}
            record = CRDTRecord(
                key=key,
                value=value,
                timestamp=time.time(),
                vector_clock=vc,
                operation=CRDTOperationType.SET,
                agent_id=agent_id,
            )
            if key in self._store:
                existing = self._store[key]
                if self._happens_before(existing.vector_clock, vc):
                    self._store[key] = record
                else:
                    merged_value = self._merge_values(existing.value, value)
                    merged_clock = self._merge_clocks(existing.vector_clock, vc)
                    record.value = merged_value
                    record.vector_clock = merged_clock
                    self._store[key] = record
            else:
                self._store[key] = record

            for cb in self._subscribers:
                try:
                    cb(record)
                except Exception:
                    pass

            return record

    def get(self, key: str) -> Any:
        with self._lock:
            record = self._store.get(key)
            return record.value if record else None

    def get_all(self) -> dict[str, Any]:
        with self._lock:
            return {k: v.value for k, v in self._store.items()}

    def subscribe(self, callback: Callable[[CRDTRecord], None]) -> None:
        self._subscribers.append(callback)

    def _happens_before(self, a: dict[str, int], b: dict[str, int]) -> bool:
        for k, v in a.items():
            if b.get(k, 0) < v:
                return False
        return True

    def _merge_values(self, a: Any, b: Any) -> Any:
        if isinstance(a, dict) and isinstance(b, dict):
            merged = {**a, **b}
            return merged
        return b

    def _merge_clocks(self, a: dict[str, int], b: dict[str, int]) -> dict[str, int]:
        merged = {}
        all_keys = set(a.keys()) | set(b.keys())
        for k in all_keys:
            merged[k] = max(a.get(k, 0), b.get(k, 0))
        return merged


@dataclass
class TaskBid:
    task_id: str
    agent_id: str
    bid_amount: int
    reputation_at_bid: float
    timestamp: str
    estimated_completion_ms: float


class TaskDelegationMarket:
    def __init__(self) -> None:
        self._tasks: dict[str, dict[str, Any]] = {}
        self._bids: dict[str, list[TaskBid]] = {}
        self._lock = threading.Lock()

    def list_task(self, task_id: str, description: str, min_reputation: float = 0.0, reward: int = 100) -> None:
        with self._lock:
            self._tasks[task_id] = {
                "id": task_id,
                "description": description,
                "min_reputation": min_reputation,
                "reward": reward,
                "status": "open",
                "winner": None,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            self._bids[task_id] = []

    def place_bid(self, task_id: str, agent_id: str, bid_amount: int, reputation: float, estimated_ms: float) -> bool:
        with self._lock:
            task = self._tasks.get(task_id)
            if not task or task["status"] != "open":
                return False
            if reputation < task["min_reputation"]:
                return False

            bid = TaskBid(
                task_id=task_id,
                agent_id=agent_id,
                bid_amount=bid_amount,
                reputation_at_bid=reputation,
                timestamp=datetime.now(timezone.utc).isoformat(),
                estimated_completion_ms=estimated_ms,
            )
            self._bids[task_id].append(bid)
            return True

    def select_winner(self, task_id: str) -> str | None:
        with self._lock:
            bids = self._bids.get(task_id, [])
            if not bids:
                return None

            task = self._tasks[task_id]
            valid_bids = [b for b in bids if b.bid_amount <= task["reward"]]
            if not valid_bids:
                valid_bids = bids

            weighted_bids = sorted(
                valid_bids,
                key=lambda b: (b.reputation_at_bid * 0.6) + ((task["reward"] - b.bid_amount) * 0.4),
                reverse=True,
            )

            winner = weighted_bids[0]
            task["winner"] = winner.agent_id
            task["status"] = "assigned"
            return winner.agent_id

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        return self._tasks.get(task_id)

    def get_open_tasks(self) -> list[dict[str, Any]]:
        return [t for t in self._tasks.values() if t["status"] == "open"]


@dataclass
class BusMessage:
    topic: str
    payload: dict[str, Any]
    sender: str
    timestamp: str
    message_id: str = ""

    def __post_init__(self) -> None:
        if not self.message_id:
            self.message_id = f"msg_{uuid.uuid4().hex[:12]}"


class SharedContextBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, list[Callable[[BusMessage], None]]] = {}
        self._history: list[BusMessage] = []
        self._lock = threading.Lock()

    def publish(self, topic: str, payload: dict[str, Any], sender: str = "system") -> BusMessage:
        message = BusMessage(
            topic=topic,
            payload=payload,
            sender=sender,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        with self._lock:
            self._history.append(message)
            subscribers = self._subscribers.get(topic, []).copy()

        for cb in subscribers:
            try:
                if asyncio.iscoroutinefunction(cb):
                    asyncio.create_task(cb(message))
                else:
                    cb(message)
            except Exception:
                pass

        return message

    def subscribe(self, topic: str, callback: Callable[[BusMessage], None]) -> None:
        with self._lock:
            if topic not in self._subscribers:
                self._subscribers[topic] = []
            self._subscribers[topic].append(callback)

    def get_history(self, topic: str | None = None, limit: int = 100) -> list[BusMessage]:
        with self._lock:
            messages = self._history
            if topic:
                messages = [m for m in messages if m.topic == topic]
            return messages[-limit:]


@dataclass
class AgentCapability:
    agent_id: str
    specialization: str
    reputation: float
    tasks_completed: int
    average_latency_ms: float
    metadata: dict[str, Any] = field(default_factory=dict)


class AgentCapabilityRegistry:
    def __init__(self) -> None:
        self._agents: dict[str, AgentCapability] = {}
        self._lock = threading.Lock()

    def register(self, agent_id: str, specialization: str, metadata: dict[str, Any] | None = None) -> None:
        with self._lock:
            if agent_id in self._agents:
                self._agents[agent_id].specialization = specialization
                if metadata:
                    self._agents[agent_id].metadata.update(metadata)
            else:
                self._agents[agent_id] = AgentCapability(
                    agent_id=agent_id,
                    specialization=specialization,
                    reputation=1.0,
                    tasks_completed=0,
                    average_latency_ms=0.0,
                    metadata=metadata or {},
                )

    def update_performance(self, agent_id: str, latency_ms: float, success: bool) -> None:
        with self._lock:
            agent = self._agents.get(agent_id)
            if not agent:
                return
            agent.tasks_completed += 1
            total_time = agent.average_latency_ms * (agent.tasks_completed - 1) + latency_ms
            agent.average_latency_ms = total_time / agent.tasks_completed
            if success:
                agent.reputation = min(10.0, agent.reputation + 0.1)
            else:
                agent.reputation = max(0.0, agent.reputation - 0.5)

    def find_best_agent(self, specialization: str) -> str | None:
        with self._lock:
            matching = [a for a in self._agents.values() if a.specialization == specialization]
            if not matching:
                return None
            return max(matching, key=lambda a: a.reputation).agent_id

    def get_all_agents(self) -> list[AgentCapability]:
        return list(self._agents.values())


@dataclass
class GovernanceProposal:
    proposal_id: str
    title: str
    description: str
    proposer: str
    votes_for: int = 0
    votes_against: int = 0
    status: str = "active"
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()


class CoalitionGovernance:
    def __init__(self, quorum: float = 0.5) -> None:
        self._proposals: dict[str, GovernanceProposal] = {}
        self._votes: dict[str, dict[str, bool]] = {}
        self._quorum = quorum
        self._lock = threading.Lock()

    def propose(self, title: str, description: str, proposer: str) -> str:
        proposal_id = f"prop_{uuid.uuid4().hex[:8]}"
        with self._lock:
            self._proposals[proposal_id] = GovernanceProposal(
                proposal_id=proposal_id,
                title=title,
                description=description,
                proposer=proposer,
            )
            self._votes[proposal_id] = {}
        return proposal_id

    def vote(self, proposal_id: str, agent_id: str, support: bool) -> bool:
        with self._lock:
            proposal = self._proposals.get(proposal_id)
            if not proposal or proposal.status != "active":
                return False
            self._votes[proposal_id][agent_id] = support
            return True

    def tally(self, proposal_id: str, total_agents: int) -> str:
        with self._lock:
            proposal = self._proposals.get(proposal_id)
            if not proposal:
                return "not_found"

            votes = self._votes.get(proposal_id, {})
            proposal.votes_for = sum(1 for v in votes.values() if v)
            proposal.votes_against = sum(1 for v in votes.values() if not v)

            participation = len(votes) / total_agents if total_agents > 0 else 0
            if participation < self._quorum:
                return "pending"

            if proposal.votes_for > proposal.votes_against:
                proposal.status = "passed"
            else:
                proposal.status = "rejected"

            return proposal.status

    def get_proposal(self, proposal_id: str) -> GovernanceProposal | None:
        return self._proposals.get(proposal_id)


class AgentCoalitionProtocol:
    def __init__(self) -> None:
        self.shared_memory = CrdtSharedMemory()
        self.task_market = TaskDelegationMarket()
        self.context_bus = SharedContextBus()
        self.capability_registry = AgentCapabilityRegistry()
        self.governance = CoalitionGovernance()

    def register_agent(self, agent_id: str, specialization: str, metadata: dict[str, Any] | None = None) -> None:
        self.capability_registry.register(agent_id, specialization, metadata)
        self.context_bus.publish("agent/registered", {
            "agent_id": agent_id,
            "specialization": specialization,
        })

    def submit_task(self, task_id: str, description: str, reward: int = 100) -> None:
        self.task_market.list_task(task_id, description, reward=reward)
        self.context_bus.publish("task/listed", {
            "task_id": task_id,
            "description": description,
            "reward": reward,
        })

    def assign_task(self, task_id: str) -> str | None:
        winner = self.task_market.select_winner(task_id)
        if winner:
            self.context_bus.publish("task/assigned", {
                "task_id": task_id,
                "winner": winner,
            })
        return winner
