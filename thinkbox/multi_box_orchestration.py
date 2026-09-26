"""
Multi-Box Swarm Orchestration with Persistent Knowledge Fabric.

This module enables:
1. Launching specialized Think Boxes as autonomous agents (screenwriter, cinematographer, etc.)
2. Coordinating parallel box execution with inter-box communication
3. Persistent knowledge fabric that survives individual box lifetimes
4. Synthesis of parallel results into unified intelligence
5. Learning that compounds across box lifecycles

Core insight: Information needs to outlive the box. The knowledge fabric is the
permanent record; boxes are ephemeral execution contexts that feed it.

Architecture:
  BoxSpecialization → SwarmCoordinator → KnowledgeFabric + InterBoxMessaging
    ↓
  Parallel execution (screenwriter, cinematographer, musician, etc.)
    ↓
  SynthesisEngine (combines findings, detects conflicts, synthesizes knowledge)
    ↓
  PersistentKnowledgeGraph (evidence-backed, cryptographically linked)
"""

import asyncio
import hashlib
import json
import logging
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ============================================================================
# 1. BOX SPECIALIZATION
# ============================================================================

class BoxRole(Enum):
    """Specialized roles that boxes can take on."""
    SCREENWRITER = "screenwriter"
    CINEMATOGRAPHER = "cinematographer"
    MUSICIAN = "musician"
    LIGHTING_DESIGNER = "lighting_designer"
    SOUND_ENGINEER = "sound_engineer"
    PRODUCTION_DESIGNER = "production_designer"
    EDITOR = "editor"
    VISUAL_EFFECTS = "visual_effects"

    # Medical domain
    PHARMACIST = "pharmacist"
    TOXICOLOGIST = "toxicologist"
    CLINICAL_RESEARCHER = "clinical_researcher"
    PHARMACOKINETICS = "pharmacokinetics"

    # Generic research
    RESEARCHER = "researcher"
    VALIDATOR = "validator"
    SYNTHESIZER = "synthesizer"


@dataclass
class BoxCapability:
    """Defines what a box can do."""
    role: BoxRole
    expertise_areas: List[str]
    constraints: Dict[str, Any]
    tools_available: List[str]
    max_concurrent_queries: int = 5
    timeout_seconds: int = 300

    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role.value,
            "expertise_areas": self.expertise_areas,
            "constraints": self.constraints,
            "tools_available": self.tools_available,
            "max_concurrent_queries": self.max_concurrent_queries,
            "timeout_seconds": self.timeout_seconds,
        }


@dataclass
class BoxInstance:
    """Running instance of a specialized Think Box."""
    box_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    role: BoxRole = None
    capability: BoxCapability = None
    status: str = "CREATED"  # CREATED, RUNNING, IDLE, SHUTDOWN
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    findings: List[Dict[str, Any]] = field(default_factory=list)
    knowledge_contributed: List[str] = field(default_factory=list)  # KG node IDs
    errors: List[str] = field(default_factory=list)

    def mark_running(self):
        self.status = "RUNNING"

    def mark_idle(self):
        self.status = "IDLE"

    def mark_shutdown(self):
        self.status = "SHUTDOWN"

    def add_finding(self, finding: Dict[str, Any]):
        """Record a finding from this box."""
        finding["box_id"] = self.box_id
        finding["timestamp"] = datetime.utcnow().isoformat()
        self.findings.append(finding)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "box_id": self.box_id,
            "role": self.role.value if self.role else None,
            "status": self.status,
            "created_at": self.created_at,
            "findings_count": len(self.findings),
            "knowledge_contributed": self.knowledge_contributed,
            "errors": self.errors,
        }


# ============================================================================
# 2. KNOWLEDGE FABRIC
# ============================================================================

@dataclass
class KnowledgeNode:
    """Atomic unit of knowledge in the knowledge fabric."""
    node_id: str = field(default_factory=lambda: str(uuid.uuid4())[:16])
    content: Dict[str, Any] = field(default_factory=dict)
    source_boxes: List[str] = field(default_factory=list)
    evidence_level: str = "INFERRED"  # INFERRED, VERIFIED, PHYSICALLY_MEASURED
    confidence: float = 0.0  # 0.0 to 1.0
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    proof_hash: str = ""  # SHA256 of (content + sources + timestamp)
    edges_to: List[str] = field(default_factory=list)  # Other node IDs

    def compute_proof_hash(self) -> str:
        """Generate tamper-evident proof hash."""
        data = json.dumps({
            "content": self.content,
            "sources": sorted(self.source_boxes),
            "created_at": self.created_at,
        }, sort_keys=True)
        return hashlib.sha256(data.encode()).hexdigest()

    def verify_integrity(self) -> bool:
        """Verify proof hash hasn't been tampered with."""
        if not self.proof_hash:
            return False
        return self.proof_hash == self.compute_proof_hash()


class KnowledgeFabric:
    """
    Persistent knowledge graph that boxes write to and read from.

    Core principle: Individual boxes are ephemeral; the knowledge fabric is eternal.
    Every finding, every synthesis, every lesson is committed to durable storage
    with cryptographic evidence of lineage.
    """

    def __init__(self, persistence_path: str = "data/knowledge_fabric.json"):
        self.nodes: Dict[str, KnowledgeNode] = {}
        self.edges: Dict[str, List[str]] = {}  # node_id -> [related_node_ids]
        self.persistence_path = persistence_path
        self.write_log: List[Dict[str, Any]] = []  # Audit trail

    def add_knowledge(
        self,
        content: Dict[str, Any],
        source_boxes: List[str],
        evidence_level: str = "INFERRED",
        confidence: float = 0.5,
    ) -> KnowledgeNode:
        """Add a knowledge node from one or more boxes."""
        node = KnowledgeNode(
            content=content,
            source_boxes=source_boxes,
            evidence_level=evidence_level,
            confidence=confidence,
        )
        node.proof_hash = node.compute_proof_hash()

        self.nodes[node.node_id] = node

        # Audit trail
        self.write_log.append({
            "action": "ADD_KNOWLEDGE",
            "node_id": node.node_id,
            "sources": source_boxes,
            "timestamp": datetime.utcnow().isoformat(),
            "proof_hash": node.proof_hash,
        })

        logger.info(f"Knowledge added: {node.node_id} from {source_boxes}")
        return node

    def link_nodes(self, source_id: str, target_id: str):
        """Create an edge between two knowledge nodes."""
        if source_id not in self.nodes or target_id not in self.nodes:
            raise ValueError(f"Invalid node IDs: {source_id}, {target_id}")

        if source_id not in self.edges:
            self.edges[source_id] = []

        if target_id not in self.edges[source_id]:
            self.edges[source_id].append(target_id)

        self.nodes[source_id].edges_to.append(target_id)

        self.write_log.append({
            "action": "LINK_NODES",
            "source": source_id,
            "target": target_id,
            "timestamp": datetime.utcnow().isoformat(),
        })

    def query_by_topic(self, topic: str, confidence_threshold: float = 0.0) -> List[KnowledgeNode]:
        """Query knowledge fabric by topic."""
        results = []
        for node in self.nodes.values():
            if (topic.lower() in json.dumps(node.content).lower() and
                node.confidence >= confidence_threshold):
                results.append(node)
        return results

    def query_by_source(self, box_id: str) -> List[KnowledgeNode]:
        """Get all knowledge contributed by a specific box."""
        return [n for n in self.nodes.values() if box_id in n.source_boxes]

    def verify_all_integrity(self) -> Tuple[int, int]:
        """Verify integrity of all nodes. Returns (valid_count, invalid_count)."""
        valid = 0
        invalid = 0
        for node in self.nodes.values():
            if node.verify_integrity():
                valid += 1
            else:
                invalid += 1
        return valid, invalid

    def persist(self) -> str:
        """Write the fabric to ``persistence_path`` atomically and return the path.

        The file is written to a temporary sibling and then renamed over the
        target, so a crash mid-write never leaves a truncated fabric behind.
        """
        path = Path(self.persistence_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "format_version": 1,
            "timestamp": datetime.utcnow().isoformat(),
            "nodes": {nid: asdict(n) for nid, n in self.nodes.items()},
            "edges": self.edges,
            "write_log": self.write_log,
        }
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(json.dumps(data, sort_keys=True, indent=2))
        os.replace(tmp, path)
        logger.info(f"Knowledge fabric persisted: {len(self.nodes)} nodes -> {path}")
        return str(path)

    @classmethod
    def load(cls, path: str) -> "KnowledgeFabric":
        """Restore a fabric written by persist().

        Every node's proof hash is re-verified; a fabric containing any node
        whose content no longer matches its proof is refused rather than
        loaded, since silently accepting tampered knowledge would defeat the
        point of the proof hashes.
        """
        data = json.loads(Path(path).read_text())
        fabric = cls(persistence_path=path)
        for nid, raw in data["nodes"].items():
            node = KnowledgeNode(**raw)
            if not node.verify_integrity():
                raise ValueError(
                    f"Knowledge node {nid} failed integrity verification in {path}"
                )
            fabric.nodes[nid] = node
        fabric.edges = {k: list(v) for k, v in data.get("edges", {}).items()}
        fabric.write_log = list(data.get("write_log", []))
        return fabric


# ============================================================================
# 3. INTER-BOX MESSAGING
# ============================================================================

@dataclass
class InterBoxMessage:
    """Message from one box to another."""
    message_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    from_box_id: str = ""
    to_box_id: str = ""  # Empty = broadcast to all
    query: str = ""
    findings: List[Dict[str, Any]] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    status: str = "SENT"  # SENT, RECEIVED, PROCESSED, ANSWERED
    response: Optional[Dict[str, Any]] = None

    def mark_received(self):
        self.status = "RECEIVED"

    def mark_processed(self):
        self.status = "PROCESSED"

    def mark_answered(self, response: Dict[str, Any]):
        self.response = response
        self.status = "ANSWERED"


class InterBoxMessenger:
    """Handles communication between boxes."""

    def __init__(self):
        self.mailbox: Dict[str, List[InterBoxMessage]] = {}  # box_id -> messages
        self.history: List[InterBoxMessage] = []

    def send_message(self, message: InterBoxMessage) -> bool:
        """Send a message from one box to another (or broadcast)."""
        if not message.to_box_id:
            # Broadcast
            logger.info(f"Broadcast from {message.from_box_id}: {message.query}")
        else:
            if message.to_box_id not in self.mailbox:
                self.mailbox[message.to_box_id] = []
            self.mailbox[message.to_box_id].append(message)
            logger.info(f"Message {message.message_id}: {message.from_box_id} → {message.to_box_id}")

        self.history.append(message)
        return True

    def receive_messages(self, box_id: str) -> List[InterBoxMessage]:
        """Retrieve messages for a specific box."""
        messages = self.mailbox.get(box_id, [])
        for msg in messages:
            msg.mark_received()
        self.mailbox[box_id] = []
        return messages

    def respond(self, original_message: InterBoxMessage, response: Dict[str, Any]):
        """Send a response to a received message."""
        original_message.mark_answered(response)
        if original_message.from_box_id:
            reply = InterBoxMessage(
                from_box_id=original_message.to_box_id,
                to_box_id=original_message.from_box_id,
                query=f"RE: {original_message.query}",
                response=response,
            )
            self.send_message(reply)


# ============================================================================
# 4. SWARM COORDINATOR
# ============================================================================

class SwarmCoordinator:
    """
    Orchestrates multiple specialized Think Boxes working in parallel.

    Responsibilities:
    1. Launch and manage box lifecycles
    2. Distribute work to appropriate boxes
    3. Coordinate inter-box communication
    4. Aggregate results via synthesis engine
    5. Maintain overall swarm health
    """

    def __init__(self):
        self.boxes: Dict[str, BoxInstance] = {}
        self.knowledge_fabric = KnowledgeFabric()
        self.messenger = InterBoxMessenger()
        self.created_at = datetime.utcnow().isoformat()

    def launch_box(self, role: BoxRole, expertise_areas: List[str],
                   tools_available: List[str] = None) -> BoxInstance:
        """Launch a new specialized box."""
        if tools_available is None:
            tools_available = []

        capability = BoxCapability(
            role=role,
            expertise_areas=expertise_areas,
            constraints={},
            tools_available=tools_available,
        )

        box = BoxInstance(role=role, capability=capability)
        box.mark_running()
        self.boxes[box.box_id] = box

        logger.info(f"Box launched: {box.box_id} ({role.value})")
        return box

    def shutdown_box(self, box_id: str):
        """Shutdown a box and preserve its knowledge."""
        if box_id in self.boxes:
            box = self.boxes[box_id]

            # Persist box findings to knowledge fabric
            for finding in box.findings:
                knowledge_node = self.knowledge_fabric.add_knowledge(
                    content=finding,
                    source_boxes=[box_id],
                    evidence_level=finding.get("evidence_level", "INFERRED"),
                    confidence=finding.get("confidence", 0.5),
                )
                box.knowledge_contributed.append(knowledge_node.node_id)

            box.mark_shutdown()
            logger.info(f"Box shutdown: {box_id}, knowledge persisted: {len(box.findings)} findings")

    def get_active_boxes(self) -> List[BoxInstance]:
        """Get all currently active boxes."""
        return [b for b in self.boxes.values() if b.status in ("RUNNING", "IDLE")]

    def swarm_status(self) -> Dict[str, Any]:
        """Get overall swarm status."""
        active_boxes = self.get_active_boxes()
        return {
            "total_boxes": len(self.boxes),
            "active_boxes": len(active_boxes),
            "box_roles": [b.role.value for b in active_boxes],
            "knowledge_nodes": len(self.knowledge_fabric.nodes),
            "messages_sent": len(self.messenger.history),
            "created_at": self.created_at,
        }


# ============================================================================
# 5. SYNTHESIS ENGINE
# ============================================================================

class SynthesisEngine:
    """
    Combines parallel results from multiple boxes into unified intelligence.

    Examples:
    - Film synthesis: combines screenwriter, cinematographer, musician, sound findings
      into a coherent production plan
    - Medical synthesis: combines pharmacist, toxicologist, researcher findings
      into drug interaction safety report
    """

    def __init__(self, fabric: KnowledgeFabric):
        self.fabric = fabric
        self.syntheses: List[Dict[str, Any]] = []

    def synthesize_findings(self, box_ids: List[str], topic: str) -> Dict[str, Any]:
        """
        Synthesize findings from multiple boxes on a topic.

        Returns unified findings with confidence scoring and conflict detection.
        """
        all_findings = []
        for box_id in box_ids:
            nodes = self.fabric.query_by_source(box_id)
            for node in nodes:
                if topic.lower() in json.dumps(node.content).lower():
                    all_findings.append({
                        "source_box": box_id,
                        "content": node.content,
                        "confidence": node.confidence,
                        "evidence_level": node.evidence_level,
                    })

        # Aggregate by consensus
        consensus_findings = []
        conflicting_findings = []

        # Simple consensus: findings from 2+ boxes with similar confidence
        seen_contents = {}
        for finding in all_findings:
            content_hash = hashlib.sha256(
                json.dumps(finding["content"], sort_keys=True).encode()
            ).hexdigest()

            if content_hash not in seen_contents:
                seen_contents[content_hash] = []
            seen_contents[content_hash].append(finding)

        # agreement_fraction is derived from the agreement structure itself,
        # not from boxes' self-reported confidence. The pre-registered
        # synthesis-calibration-v1 experiment showed average_confidence is
        # poorly calibrated for exactly this reason; see
        # docs/guides/synthesis-calibration-arena.md.
        total_findings = len(all_findings)
        for findings in seen_contents.values():
            if len(findings) >= 2:
                consensus_findings.append({
                    "consensus": True,
                    "agreements": len(findings),
                    "boxes": [f["source_box"] for f in findings],
                    "average_confidence": sum(f["confidence"] for f in findings) / len(findings),
                    "agreement_fraction": len(findings) / total_findings,
                    "content": findings[0]["content"],
                })
            else:
                conflicting_findings.extend(
                    {**f, "agreement_fraction": 1 / total_findings} for f in findings
                )

        synthesis = {
            "synthesis_id": str(uuid.uuid4())[:12],
            "topic": topic,
            "timestamp": datetime.utcnow().isoformat(),
            "consensus_findings": consensus_findings,
            "conflicting_findings": conflicting_findings,
            "participant_boxes": box_ids,
            "total_findings_synthesized": len(all_findings),
        }

        self.syntheses.append(synthesis)
        logger.info(f"Synthesis: {len(consensus_findings)} consensus, {len(conflicting_findings)} conflicts")

        return synthesis


# ============================================================================
# 6. ORCHESTRATION EXAMPLE
# ============================================================================

class MultiBoxOrchestrationEngine:
    """High-level orchestration engine for multi-box workflows."""

    def __init__(self):
        self.coordinator = SwarmCoordinator()
        self.synthesis = SynthesisEngine(self.coordinator.knowledge_fabric)

    async def run_film_production_swarm(self) -> Dict[str, Any]:
        """Example: Orchestrate a film production swarm."""
        boxes = []

        # Launch specialized roles
        roles = [
            (BoxRole.SCREENWRITER, ["narrative", "dialogue", "structure"]),
            (BoxRole.CINEMATOGRAPHER, ["visual_composition", "framing", "color"]),
            (BoxRole.MUSICIAN, ["score", "themes", "sound_design"]),
            (BoxRole.LIGHTING_DESIGNER, ["mood", "contrast", "lighting_setup"]),
            (BoxRole.PRODUCTION_DESIGNER, ["sets", "props", "environment"]),
        ]

        for role, expertise in roles:
            box = self.coordinator.launch_box(role, expertise)
            boxes.append(box)
            await asyncio.sleep(0.1)

        # Simulate collaboration: boxes request findings from each other
        for box in boxes:
            for other_box in boxes:
                if box.box_id != other_box.box_id:
                    msg = InterBoxMessage(
                        from_box_id=box.box_id,
                        to_box_id=other_box.box_id,
                        query=f"How does {box.role.value} impact {other_box.role.value}?",
                    )
                    self.coordinator.messenger.send_message(msg)

        # Simulate findings
        for box in boxes:
            box.add_finding({
                "type": "creative_direction",
                "domain": box.role.value,
                "evidence_level": "INFERRED",
                "confidence": 0.8,
            })

        # Shutdown and persist
        for box in boxes:
            self.coordinator.shutdown_box(box.box_id)

        # Synthesize results
        film_synthesis = self.synthesis.synthesize_findings(
            [b.box_id for b in boxes],
            "film_production"
        )

        return {
            "swarm_status": self.coordinator.swarm_status(),
            "synthesis": film_synthesis,
            "knowledge_nodes": len(self.coordinator.knowledge_fabric.nodes),
        }

    async def run_drug_interaction_swarm(self) -> Dict[str, Any]:
        """Example: Orchestrate drug interaction research swarm."""
        boxes = []

        # Launch pharmacology specialists
        roles = [
            (BoxRole.PHARMACIST, ["drug_properties", "interactions"]),
            (BoxRole.TOXICOLOGIST, ["toxicity", "side_effects"]),
            (BoxRole.CLINICAL_RESEARCHER, ["clinical_trials", "outcomes"]),
            (BoxRole.PHARMACOKINETICS, ["absorption", "metabolism", "elimination"]),
        ]

        for role, expertise in roles:
            box = self.coordinator.launch_box(role, expertise)
            boxes.append(box)

        # Simulate research findings
        for box in boxes:
            box.add_finding({
                "type": "research_finding",
                "domain": box.role.value,
                "evidence_level": "VERIFIED",
                "confidence": 0.95,
            })

        # Shutdown and persist
        for box in boxes:
            self.coordinator.shutdown_box(box.box_id)

        # Synthesize drug safety report
        safety_synthesis = self.synthesis.synthesize_findings(
            [b.box_id for b in boxes],
            "drug_interaction"
        )

        return {
            "swarm_status": self.coordinator.swarm_status(),
            "synthesis": safety_synthesis,
        }
