"""ThinkBox Reward Economy — Internal currency and contribution mining.

Features:
16. AgentTokenEconomy — Internal currency for agent contributions
17. ContributionMining — Reward agents for useful outputs
18. StakingMechanism — Stake tokens to claim high-value tasks
19. SlashConditions — Penalty system for poor performance
20. TreasuryGovernance — Decentralized resource management
"""

from __future__ import annotations

import hashlib
import json
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class TokenAccount:
    agent_id: str
    balance: int = 100
    staked: int = 0
    mined: int = 0
    slashed: int = 0
    reputation: float = 1.0


@dataclass
class Transaction:
    tx_id: str
    from_agent: str
    to_agent: str
    amount: int
    reason: str
    timestamp: str
    signature: str = ""


class AgentTokenEconomy:
    def __init__(self, initial_supply: int = 10000) -> None:
        self._accounts: dict[str, TokenAccount] = {}
        self._transactions: list[Transaction] = []
        self._total_supply = initial_supply
        self._lock = threading.Lock()

    def create_account(self, agent_id: str, initial_balance: int = 100) -> TokenAccount:
        with self._lock:
            if agent_id not in self._accounts:
                self._accounts[agent_id] = TokenAccount(
                    agent_id=agent_id,
                    balance=initial_balance,
                )
            return self._accounts[agent_id]

    def transfer(self, from_agent: str, to_agent: str, amount: int, reason: str = "") -> bool:
        with self._lock:
            from_acc = self._accounts.get(from_agent)
            if not from_acc or from_acc.balance < amount:
                return False

            if to_agent not in self._accounts:
                self.create_account(to_agent)

            from_acc.balance -= amount
            self._accounts[to_agent].balance += amount

            tx = Transaction(
                tx_id=f"tx_{uuid.uuid4().hex[:12]}",
                from_agent=from_agent,
                to_agent=to_agent,
                amount=amount,
                reason=reason,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
            self._transactions.append(tx)
            return True

    def get_balance(self, agent_id: str) -> int:
        account = self._accounts.get(agent_id)
        return account.balance if account else 0

    def get_all_accounts(self) -> list[TokenAccount]:
        return list(self._accounts.values())


class ContributionMining:
    def __init__(self, economy: AgentTokenEconomy) -> None:
        self._economy = economy
        self._rewards: dict[str, int] = {
            "task_complete": 10,
            "bug_fix": 25,
            "code_review": 15,
            "documentation": 5,
            "speculative_success": 8,
            "consensus_participation": 3,
        }

    def mine(self, agent_id: str, contribution_type: str, quality_multiplier: float = 1.0) -> int:
        base_reward = self._rewards.get(contribution_type, 5)
        reward = int(base_reward * quality_multiplier)

        self._economy.create_account(agent_id)
        self._economy.transfer("treasury", agent_id, reward, f"mining_{contribution_type}")
        return reward

    def get_reward_rate(self, contribution_type: str) -> int:
        return self._rewards.get(contribution_type, 5)


class StakingMechanism:
    def __init__(self, economy: AgentTokenEconomy) -> None:
        self._economy = economy
        self._stakes: dict[str, dict[str, int]] = {}

    def stake(self, agent_id: str, task_id: str, amount: int) -> bool:
        balance = self._economy.get_balance(agent_id)
        if balance < amount:
            return False

        if task_id not in self._stakes:
            self._stakes[task_id] = {}

        self._stakes[task_id][agent_id] = amount
        return True

    def get_stake(self, task_id: str, agent_id: str) -> int:
        return self._stakes.get(task_id, {}).get(agent_id, 0)

    def release_stake(self, task_id: str, agent_id: str) -> int:
        amount = self._stakes.get(task_id, {}).pop(agent_id, 0)
        return amount

    def get_task_stakes(self, task_id: str) -> dict[str, int]:
        return self._stakes.get(task_id, {})


class SlashConditions:
    def __init__(self, economy: AgentTokenEconomy) -> None:
        self._economy = economy
        self._penalties: dict[str, int] = {
            "task_failure": 5,
            "timeout": 10,
            "malicious_output": 50,
            "consensus_abstain": 2,
        }

    def slash(self, agent_id: str, reason: str) -> int:
        penalty = self._penalties.get(reason, 5)
        balance = self._economy.get_balance(agent_id)
        actual_penalty = min(penalty, balance)

        if actual_penalty > 0:
            self._economy.transfer(agent_id, "treasury", actual_penalty, f"slash_{reason}")
        return actual_penalty

    def get_penalty(self, reason: str) -> int:
        return self._penalties.get(reason, 5)


class TreasuryGovernance:
    def __init__(self, economy: AgentTokenEconomy) -> None:
        self._economy = economy
        self._allocations: dict[str, int] = {}
        self._proposals: list[dict[str, Any]] = []

    def allocate(self, category: str, amount: int) -> bool:
        treasury_balance = self._economy.get_balance("treasury")
        if treasury_balance < amount:
            return False

        self._allocations[category] = self._allocations.get(category, 0) + amount
        return True

    def get_allocation(self, category: str) -> int:
        return self._allocations.get(category, 0)

    def submit_proposal(self, title: str, amount: int, proposer: str) -> str:
        proposal_id = f"treasury_{uuid.uuid4().hex[:8]}"
        self._proposals.append({
            "id": proposal_id,
            "title": title,
            "amount": amount,
            "proposer": proposer,
            "status": "pending",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        return proposal_id

    def get_treasury_balance(self) -> int:
        return self._economy.get_balance("treasury")
