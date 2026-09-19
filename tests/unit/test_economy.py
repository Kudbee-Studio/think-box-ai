"""Unit tests for thinkbox.economy — token economy, contribution mining, staking, slash, treasury."""

import unittest

from thinkbox.economy import (
    TokenAccount,
    Transaction,
    AgentTokenEconomy,
    ContributionMining,
    StakingMechanism,
    SlashConditions,
    TreasuryGovernance,
)


class TestTokenAccount(unittest.TestCase):
    def test_default(self) -> None:
        account = TokenAccount(agent_id="agent1")
        self.assertEqual(account.balance, 100)
        self.assertEqual(account.staked, 0)
        self.assertEqual(account.mined, 0)
        self.assertEqual(account.slashed, 0)
        self.assertEqual(account.reputation, 1.0)

    def test_custom_initial(self) -> None:
        account = TokenAccount(agent_id="a", balance=500, staked=100)
        self.assertEqual(account.balance, 500)
        self.assertEqual(account.staked, 100)


class TestAgentTokenEconomy(unittest.TestCase):
    def setUp(self) -> None:
        self.economy = AgentTokenEconomy(initial_supply=10000)

    def test_create_account(self) -> None:
        account = self.economy.create_account("agent1")
        self.assertEqual(account.agent_id, "agent1")
        self.assertEqual(account.balance, 100)

    def test_create_account_existing(self) -> None:
        self.economy.create_account("agent1")
        account = self.economy.create_account("agent1")
        self.assertEqual(account.balance, 100)

    def test_create_account_custom_balance(self) -> None:
        account = self.economy.create_account("agent1", initial_balance=500)
        self.assertEqual(account.balance, 500)

    def test_transfer(self) -> None:
        self.economy.create_account("alice")
        self.economy.create_account("bob")
        result = self.economy.transfer("alice", "bob", 50, "payment")
        self.assertTrue(result)
        self.assertEqual(self.economy.get_balance("alice"), 50)
        self.assertEqual(self.economy.get_balance("bob"), 150)

    def test_transfer_insufficient_funds(self) -> None:
        self.economy.create_account("alice", initial_balance=10)
        self.economy.create_account("bob")
        result = self.economy.transfer("alice", "bob", 50, "payment")
        self.assertFalse(result)
        self.assertEqual(self.economy.get_balance("alice"), 10)

    def test_transfer_unknown_sender(self) -> None:
        self.economy.create_account("bob")
        result = self.economy.transfer("unknown", "bob", 10, "payment")
        self.assertFalse(result)

    def test_get_balance_unknown(self) -> None:
        self.assertEqual(self.economy.get_balance("unknown"), 0)

    def test_get_all_accounts(self) -> None:
        self.economy.create_account("a1")
        self.economy.create_account("a2")
        accounts = self.economy.get_all_accounts()
        self.assertEqual(len(accounts), 2)

    def test_transaction_created(self) -> None:
        self.economy.create_account("alice")
        self.economy.create_account("bob")
        self.economy.transfer("alice", "bob", 30, "test")
        txs = self.economy._transactions
        self.assertEqual(len(txs), 1)
        self.assertEqual(txs[0].from_agent, "alice")
        self.assertEqual(txs[0].to_agent, "bob")
        self.assertEqual(txs[0].amount, 30)


class TestContributionMining(unittest.TestCase):
    def setUp(self) -> None:
        self.economy = AgentTokenEconomy()
        self.mining = ContributionMining(self.economy)

    def test_mine_task_complete(self) -> None:
        reward = self.mining.mine("agent1", "task_complete")
        self.assertEqual(reward, 10)
        self.assertEqual(self.economy.get_balance("agent1"), 110)

    def test_mine_bug_fix(self) -> None:
        reward = self.mining.mine("agent1", "bug_fix")
        self.assertEqual(reward, 25)

    def test_mine_quality_multiplier(self) -> None:
        reward = self.mining.mine("agent1", "task_complete", quality_multiplier=2.0)
        self.assertEqual(reward, 20)

    def test_mine_unknown_type(self) -> None:
        reward = self.mining.mine("agent1", "unknown")
        self.assertEqual(reward, 5)

    def test_mine_creates_account(self) -> None:
        self.mining.mine("new_agent", "task_complete")
        self.assertEqual(self.economy.get_balance("new_agent"), 110)

    def test_get_reward_rate(self) -> None:
        self.assertEqual(self.mining.get_reward_rate("task_complete"), 10)
        self.assertEqual(self.mining.get_reward_rate("unknown"), 5)


class TestStakingMechanism(unittest.TestCase):
    def setUp(self) -> None:
        self.economy = AgentTokenEconomy()
        self.staking = StakingMechanism(self.economy)

    def test_stake(self) -> None:
        result = self.staking.stake("agent1", "task1", 50)
        self.assertTrue(result)

    def test_stake_insufficient(self) -> None:
        result = self.staking.stake("agent1", "task1", 200)
        self.assertFalse(result)

    def test_get_stake(self) -> None:
        self.staking.stake("agent1", "task1", 50)
        self.assertEqual(self.staking.get_stake("task1", "agent1"), 50)

    def test_get_stake_none(self) -> None:
        self.assertEqual(self.staking.get_stake("task1", "agent1"), 0)

    def test_release_stake(self) -> None:
        self.staking.stake("agent1", "task1", 50)
        released = self.staking.release_stake("task1", "agent1")
        self.assertEqual(released, 50)
        self.assertEqual(self.staking.get_stake("task1", "agent1"), 0)

    def test_get_task_stakes(self) -> None:
        self.staking.stake("a1", "task1", 30)
        self.staking.stake("a2", "task1", 40)
        stakes = self.staking.get_task_stakes("task1")
        self.assertEqual(len(stakes), 2)
        self.assertEqual(stakes["a1"], 30)


class TestSlashConditions(unittest.TestCase):
    def setUp(self) -> None:
        self.economy = AgentTokenEconomy()
        self.slash = SlashConditions(self.economy)

    def test_slash_task_failure(self) -> None:
        self.economy.create_account("agent1", initial_balance=100)
        penalty = self.slash.slash("agent1", "task_failure")
        self.assertEqual(penalty, 5)
        self.assertEqual(self.economy.get_balance("agent1"), 95)

    def test_slash_timeout(self) -> None:
        self.economy.create_account("agent1", initial_balance=100)
        penalty = self.slash.slash("agent1", "timeout")
        self.assertEqual(penalty, 10)

    def test_slash_malicious(self) -> None:
        self.economy.create_account("agent1", initial_balance=100)
        penalty = self.slash.slash("agent1", "malicious_output")
        self.assertEqual(penalty, 50)

    def test_slash_insufficient_balance(self) -> None:
        self.economy.create_account("agent1", initial_balance=3)
        penalty = self.slash.slash("agent1", "task_failure")
        self.assertEqual(penalty, 3)
        self.assertEqual(self.economy.get_balance("agent1"), 0)

    def test_get_penalty(self) -> None:
        self.assertEqual(self.slash.get_penalty("task_failure"), 5)
        self.assertEqual(self.slash.get_penalty("unknown"), 5)


class TestTreasuryGovernance(unittest.TestCase):
    def setUp(self) -> None:
        self.economy = AgentTokenEconomy()
        self.economy.create_account("treasury", initial_balance=1000)
        self.treasury = TreasuryGovernance(self.economy)

    def test_allocate(self) -> None:
        result = self.treasury.allocate("research", 100)
        self.assertTrue(result)
        self.assertEqual(self.treasury.get_allocation("research"), 100)

    def test_allocate_insufficient(self) -> None:
        result = self.treasury.allocate("research", 5000)
        self.assertFalse(result)

    def test_submit_proposal(self) -> None:
        proposal_id = self.treasury.submit_proposal("Build feature X", 200, "agent1")
        self.assertIsNotNone(proposal_id)

    def test_get_treasury_balance(self) -> None:
        self.assertEqual(self.treasury.get_treasury_balance(), 1000)
