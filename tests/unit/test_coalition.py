"""Unit tests for thinkbox.coalition — CRDT shared memory, task market, pub/sub, capability registry, governance."""

import threading
import time
import unittest

from thinkbox.coalition import (
    CRDTOperationType,
    CRDTRecord,
    CrdtSharedMemory,
    TaskBid,
    TaskDelegationMarket,
    BusMessage,
    SharedContextBus,
    AgentCapability,
    AgentCapabilityRegistry,
    GovernanceProposal,
    CoalitionGovernance,
)


class TestCRDTRecord(unittest.TestCase):
    def test_to_dict(self) -> None:
        record = CRDTRecord(
            key="test", value="data", timestamp=12345.0,
            vector_clock={"a": 1}, operation=CRDTOperationType.SET, agent_id="agent1",
        )
        d = record.to_dict()
        self.assertEqual(d["key"], "test")
        self.assertEqual(d["value"], "data")
        self.assertEqual(d["operation"], "set")
        self.assertEqual(d["agent_id"], "agent1")

    def test_all_operation_types(self) -> None:
        for op in CRDTOperationType:
            record = CRDTRecord(
                key=f"key_{op.value}", value=op.value, timestamp=time.time(),
                vector_clock={"a": 1}, operation=op, agent_id="agent1",
            )
            self.assertIn(op.value, record.to_dict()["operation"])


class TestCrdtSharedMemory(unittest.TestCase):
    def setUp(self) -> None:
        self.memory = CrdtSharedMemory()

    def test_set_and_get(self) -> None:
        record = self.memory.set("key1", "value1", "agent1")
        self.assertEqual(self.memory.get("key1"), "value1")
        self.assertEqual(record.key, "key1")
        self.assertEqual(record.agent_id, "agent1")
        self.assertEqual(record.operation, CRDTOperationType.SET)

    def test_get_all(self) -> None:
        self.memory.set("a", "1", "agent1")
        self.memory.set("b", "2", "agent2")
        all_vals = self.memory.get_all()
        self.assertEqual(all_vals["a"], "1")
        self.assertEqual(all_vals["b"], "2")

    def test_get_missing_key(self) -> None:
        self.assertIsNone(self.memory.get("nonexistent"))

    def test_set_overwrites(self) -> None:
        self.memory.set("key", "v1", "agent1")
        self.memory.set("key", "v2", "agent2")
        self.assertEqual(self.memory.get("key"), "v2")

    def test_subscriber_callback(self) -> None:
        events: list[CRDTRecord] = []
        self.memory.subscribe(events.append)
        self.memory.set("key", "val", "agent1")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].key, "key")

    def test_subscriber_error_does_not_propagate(self) -> None:
        def bad_cb(record: CRDTRecord) -> None:
            raise RuntimeError("bad")
        self.memory.subscribe(bad_cb)
        self.memory.set("key", "val", "agent1")
        self.assertEqual(self.memory.get("key"), "val")

    def test_thread_safety(self) -> None:
        errors: list[Exception] = []
        def writer() -> None:
            try:
                for i in range(100):
                    self.memory.set(f"key_{i}", i, "writer")
            except Exception as e:
                errors.append(e)
        threads = [threading.Thread(target=writer) for _ in range(5)]
        for t in threads: t.start()
        for t in threads: t.join()
        self.assertEqual(len(errors), 0)
        self.assertEqual(len(self.memory.get_all()), 100)


class TestTaskDelegationMarket(unittest.TestCase):
    def setUp(self) -> None:
        self.market = TaskDelegationMarket()

    def test_list_task(self) -> None:
        self.market.list_task("task1", "Fix bug", reward=100)
        task = self.market.get_task("task1")
        self.assertIsNotNone(task)
        self.assertEqual(task["status"], "open")
        self.assertEqual(task["reward"], 100)

    def test_list_task_default_values(self) -> None:
        self.market.list_task("task1", "Test")
        task = self.market.get_task("task1")
        self.assertEqual(task["min_reputation"], 0.0)
        self.assertEqual(task["reward"], 100)
        self.assertEqual(task["status"], "open")

    def test_get_open_tasks(self) -> None:
        self.market.list_task("task1", "A")
        self.market.list_task("task2", "B")
        open_tasks = self.market.get_open_tasks()
        self.assertEqual(len(open_tasks), 2)

    def test_place_bid(self) -> None:
        self.market.list_task("task1", "Fix", reward=100)
        result = self.market.place_bid("task1", "agent1", 50, 0.9, 1000.0)
        self.assertTrue(result)

    def test_place_bid_low_reputation(self) -> None:
        self.market.list_task("task1", "Fix", min_reputation=0.8, reward=100)
        result = self.market.place_bid("task1", "agent1", 50, 0.5, 1000.0)
        self.assertFalse(result)

    def test_place_bid_closed_task(self) -> None:
        # Must place a bid first, then winner selection closes the task
        self.market.list_task("task1", "Fix", reward=100)
        self.market.place_bid("task1", "agent1", 50, 0.9, 1000.0)
        self.market.select_winner("task1")
        result = self.market.place_bid("task1", "agent2", 30, 0.9, 1000.0)
        self.assertFalse(result)

    def test_select_winner(self) -> None:
        self.market.list_task("task1", "Fix", reward=100)
        self.market.place_bid("task1", "agent1", 50, 0.9, 1000.0)
        self.market.place_bid("task1", "agent2", 30, 0.8, 800.0)
        winner = self.market.select_winner("task1")
        self.assertIsNotNone(winner)
        task = self.market.get_task("task1")
        self.assertEqual(task["status"], "assigned")
        self.assertEqual(task["winner"], winner)

    def test_select_winner_no_bids(self) -> None:
        self.market.list_task("task1", "Fix", reward=100)
        winner = self.market.select_winner("task1")
        self.assertIsNone(winner)

    def test_task_bid_has_fields(self) -> None:
        bid = TaskBid("t", "a", 50, 0.9, "2026-01-01", 1000.0)
        self.assertEqual(bid.task_id, "t")
        self.assertEqual(bid.bid_amount, 50)


class TestSharedContextBus(unittest.TestCase):
    def setUp(self) -> None:
        self.bus = SharedContextBus()

    def test_publish(self) -> None:
        msg = self.bus.publish("topic1", {"data": "test"}, sender="agent1")
        self.assertEqual(msg.topic, "topic1")
        self.assertEqual(msg.payload["data"], "test")
        self.assertEqual(msg.sender, "agent1")
        self.assertIsNotNone(msg.message_id)

    def test_subscribe_and_publish(self) -> None:
        received: list[BusMessage] = []
        self.bus.subscribe("topic1", received.append)
        self.bus.publish("topic1", {"data": "test"})
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].payload["data"], "test")

    def test_subscribe_wrong_topic(self) -> None:
        received: list[BusMessage] = []
        self.bus.subscribe("topic1", received.append)
        self.bus.publish("topic2", {"data": "test"})
        self.assertEqual(len(received), 0)

    def test_get_history(self) -> None:
        self.bus.publish("t1", {"d": 1})
        self.bus.publish("t2", {"d": 2})
        history = self.bus.get_history()
        self.assertEqual(len(history), 2)

    def test_get_history_by_topic(self) -> None:
        self.bus.publish("t1", {"d": 1})
        self.bus.publish("t2", {"d": 2})
        history = self.bus.get_history(topic="t1")
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].topic, "t1")

    def test_get_history_limit(self) -> None:
        for i in range(5):
            self.bus.publish("t", {"i": i})
        history = self.bus.get_history(limit=3)
        self.assertEqual(len(history), 3)


class TestAgentCapabilityRegistry(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = AgentCapabilityRegistry()

    def test_register(self) -> None:
        self.registry.register("agent1", "search", {"version": "1.0"})
        agents = self.registry.get_all_agents()
        self.assertEqual(len(agents), 1)
        self.assertEqual(agents[0].agent_id, "agent1")

    def test_update_performance(self) -> None:
        self.registry.register("agent1", "search")
        self.registry.update_performance("agent1", 100.0, True)
        agents = self.registry.get_all_agents()
        self.assertEqual(agents[0].tasks_completed, 1)

    def test_find_best_agent(self) -> None:
        self.registry.register("a1", "search")
        self.registry.register("a2", "search")
        self.registry.update_performance("a1", 100.0, True)
        self.registry.update_performance("a1", 100.0, True)
        self.registry.update_performance("a2", 100.0, False)
        best = self.registry.find_best_agent("search")
        self.assertEqual(best, "a1")

    def test_get_all_agents(self) -> None:
        self.registry.register("a1", "search")
        self.registry.register("a2", "code")
        caps = self.registry.get_all_agents()
        self.assertEqual(len(caps), 2)


class TestCoalitionGovernance(unittest.TestCase):
    def setUp(self) -> None:
        self.gov = CoalitionGovernance()

    def test_create_proposal(self) -> None:
        proposal_id = self.gov.propose("Test Proposal", "desc", "agent1")
        self.assertIsNotNone(proposal_id)
        proposal = self.gov.get_proposal(proposal_id)
        self.assertIsNotNone(proposal)
        self.assertEqual(proposal.title, "Test Proposal")
        self.assertEqual(proposal.status, "active")

    def test_vote(self) -> None:
        proposal_id = self.gov.propose("Test", "desc", "agent1")
        result = self.gov.vote(proposal_id, "agent2", True)
        self.assertTrue(result)

    def test_get_proposal_missing(self) -> None:
        self.assertIsNone(self.gov.get_proposal("nonexistent"))

    def test_tally_passes(self) -> None:
        proposal_id = self.gov.propose("Test", "desc", "agent1")
        self.gov.vote(proposal_id, "agent2", True)
        self.gov.vote(proposal_id, "agent3", True)
        status = self.gov.tally(proposal_id, total_agents=3)
        self.assertEqual(status, "passed")


class TestConcurrency(unittest.TestCase):
    def test_crdt_thread_safe(self) -> None:
        memory = CrdtSharedMemory()
        errors: list[Exception] = []
        def writer() -> None:
            try:
                for i in range(50):
                    memory.set(f"k_{i}", i, "w")
            except Exception as e:
                errors.append(e)
        threads = [threading.Thread(target=writer) for _ in range(3)]
        for t in threads: t.start()
        for t in threads: t.join()
        self.assertEqual(len(errors), 0)
        self.assertEqual(len(memory.get_all()), 50)