"""
Comprehensive tests for multi-box swarm orchestration with persistent knowledge fabric.

Tests validate:
1. Box specialization and lifecycle
2. Knowledge fabric persistence and integrity
3. Inter-box messaging and collaboration
4. Synthesis of parallel findings
5. Real-world use cases (film, drug interactions)
"""

import asyncio
import json
import unittest
from pathlib import Path
from datetime import datetime

from thinkbox.multi_box_orchestration import (
    BoxRole,
    BoxCapability,
    BoxInstance,
    KnowledgeNode,
    KnowledgeFabric,
    InterBoxMessage,
    InterBoxMessenger,
    SwarmCoordinator,
    SynthesisEngine,
    MultiBoxOrchestrationEngine,
)


class TestBoxSpecialization(unittest.TestCase):
    """Test box specialization and capabilities."""

    def test_box_capability_definition(self):
        """Test defining a box capability."""
        cap = BoxCapability(
            role=BoxRole.SCREENWRITER,
            expertise_areas=["narrative", "dialogue", "structure"],
            constraints={"max_scenes": 100},
            tools_available=["writing_assistant", "plot_validator"],
        )

        self.assertEqual(cap.role, BoxRole.SCREENWRITER)
        self.assertIn("narrative", cap.expertise_areas)
        self.assertEqual(cap.max_concurrent_queries, 5)

    def test_box_instance_creation(self):
        """Test creating a box instance."""
        box = BoxInstance(
            role=BoxRole.CINEMATOGRAPHER,
            capability=BoxCapability(
                role=BoxRole.CINEMATOGRAPHER,
                expertise_areas=["framing", "color"],
                constraints={},
                tools_available=["shot_planner"],
            )
        )

        self.assertIsNotNone(box.box_id)
        self.assertEqual(box.status, "CREATED")
        self.assertEqual(len(box.findings), 0)

    def test_box_lifecycle(self):
        """Test box status transitions."""
        box = BoxInstance(role=BoxRole.MUSICIAN)

        self.assertEqual(box.status, "CREATED")
        box.mark_running()
        self.assertEqual(box.status, "RUNNING")
        box.mark_idle()
        self.assertEqual(box.status, "IDLE")
        box.mark_shutdown()
        self.assertEqual(box.status, "SHUTDOWN")

    def test_box_add_finding(self):
        """Test box recording findings."""
        box = BoxInstance(role=BoxRole.PHARMACIST)

        finding = {
            "drug": "aspirin",
            "interaction": "warfarin",
            "severity": "high",
        }
        box.add_finding(finding)

        self.assertEqual(len(box.findings), 1)
        self.assertEqual(box.findings[0]["drug"], "aspirin")
        self.assertIn("box_id", box.findings[0])
        self.assertIn("timestamp", box.findings[0])

    def test_box_to_dict(self):
        """Test serializing box state."""
        box = BoxInstance(role=BoxRole.SCREENWRITER)
        box.add_finding({"scene": 1})

        d = box.to_dict()
        self.assertEqual(d["role"], "screenwriter")
        self.assertEqual(d["findings_count"], 1)
        self.assertIn("box_id", d)


class TestKnowledgeFabric(unittest.TestCase):
    """Test persistent knowledge fabric."""

    def setUp(self):
        self.fabric = KnowledgeFabric()

    def test_add_knowledge(self):
        """Test adding a knowledge node."""
        node = self.fabric.add_knowledge(
            content={"finding": "aspirin + warfarin interaction"},
            source_boxes=["box_1", "box_2"],
            evidence_level="VERIFIED",
            confidence=0.95,
        )

        self.assertIsNotNone(node.node_id)
        self.assertEqual(node.confidence, 0.95)
        self.assertEqual(len(node.source_boxes), 2)
        self.assertIn(node.node_id, self.fabric.nodes)

    def test_knowledge_integrity_proof(self):
        """Test tamper-evident proof hashes."""
        node = self.fabric.add_knowledge(
            content={"data": "critical"},
            source_boxes=["box_1"],
        )

        self.assertNotEqual(node.proof_hash, "")
        self.assertTrue(node.verify_integrity())

        # Tamper with content
        node.content["data"] = "modified"
        self.assertFalse(node.verify_integrity())

    def test_link_nodes(self):
        """Test linking knowledge nodes."""
        node1 = self.fabric.add_knowledge(
            content={"finding": "A"},
            source_boxes=["box_1"],
        )
        node2 = self.fabric.add_knowledge(
            content={"finding": "B"},
            source_boxes=["box_2"],
        )

        self.fabric.link_nodes(node1.node_id, node2.node_id)

        self.assertIn(node2.node_id, node1.edges_to)
        self.assertIn(node2.node_id, self.fabric.edges.get(node1.node_id, []))

    def test_query_by_topic(self):
        """Test querying knowledge by topic."""
        self.fabric.add_knowledge(
            content={"topic": "drug_interactions", "finding": "X"},
            source_boxes=["box_1"],
            confidence=0.9,
        )
        self.fabric.add_knowledge(
            content={"topic": "toxicity", "finding": "Y"},
            source_boxes=["box_2"],
            confidence=0.5,
        )

        results = self.fabric.query_by_topic("drug_interactions", confidence_threshold=0.8)
        self.assertEqual(len(results), 1)
        self.assertIn("drug_interactions", json.dumps(results[0].content))

    def test_query_by_source(self):
        """Test querying knowledge by source box."""
        self.fabric.add_knowledge(
            content={"data": "1"},
            source_boxes=["box_1"],
        )
        self.fabric.add_knowledge(
            content={"data": "2"},
            source_boxes=["box_1"],
        )
        self.fabric.add_knowledge(
            content={"data": "3"},
            source_boxes=["box_2"],
        )

        box1_knowledge = self.fabric.query_by_source("box_1")
        self.assertEqual(len(box1_knowledge), 2)

        box2_knowledge = self.fabric.query_by_source("box_2")
        self.assertEqual(len(box2_knowledge), 1)

    def test_verify_all_integrity(self):
        """Test verifying all nodes."""
        self.fabric.add_knowledge(
            content={"data": "1"},
            source_boxes=["box_1"],
        )
        self.fabric.add_knowledge(
            content={"data": "2"},
            source_boxes=["box_1"],
        )

        valid, invalid = self.fabric.verify_all_integrity()
        self.assertEqual(valid, 2)
        self.assertEqual(invalid, 0)

    def test_write_audit_trail(self):
        """Test knowledge fabric audit trail."""
        self.fabric.add_knowledge(
            content={"data": "1"},
            source_boxes=["box_1"],
        )
        node1 = list(self.fabric.nodes.values())[0]

        self.fabric.add_knowledge(
            content={"data": "2"},
            source_boxes=["box_2"],
        )
        node2 = list(self.fabric.nodes.values())[1]

        self.fabric.link_nodes(node1.node_id, node2.node_id)

        self.assertGreaterEqual(len(self.fabric.write_log), 3)
        self.assertEqual(self.fabric.write_log[0]["action"], "ADD_KNOWLEDGE")
        self.assertEqual(self.fabric.write_log[2]["action"], "LINK_NODES")


class TestInterBoxMessaging(unittest.TestCase):
    """Test inter-box communication."""

    def setUp(self):
        self.messenger = InterBoxMessenger()

    def test_send_message(self):
        """Test sending a message."""
        msg = InterBoxMessage(
            from_box_id="box_1",
            to_box_id="box_2",
            query="What is X?",
        )

        self.assertTrue(self.messenger.send_message(msg))
        self.assertIn("box_2", self.messenger.mailbox)

    def test_receive_messages(self):
        """Test receiving messages."""
        msg1 = InterBoxMessage(
            from_box_id="box_1",
            to_box_id="box_2",
            query="Query 1?",
        )
        msg2 = InterBoxMessage(
            from_box_id="box_1",
            to_box_id="box_2",
            query="Query 2?",
        )

        self.messenger.send_message(msg1)
        self.messenger.send_message(msg2)

        received = self.messenger.receive_messages("box_2")
        self.assertEqual(len(received), 2)
        self.assertEqual(received[0].status, "RECEIVED")

        # Mailbox should be empty after retrieval
        self.assertEqual(len(self.messenger.receive_messages("box_2")), 0)

    def test_message_response(self):
        """Test responding to messages."""
        msg = InterBoxMessage(
            from_box_id="box_1",
            to_box_id="box_2",
            query="Question?",
        )

        self.messenger.send_message(msg)

        response = {"answer": "Yes"}
        self.messenger.respond(msg, response)

        self.assertEqual(msg.response, response)
        self.assertEqual(msg.status, "ANSWERED")


class TestSwarmCoordinator(unittest.TestCase):
    """Test swarm coordination."""

    def setUp(self):
        self.coordinator = SwarmCoordinator()

    def test_launch_box(self):
        """Test launching a box."""
        box = self.coordinator.launch_box(
            BoxRole.SCREENWRITER,
            ["narrative", "dialogue"],
        )

        self.assertIsNotNone(box.box_id)
        self.assertEqual(box.role, BoxRole.SCREENWRITER)
        self.assertEqual(box.status, "RUNNING")
        self.assertIn(box.box_id, self.coordinator.boxes)

    def test_multiple_box_launch(self):
        """Test launching multiple boxes."""
        roles = [
            BoxRole.SCREENWRITER,
            BoxRole.CINEMATOGRAPHER,
            BoxRole.MUSICIAN,
        ]

        for role in roles:
            self.coordinator.launch_box(role, [])

        self.assertEqual(len(self.coordinator.boxes), 3)

    def test_shutdown_box_persists_knowledge(self):
        """Test that box shutdown persists findings to knowledge fabric."""
        box = self.coordinator.launch_box(BoxRole.PHARMACIST, [])

        box.add_finding({"drug": "A", "interaction": "B"})
        box.add_finding({"drug": "C", "interaction": "D"})

        self.coordinator.shutdown_box(box.box_id)

        # Findings should be in knowledge fabric
        self.assertEqual(len(self.coordinator.knowledge_fabric.nodes), 2)
        self.assertEqual(len(box.knowledge_contributed), 2)

    def test_get_active_boxes(self):
        """Test getting active boxes."""
        box1 = self.coordinator.launch_box(BoxRole.SCREENWRITER, [])
        box2 = self.coordinator.launch_box(BoxRole.MUSICIAN, [])

        active = self.coordinator.get_active_boxes()
        self.assertEqual(len(active), 2)

        self.coordinator.shutdown_box(box1.box_id)
        active = self.coordinator.get_active_boxes()
        self.assertEqual(len(active), 1)

    def test_swarm_status(self):
        """Test getting swarm status."""
        self.coordinator.launch_box(BoxRole.SCREENWRITER, [])
        self.coordinator.launch_box(BoxRole.CINEMATOGRAPHER, [])

        status = self.coordinator.swarm_status()

        self.assertEqual(status["total_boxes"], 2)
        self.assertEqual(status["active_boxes"], 2)
        self.assertIn("screenwriter", status["box_roles"])


class TestSynthesisEngine(unittest.TestCase):
    """Test synthesis of parallel findings."""

    def setUp(self):
        self.fabric = KnowledgeFabric()
        self.synthesis = SynthesisEngine(self.fabric)

    def test_synthesize_consensus_findings(self):
        """Test synthesizing consensus findings from multiple boxes."""
        # Two boxes agree on a finding
        shared_finding = {
            "finding": "aspirin + warfarin interaction",
            "severity": "high",
            "topic": "drug_interaction"
        }

        self.fabric.add_knowledge(
            content=shared_finding,
            source_boxes=["pharmacist"],
            confidence=0.95,
        )
        self.fabric.add_knowledge(
            content=shared_finding,
            source_boxes=["toxicologist"],
            confidence=0.90,
        )

        result = self.synthesis.synthesize_findings(
            ["pharmacist", "toxicologist"],
            "drug_interaction"
        )

        self.assertGreater(len(result["consensus_findings"]), 0)
        self.assertEqual(result["consensus_findings"][0]["agreements"], 2)

    def test_synthesize_conflicting_findings(self):
        """Test synthesizing conflicting findings."""
        self.fabric.add_knowledge(
            content={"severity": "high"},
            source_boxes=["box_1"],
            confidence=0.9,
        )
        self.fabric.add_knowledge(
            content={"severity": "low"},
            source_boxes=["box_2"],
            confidence=0.8,
        )

        result = self.synthesis.synthesize_findings(
            ["box_1", "box_2"],
            "severity"
        )

        self.assertGreater(len(result["conflicting_findings"]), 0)

    def test_synthesis_produces_consistent_results(self):
        """Test that synthesis produces consistent results."""
        # Add identical findings from multiple sources
        for i in range(3):
            self.fabric.add_knowledge(
                content={"consensus_point": "important"},
                source_boxes=[f"box_{i}"],
                confidence=0.95,
            )

        result = self.synthesis.synthesize_findings(
            ["box_0", "box_1", "box_2"],
            "consensus"
        )

        self.assertEqual(len(result["consensus_findings"]), 1)
        self.assertEqual(result["consensus_findings"][0]["agreements"], 3)


class TestMultiBoxFilmProduction(unittest.TestCase):
    """Test film production use case."""

    def test_film_swarm_integration(self):
        """Test orchestrating a film production swarm."""
        engine = MultiBoxOrchestrationEngine()

        # Launch film production swarm
        boxes = []
        roles = [
            BoxRole.SCREENWRITER,
            BoxRole.CINEMATOGRAPHER,
            BoxRole.MUSICIAN,
        ]

        for role in roles:
            box = engine.coordinator.launch_box(role, [])
            boxes.append(box)

        # Each box contributes findings
        for box in boxes:
            box.add_finding({
                "domain": box.role.value,
                "contribution": f"Creative direction from {box.role.value}",
            })

        # Shutdown and persist
        for box in boxes:
            engine.coordinator.shutdown_box(box.box_id)

        # Verify knowledge persisted
        self.assertEqual(len(engine.coordinator.knowledge_fabric.nodes), 3)

        # Synthesize
        result = engine.synthesis.synthesize_findings(
            [b.box_id for b in boxes],
            "film"
        )

        self.assertEqual(result["participant_boxes"], [b.box_id for b in boxes])


class TestMultiBoxDrugInteraction(unittest.TestCase):
    """Test drug interaction research use case."""

    def test_drug_research_swarm(self):
        """Test orchestrating drug interaction research."""
        engine = MultiBoxOrchestrationEngine()

        # Launch research swarm
        roles = [
            BoxRole.PHARMACIST,
            BoxRole.TOXICOLOGIST,
            BoxRole.CLINICAL_RESEARCHER,
        ]

        boxes = []
        for role in roles:
            box = engine.coordinator.launch_box(role, [])
            boxes.append(box)

        # Each researcher contributes findings
        findings_data = [
            {"type": "pharmacist", "finding": "Drug A inhibits metabolism of Drug B"},
            {"type": "toxicologist", "finding": "Drug A + Drug B increases hepatotoxicity"},
            {"type": "researcher", "finding": "Clinical trial shows 3x adverse events"},
        ]

        for box, data in zip(boxes, findings_data):
            box.add_finding(data)

        # Shutdown
        for box in boxes:
            engine.coordinator.shutdown_box(box.box_id)

        # Verify knowledge
        self.assertEqual(len(engine.coordinator.knowledge_fabric.nodes), 3)

        # All sources should agree this is important
        fabric = engine.coordinator.knowledge_fabric
        all_nodes = list(fabric.nodes.values())

        # Check confidence levels - default is 0.5, so >= 0.5
        for node in all_nodes:
            self.assertGreaterEqual(node.confidence, 0.5)


class TestKnowledgePersistence(unittest.TestCase):
    """Test that knowledge outlives boxes."""

    def test_knowledge_survives_box_shutdown(self):
        """Test that knowledge persists after box shutdown."""
        coordinator = SwarmCoordinator()

        # Create and populate boxes
        box1 = coordinator.launch_box(BoxRole.PHARMACIST, [])
        box2 = coordinator.launch_box(BoxRole.TOXICOLOGIST, [])

        box1.add_finding({"research": "Finding A"})
        box2.add_finding({"research": "Finding B"})

        box1_id = box1.box_id
        box2_id = box2.box_id

        # Shutdown both boxes
        coordinator.shutdown_box(box1_id)
        coordinator.shutdown_box(box2_id)

        # All boxes are now shutdown
        active = coordinator.get_active_boxes()
        self.assertEqual(len(active), 0)

        # But knowledge persists
        knowledge = coordinator.knowledge_fabric.nodes
        self.assertEqual(len(knowledge), 2)

        # Knowledge can be queried
        box1_knowledge = coordinator.knowledge_fabric.query_by_source(box1_id)
        self.assertEqual(len(box1_knowledge), 1)


class TestAsyncOrchestration(unittest.TestCase):
    """Test async multi-box orchestration."""

    def test_film_swarm_async(self):
        """Test async film production swarm."""
        async def run_test():
            engine = MultiBoxOrchestrationEngine()
            result = await engine.run_film_production_swarm()

            self.assertGreater(result["swarm_status"]["total_boxes"], 0)
            self.assertEqual(result["swarm_status"]["active_boxes"], 0)  # All shutdown
            self.assertGreater(result["knowledge_nodes"], 0)

            return result

        result = asyncio.run(run_test())
        self.assertIsNotNone(result)

    def test_drug_swarm_async(self):
        """Test async drug research swarm."""
        async def run_test():
            engine = MultiBoxOrchestrationEngine()
            result = await engine.run_drug_interaction_swarm()

            self.assertGreater(result["swarm_status"]["total_boxes"], 0)
            self.assertEqual(result["swarm_status"]["active_boxes"], 0)

            return result

        result = asyncio.run(run_test())
        self.assertIsNotNone(result)



class TestAgreementFraction(unittest.TestCase):
    """agreement_fraction is derived from the agreement structure, not from
    boxes' self-reported confidence (see synthesis-calibration-v1 result)."""

    def setUp(self):
        self.fabric = KnowledgeFabric()
        self.synthesis = SynthesisEngine(self.fabric)

    def test_consensus_finding_has_agreement_fraction(self):
        for box in ("a", "b"):
            self.fabric.add_knowledge(
                content={"answer": 1, "topic": "q1"}, source_boxes=[box], confidence=0.99
            )
        self.fabric.add_knowledge(
            content={"answer": 2, "topic": "q1"}, source_boxes=["c"], confidence=0.99
        )
        result = self.synthesis.synthesize_findings(["a", "b", "c"], "q1")
        self.assertAlmostEqual(result["consensus_findings"][0]["agreement_fraction"], 2 / 3)
        self.assertAlmostEqual(result["conflicting_findings"][0]["agreement_fraction"], 1 / 3)

    def test_average_confidence_unchanged(self):
        for box, conf in (("a", 0.9), ("b", 0.7)):
            self.fabric.add_knowledge(
                content={"answer": 1, "topic": "q2"}, source_boxes=[box], confidence=conf
            )
        result = self.synthesis.synthesize_findings(["a", "b"], "q2")
        finding = result["consensus_findings"][0]
        self.assertAlmostEqual(finding["average_confidence"], 0.8)
        self.assertAlmostEqual(finding["agreement_fraction"], 1.0)

    def test_empty_synthesis_does_not_divide_by_zero(self):
        result = self.synthesis.synthesize_findings(["nobody"], "no-such-topic")
        self.assertEqual(result["consensus_findings"], [])
        self.assertEqual(result["conflicting_findings"], [])


class TestKnowledgeFabricDurability(unittest.TestCase):
    """persist() previously built a payload, wrote nothing, and logged
    'persisted'. These tests hold the fabric to its actual claim: knowledge
    survives the process, not just the box."""

    def setUp(self):
        import tempfile
        self._tmp = tempfile.TemporaryDirectory()
        self.path = str(Path(self._tmp.name) / "nested" / "fabric.json")

    def tearDown(self):
        self._tmp.cleanup()

    def test_persist_writes_file_and_load_restores(self):
        fabric = KnowledgeFabric(persistence_path=self.path)
        a = fabric.add_knowledge({"finding": "A"}, ["box_1"], "VERIFIED", 0.9)
        b = fabric.add_knowledge({"finding": "B"}, ["box_2"])
        fabric.link_nodes(a.node_id, b.node_id)
        written = fabric.persist()
        self.assertEqual(written, self.path)
        self.assertTrue(Path(self.path).exists())

        restored = KnowledgeFabric.load(self.path)
        self.assertEqual(set(restored.nodes), {a.node_id, b.node_id})
        self.assertEqual(restored.nodes[a.node_id].content, {"finding": "A"})
        self.assertEqual(restored.nodes[a.node_id].evidence_level, "VERIFIED")
        self.assertEqual(restored.edges[a.node_id], [b.node_id])
        self.assertEqual(len(restored.write_log), len(fabric.write_log))
        self.assertEqual(restored.verify_all_integrity(), (2, 0))

    def test_knowledge_outlives_box_and_process(self):
        coordinator = SwarmCoordinator()
        coordinator.knowledge_fabric.persistence_path = self.path
        box = coordinator.launch_box(BoxRole.PHARMACIST, ["interactions"])
        box.add_finding({"drug": "A", "interaction": "B"})
        box_id = box.box_id
        coordinator.shutdown_box(box_id)
        coordinator.knowledge_fabric.persist()
        del coordinator  # the box, the coordinator, and the in-memory fabric are gone

        fresh = KnowledgeFabric.load(self.path)
        findings = fresh.query_by_source(box_id)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].content["drug"], "A")

    def test_load_refuses_tampered_file(self):
        import json
        fabric = KnowledgeFabric(persistence_path=self.path)
        fabric.add_knowledge({"finding": "original"}, ["box_1"])
        fabric.persist()
        data = json.loads(Path(self.path).read_text())
        node_id = next(iter(data["nodes"]))
        data["nodes"][node_id]["content"]["finding"] = "forged"
        Path(self.path).write_text(json.dumps(data))
        with self.assertRaises(ValueError) as ctx:
            KnowledgeFabric.load(self.path)
        self.assertIn(node_id, str(ctx.exception))

    def test_persist_leaves_no_temp_file(self):
        fabric = KnowledgeFabric(persistence_path=self.path)
        fabric.add_knowledge({"x": 1}, ["b"])
        fabric.persist()
        leftovers = [p.name for p in Path(self.path).parent.iterdir() if p.name != "fabric.json"]
        self.assertEqual(leftovers, [])

    def test_load_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            KnowledgeFabric.load(self.path)

if __name__ == "__main__":
    unittest.main()
