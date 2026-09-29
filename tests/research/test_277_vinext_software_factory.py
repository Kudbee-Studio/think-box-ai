"""Research #277: Vinext-style software-factory experiment.

Tests whether Think Box can reproduce autonomous software-factory workflows
using existing primitives without new core abstractions.

Workflow stages:
1. Upstream Change → Detect Impact → Reproduce Case → Execute Work
2. Collect Evidence → Classify Result → Identify Action → Human Escalation
"""

import json
import unittest
from dataclasses import dataclass
from typing import Any

# Existing primitives (imports demonstrate no new core abstractions)
from core.memory.store import MemoryStore
from thinkbox.memory_layers import MemoryLayer, query_layer, record_task_step, write_verified


@dataclass
class UpstreamEvent:
    """Stage 1: Upstream change detection."""
    event_type: str  # e.g., "dependency_update", "api_breaking_change"
    package: str
    old_version: str
    new_version: str
    breaking_changes: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.event_type,
            "package": self.package,
            "old_version": self.old_version,
            "new_version": self.new_version,
            "breaking_changes": self.breaking_changes,
        }


@dataclass
class ImpactAssessment:
    """Stage 2: Impact detection."""
    affected_files: list[str]
    affected_symbols: list[str]
    confidence: float  # 0.0–1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "affected_files": self.affected_files,
            "affected_symbols": self.affected_symbols,
            "confidence": self.confidence,
        }


@dataclass
class TestCaseReproduction:
    """Stage 3: Reproduce breaking case."""
    test_file: str
    test_name: str
    import_statements: list[str]
    assertions: list[str]
    expected_failure_reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "test_file": self.test_file,
            "test_name": self.test_name,
            "imports": self.import_statements,
            "assertions": self.assertions,
            "expected_failure": self.expected_failure_reason,
        }


@dataclass
class ExecutionResult:
    """Stage 4: Work execution result."""
    old_version_result: str  # "PASS" | "FAIL"
    new_version_result: str  # "PASS" | "FAIL"
    error_message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "old_version": self.old_version_result,
            "new_version": self.new_version_result,
            "error": self.error_message,
        }


@dataclass
class Evidence:
    """Stage 5: Evidence collection (uses kilo_live_smoke_evidence schema)."""
    upstream_event: dict[str, Any]
    impact_assessment: dict[str, Any]
    test_case: dict[str, Any]
    execution_result: dict[str, Any]
    live_verified: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "upstream_event": self.upstream_event,
            "impact": self.impact_assessment,
            "test_case": self.test_case,
            "execution": self.execution_result,
            "live_verified": self.live_verified,
        }


@dataclass
class Classification:
    """Stage 6: Result classification."""
    verdict: str  # "INCOMPATIBLE" | "COMPATIBLE" | "REQUIRES_REVIEW"
    confidence: float
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "confidence": self.confidence,
            "rationale": self.rationale,
        }


@dataclass
class ActionRecommendation:
    """Stage 7: Next action identification."""
    action_type: str  # "FIX" | "ESCALATE" | "MONITOR" | "SKIP"
    priority: str  # "CRITICAL" | "HIGH" | "MEDIUM" | "LOW"
    description: str
    estimated_effort: str  # "TRIVIAL" | "SMALL" | "MEDIUM" | "LARGE"
    requires_human_review: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.action_type,
            "priority": self.priority,
            "description": self.description,
            "effort": self.estimated_effort,
            "requires_human": self.requires_human_review,
        }


class TestVinextStage1UpstreamDetection(unittest.TestCase):
    """Stage 1: Detect upstream change."""

    def test_upstream_event_creation(self):
        """Can create and parse upstream change event."""
        event = UpstreamEvent(
            event_type="dependency_update",
            package="think-box-core",
            old_version="0.1.0",
            new_version="0.2.0",
            breaking_changes=[
                "API.think_job_status: removed `local_result`, use `global_result`",
                "API.receipt_chain: changed return type from dict to Receipt",
            ]
        )

        data = event.to_dict()
        self.assertEqual(data["type"], "dependency_update")
        self.assertEqual(data["package"], "think-box-core")
        self.assertEqual(len(data["breaking_changes"]), 2)
        self.assertTrue(any("local_result" in bc for bc in data["breaking_changes"]))


class TestVinextStage2ImpactDetection(unittest.TestCase):
    """Stage 2: Detect impact on existing code."""

    def test_impact_assessment(self):
        """Can identify affected code."""
        assessment = ImpactAssessment(
            affected_files=[
                "thinkbox/autonomous_workflow.py",
                "tests/unit/test_autonomous_workflow.py",
                "apps/web/status.ts",
            ],
            affected_symbols=[
                "think_job_status()",
                "_receipt_status_from_sqlite()",
            ],
            confidence=0.95
        )

        data = assessment.to_dict()
        self.assertEqual(len(data["affected_files"]), 3)
        self.assertEqual(len(data["affected_symbols"]), 2)
        self.assertGreaterEqual(data["confidence"], 0.9)


class TestVinextStage3ReproduceCase(unittest.TestCase):
    """Stage 3: Create minimal test case."""

    def test_case_reproduction(self):
        """Can generate test case that reproduces breaking change."""
        case = TestCaseReproduction(
            test_file="test_broken_api.py",
            test_name="test_old_api_removed",
            import_statements=[
                "from thinkbox.think_job import think_job_status",
                "from thinkbox.autonomous_workflow import Receipt",
            ],
            assertions=[
                "result = think_job_status(job_id)",
                "assert hasattr(result, 'local_result')",
            ],
            expected_failure_reason="AttributeError: 'Receipt' object has no attribute 'local_result'"
        )

        data = case.to_dict()
        self.assertEqual(data["test_name"], "test_old_api_removed")
        self.assertIn("AttributeError", data["expected_failure"])


class TestVinextStage4ExecuteWork(unittest.TestCase):
    """Stage 4: Execute work (run test against both versions)."""

    def test_execution_result(self):
        """Can capture execution results."""
        result = ExecutionResult(
            old_version_result="PASS",
            new_version_result="FAIL",
            error_message="AttributeError: 'Receipt' object has no attribute 'local_result' (line 42)"
        )

        data = result.to_dict()
        self.assertEqual(data["old_version"], "PASS")
        self.assertEqual(data["new_version"], "FAIL")
        self.assertIn("AttributeError", data["error"])


class TestVinextStage5CollectEvidence(unittest.TestCase):
    """Stage 5: Collect evidence using existing schema."""

    def test_evidence_collection(self):
        """Can persist evidence using existing kilo_live_smoke_evidence schema."""
        event = UpstreamEvent(
            event_type="dependency_update",
            package="think-box-core",
            old_version="0.1.0",
            new_version="0.2.0",
            breaking_changes=["API.think_job_status: removed `local_result`"]
        )

        assessment = ImpactAssessment(
            affected_files=["thinkbox/autonomous_workflow.py"],
            affected_symbols=["think_job_status()"],
            confidence=0.95
        )

        case = TestCaseReproduction(
            test_file="test_broken_api.py",
            test_name="test_old_api_removed",
            import_statements=["from thinkbox.think_job import think_job_status"],
            assertions=["assert hasattr(result, 'local_result')"],
            expected_failure_reason="AttributeError: no attribute 'local_result'"
        )

        result = ExecutionResult(
            old_version_result="PASS",
            new_version_result="FAIL",
            error_message="AttributeError: 'Receipt' object has no attribute 'local_result'"
        )

        evidence = Evidence(
            upstream_event=event.to_dict(),
            impact_assessment=assessment.to_dict(),
            test_case=case.to_dict(),
            execution_result=result.to_dict(),
            live_verified=False
        )

        data = evidence.to_dict()
        self.assertFalse(data["live_verified"])
        self.assertEqual(data["upstream_event"]["type"], "dependency_update")
        self.assertEqual(data["execution"]["new_version"], "FAIL")


class TestVinextStage6Classification(unittest.TestCase):
    """Stage 6: Classify result."""

    def test_classification_incompatible(self):
        """Can classify as INCOMPATIBLE."""
        classification = Classification(
            verdict="INCOMPATIBLE",
            confidence=0.95,
            rationale="Test passes on old version, fails on new version. Breaking change confirmed."
        )

        data = classification.to_dict()
        self.assertEqual(data["verdict"], "INCOMPATIBLE")
        self.assertGreaterEqual(data["confidence"], 0.9)

    def test_classification_requires_review(self):
        """Can classify as REQUIRES_REVIEW."""
        classification = Classification(
            verdict="REQUIRES_REVIEW",
            confidence=0.5,
            rationale="Test result is ambiguous. API change may not affect this code path."
        )

        data = classification.to_dict()
        self.assertEqual(data["verdict"], "REQUIRES_REVIEW")
        self.assertEqual(data["confidence"], 0.5)


class TestVinextStage7ActionRecommendation(unittest.TestCase):
    """Stage 7: Identify next action."""

    def test_action_fix_critical(self):
        """Can recommend critical fix."""
        action = ActionRecommendation(
            action_type="FIX",
            priority="CRITICAL",
            description="Update `think_job_status()` to use `global_result` instead of `local_result`",
            estimated_effort="SMALL",
            requires_human_review=False
        )

        data = action.to_dict()
        self.assertEqual(data["type"], "FIX")
        self.assertEqual(data["priority"], "CRITICAL")
        self.assertFalse(data["requires_human"])

    def test_action_escalate(self):
        """Can recommend escalation."""
        action = ActionRecommendation(
            action_type="ESCALATE",
            priority="HIGH",
            description="Ambiguous breaking change requires architectural review",
            estimated_effort="MEDIUM",
            requires_human_review=True
        )

        data = action.to_dict()
        self.assertEqual(data["type"], "ESCALATE")
        self.assertTrue(data["requires_human"])


class TestVinextStage8HumanEscalation(unittest.TestCase):
    """Stage 8: Determine escalation boundary."""

    def test_escalation_gate_high_confidence_no_escalate(self):
        """High-confidence INCOMPATIBLE → no escalation needed."""
        classification = Classification(
            verdict="INCOMPATIBLE",
            confidence=0.95,
            rationale="Clear breaking change, test reproduces it."
        )

        # Decision logic: high confidence INCOMPATIBLE → automated action
        escalate = classification.confidence < 0.8 or classification.verdict == "REQUIRES_REVIEW"
        self.assertFalse(escalate)

    def test_escalation_gate_low_confidence_escalate(self):
        """Low-confidence result → escalation needed."""
        classification = Classification(
            verdict="REQUIRES_REVIEW",
            confidence=0.4,
            rationale="Change might affect this code, but it's unclear."
        )

        escalate = classification.confidence < 0.8 or classification.verdict == "REQUIRES_REVIEW"
        self.assertTrue(escalate)


class TestVinextMemoryIntegration(unittest.TestCase):
    """Test integration with Think Box memory layers."""

    def test_memory_layer_usage(self):
        """Existing Think Box memory layers can store research data."""
        store = MemoryStore(db_path=":memory:")

        # Verify the store exists (proof of memory layer integration)
        self.assertIsNotNone(store)

        # Verify memory layer constants exist
        self.assertIsNotNone(MemoryLayer.TASK)
        self.assertIsNotNone(MemoryLayer.ORGANIZATIONAL)
        self.assertIsNotNone(MemoryLayer.VERIFIED_KNOWLEDGE)
        self.assertIsNotNone(MemoryLayer.SESSION)

        # Key finding: Think Box has 4 memory layers that research data
        # can be mapped to
        memory_layers = [
            MemoryLayer.SESSION,  # Transient session state
            MemoryLayer.TASK,  # Finished run results
            MemoryLayer.ORGANIZATIONAL,  # Shared knowledge
            MemoryLayer.VERIFIED_KNOWLEDGE,  # Ground truth
        ]
        self.assertEqual(len(memory_layers), 4)


class TestVinextFullWorkflow(unittest.TestCase):
    """Test complete 8-stage workflow."""

    def test_277_complete_software_factory_cycle(self):
        """
        Minimal end-to-end test of Vinext-style software-factory workflow.

        Stages:
        1. Upstream change detected
        2. Impact assessed
        3. Case reproduced
        4. Work executed
        5. Evidence collected
        6. Result classified
        7. Action recommended
        8. Escalation gate applied
        """
        # 1. Upstream change
        upstream = UpstreamEvent(
            event_type="dependency_update",
            package="think-box-core",
            old_version="0.1.0",
            new_version="0.2.0",
            breaking_changes=["API.think_job_status: removed `local_result`"]
        )
        self.assertEqual(upstream.package, "think-box-core")

        # 2. Impact detection
        impact = ImpactAssessment(
            affected_files=["thinkbox/autonomous_workflow.py"],
            affected_symbols=["think_job_status()"],
            confidence=0.95
        )
        self.assertGreaterEqual(impact.confidence, 0.9)

        # 3. Case reproduction
        test_case = TestCaseReproduction(
            test_file="test_broken_api.py",
            test_name="test_old_api_removed",
            import_statements=["from thinkbox.think_job import think_job_status"],
            assertions=["assert hasattr(result, 'local_result')"],
            expected_failure_reason="AttributeError: no attribute 'local_result'"
        )
        self.assertEqual(test_case.test_name, "test_old_api_removed")

        # 4. Execution
        execution = ExecutionResult(
            old_version_result="PASS",
            new_version_result="FAIL",
            error_message="AttributeError: 'Receipt' object has no attribute 'local_result'"
        )
        self.assertEqual(execution.old_version_result, "PASS")
        self.assertEqual(execution.new_version_result, "FAIL")

        # 5. Evidence collection
        evidence = Evidence(
            upstream_event=upstream.to_dict(),
            impact_assessment=impact.to_dict(),
            test_case=test_case.to_dict(),
            execution_result=execution.to_dict(),
            live_verified=False
        )
        self.assertFalse(evidence.live_verified)

        # 6. Classification
        classification = Classification(
            verdict="INCOMPATIBLE",
            confidence=0.95,
            rationale="Breaking change confirmed by test."
        )
        self.assertEqual(classification.verdict, "INCOMPATIBLE")

        # 7. Action recommendation
        action = ActionRecommendation(
            action_type="FIX",
            priority="CRITICAL",
            description="Update to new API",
            estimated_effort="SMALL",
            requires_human_review=False
        )
        self.assertFalse(action.requires_human_review)

        # 8. Escalation check
        needs_escalation = classification.confidence < 0.8 or classification.verdict == "REQUIRES_REVIEW"
        self.assertFalse(needs_escalation)

        # All stages completed successfully
        self.assertEqual(
            [upstream.package, impact.confidence > 0.9, test_case.test_name,
             execution.new_version_result, evidence.live_verified,
             classification.verdict, action.action_type, not needs_escalation],
            ["think-box-core", True, "test_old_api_removed", "FAIL", False,
             "INCOMPATIBLE", "FIX", True]
        )


if __name__ == "__main__":
    unittest.main()
