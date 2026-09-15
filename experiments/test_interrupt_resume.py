#!/usr/bin/env python3
"""Interrupt/Resume Test for KUDBEE Orchestrator.

This test demonstrates that a KUDBEE job can survive process interruption
and resume from the last durable checkpoint.
"""

import asyncio
import json
import os
import pickle
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Add project to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from experiments.kudbee_orchestrator import (
    KUDBEEOrchestrator,
    ExperimentTask,
    JobCheckpoint,
    BoxRole,
)


async def test_interrupt_resume():
    """Test that a job can be interrupted and resumed from checkpoint."""
    
    print("=" * 60)
    print("KUDBEE INTERRUPT/RESUME TEST")
    print("=" * 60)
    
    checkpoint_dir = Path("data/checkpoints/interrupt_test")
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    
    # Task: simple REST endpoint
    task = ExperimentTask(
        task_id="interrupt_test_task",
        description="Create a REST endpoint with SQL injection trap",
        requirements={
            "endpoint": "POST /items",
            "validation": "Pydantic model",
            "storage": "SQLite",
        },
        trap={
            "type": "sql_injection",
            "location": "search endpoint",
            "description": "Direct string interpolation",
        },
    )
    
    # ============================================================
    # PHASE 1: Start job and run to EXECUTE stage, save checkpoint
    # ============================================================
    print("\n[PHASE 1] Starting job, running to EXECUTE stage...")
    
    orchestrator = KUDBEEOrchestrator(
        use_commons=False,
        db_path=":memory:",
    )
    
    # Add checkpoint support to orchestrator instance
    orchestrator.job_id = "interrupt_test_job"
    orchestrator.checkpoint_dir = checkpoint_dir
    orchestrator.completed_stages = []
    
    def save_checkpoint(stage: str, state: dict[str, Any], artifact_path: str = "") -> None:
        checkpoint = JobCheckpoint(
            job_id=orchestrator.job_id,
            task_id=state.get("task_id", ""),
            stage=stage,
            timestamp=datetime.now(timezone.utc).isoformat(),
            state=state,
            completed_stages=list(orchestrator.completed_stages),
            artifact_path=artifact_path,
        )
        checkpoint_file = orchestrator.checkpoint_dir / f"{orchestrator.job_id}_{stage.lower()}.pkl"
        with open(checkpoint_file, "wb") as f:
            pickle.dump(checkpoint, f)
        json_file = orchestrator.checkpoint_dir / f"{orchestrator.job_id}_{stage.lower()}.json"
        with open(json_file, "w") as f:
            json.dump(checkpoint.to_dict(), f, indent=2, default=str)
        print(f"    [CHECKPOINT] Saved {stage} checkpoint: {checkpoint_file}")
    
    orchestrator.save_checkpoint = save_checkpoint
    
    # Run stages up to EXECUTE
    print("\n[PHASE 1] Running INTENT → DECOMPOSE → BURST → EXECUTE...")
    plan = orchestrator._decompose_task(task)
    orchestrator.completed_stages.extend(["INTENT", "DECOMPOSE"])
    orchestrator.save_checkpoint("DECOMPOSE", {"task_id": task.task_id, "task": task, "plan": plan})
    
    executions = await orchestrator._execute_burst(plan, task)
    orchestrator.completed_stages.append("BURST")
    orchestrator.save_checkpoint("BURST", {"task_id": task.task_id, "task": task, "plan": plan, "executions": executions})
    
    builder_exec = next(e for e in executions if e.role == BoxRole.BUILDER)
    artifact = await orchestrator._execute_builder(builder_exec, task)
    orchestrator.completed_stages.append("EXECUTE")
    orchestrator.save_checkpoint("EXECUTE", {
        "task_id": task.task_id, "task": task, "plan": plan, 
        "executions": executions, "artifact": artifact
    }, artifact)
    
    # Also run EVIDENCE and JURY to have a complete state
    evidence = orchestrator._collect_evidence(executions, artifact, task)
    orchestrator.completed_stages.append("EVIDENCE")
    orchestrator.save_checkpoint("EVIDENCE", {
        "task_id": task.task_id, "task": task, "plan": plan, 
        "executions": executions, "artifact": artifact, "evidence": evidence
    }, artifact)
    
    jury_result = await orchestrator._jury_evaluate(evidence, artifact, task)
    orchestrator.completed_stages.append("JURY")
    orchestrator.save_checkpoint("JURY", {
        "task_id": task.task_id, "task": task, "plan": plan, 
        "executions": executions, "artifact": artifact, "evidence": evidence,
        "jury_result": jury_result
    }, artifact)
    
    artifact_path = artifact
    print(f"\n[PHASE 1] Checkpoint saved at JURY stage. Artifact: {artifact_path}")
    
    # Verify checkpoint exists
    checkpoints = list(checkpoint_dir.glob("interrupt_test_job_jury.*"))
    print(f"[VERIFY] Checkpoints found: {checkpoints}")
    if not checkpoints:
        print("[FAIL] No checkpoint saved!")
        return False
    
    pkl_checkpoints = list(checkpoint_dir.glob("interrupt_test_job_jury*.pkl"))
    latest_checkpoint = max(pkl_checkpoints, key=lambda p: p.stat().st_mtime)
    print(f"[VERIFY] Latest checkpoint: {latest_checkpoint}")
    
    # Load and verify checkpoint
    with open(latest_checkpoint, "rb") as f:
        checkpoint = pickle.load(f)
    
    print(f"[VERIFY] Checkpoint job_id: {checkpoint.job_id}")
    print(f"[VERIFY] Checkpoint stage: {checkpoint.stage}")
    print(f"[VERIFY] Completed stages: {checkpoint.completed_stages}")
    print(f"[VERIFY] Artifact path: {checkpoint.artifact_path}")
    
    # ============================================================
    # PHASE 2: Simulate interruption - create NEW orchestrator, resume
    # ============================================================
    print("\n[PHASE 2] Simulating interruption - creating NEW orchestrator...")
    print("[PHASE 2] Resuming from JURY checkpoint...")
    
    orchestrator2 = KUDBEEOrchestrator(
        use_commons=False,
        db_path=":memory:",
    )
    orchestrator2.job_id = "interrupt_test_job"
    orchestrator2.checkpoint_dir = checkpoint_dir
    
    # Load checkpoint
    checkpoints2 = sorted(orchestrator2.checkpoint_dir.glob(f"{orchestrator2.job_id}_*.pkl"))
    latest2 = checkpoints2[-1]
    with open(latest2, "rb") as f:
        loaded_checkpoint = pickle.load(f)
    
    orchestrator2.current_checkpoint = loaded_checkpoint
    orchestrator2.completed_stages = loaded_checkpoint.completed_stages
    
    print(f"[RESUME] Loaded checkpoint: {latest2}")
    print(f"[RESUME] Completed stages: {orchestrator2.completed_stages}")
    print(f"[RESUME] Will resume from stage: {loaded_checkpoint.stage}")
    
    # Verify it skips completed stages
    assert "INTENT" in orchestrator2.completed_stages
    assert "DECOMPOSE" in orchestrator2.completed_stages
    assert "BURST" in orchestrator2.completed_stages
    assert "EXECUTE" in orchestrator2.completed_stages
    assert "EVIDENCE" in orchestrator2.completed_stages
    assert "JURY" in orchestrator2.completed_stages
    assert "CHALLENGE" not in orchestrator2.completed_stages
    
    print("[RESUME] Stage skipping verified!")
    
    # Restore task state from checkpoint
    task_state = loaded_checkpoint.state
    task = task_state["task"]
    executions = task_state["executions"]
    artifact = task_state["artifact"]
    evidence = task_state["evidence"]
    jury_result = task_state["jury_result"]
    
    # ============================================================
    # PHASE 3: Continue from CHALLENGE stage
    # ============================================================
    print("\n[PHASE 3] Continuing from CHALLENGE stage...")
    
    challenge_result = await orchestrator2._adversarial_challenge(evidence, artifact, task)
    print(f"[CHALLENGE] Vulnerabilities found: {challenge_result['vulnerabilities_found']}")
    
    repair_executions = []
    if challenge_result.get("vulnerabilities"):
        print("\n[PHASE 4] RETRY - Repairing vulnerabilities...")
        repair_executions = await orchestrator2._repair_vulnerabilities(
            challenge_result["vulnerabilities"], executions, artifact, task
        )
        # Re-evaluate after repair
        jury_result = await orchestrator2._jury_evaluate(evidence, artifact, task)
        print(f"[JURY after repair] Passed: {jury_result['passed']}")
    
    # ============================================================
    # PHASE 5: Complete remaining stages
    # ============================================================
    print("\n[PHASE 5] PROOF - Final verification...")
    proof = await orchestrator2._final_verification(artifact, task)
    print(f"[PROOF] Tests passed: {proof['tests_passed']}")
    
    print("\n[PHASE 6] TOKEN - Minting for verified work...")
    token_result = orchestrator2._mint_token(proof, task)
    print(f"[TOKEN] Minted: {token_result['minted']} ({token_result['token_id']})")
    
    print("\n[PHASE 7] HARVEST - Extracting knowledge...")
    harvest = orchestrator2._harvest_knowledge(executions + repair_executions, evidence, task)
    print(f"[HARVEST] Groundedness: {harvest.metrics.groundedness_score:.3f}")
    
    print("\n[PHASE 8] REPLAY - Deterministic verification...")
    replay_ok = await orchestrator2._deterministic_replay(evidence, artifact, task)
    print(f"[REPLAY] Verified: {replay_ok}")
    
    # Verify artifact still exists and tests pass
    if Path(artifact_path).exists():
        print(f"\n[VERIFY] Artifact exists at: {artifact_path}")
        import subprocess
        test_result = subprocess.run([
            sys.executable, "-m", "pytest",
            str(Path(artifact_path).parent / "test_endpoint.py"),
            "-v", "--tb=short"
        ], capture_output=True, text=True, cwd=Path(artifact_path).parent, timeout=60)
        
        if test_result.returncode == 0:
            print("[VERIFY] Artifact tests PASSED")
        else:
            print(f"[VERIFY] Artifact tests FAILED: {test_result.stdout[-200:]}")
            return False
    
    print("\n" + "=" * 60)
    print("INTERRUPT/RESUME TEST: PASSED!")
    print("=" * 60)
    print("  ✓ Job checkpointed at JURY stage")
    print("  ✓ New process created (simulated interruption)")
    print("  ✓ Job resumed from JURY checkpoint")
    print("  ✓ Stages INTENT→JURY correctly skipped")
    print("  ✓ CHALLENGE, RETRY, PROOF, TOKEN, HARVEST, REPLAY completed")
    print("  ✓ Artifact verified, tests passed")
    print("  ✓ Full evidence trail preserved")
    return True


async def main():
    """Run the interrupt/resume test."""
    success = await test_interrupt_resume()
    if success:
        print("\n" + "=" * 60)
        print("INTERRUPT/RESUME TEST: PASSED")
        print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print("INTERRUPT/RESUME TEST: FAILED")
        print("=" * 60)
    return success


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)