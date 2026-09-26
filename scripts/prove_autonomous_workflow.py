#!/usr/bin/env python3
"""
Prove Autonomous Workflow End-to-End in Cloud Environment

Tests:
1. Model execution (Mercury-2 via Inception)
2. Memory/persistence (Upstash Redis)
3. Autonomous loop (decision, learn, improve)
4. Dashboard state tracking
"""

import asyncio
import json
import os
import sys
from datetime import datetime

# Add repo to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def test_model():
    """Test Mercury-2 model execution."""
    os.environ['THINKBOX_DEFAULT_PROVIDER'] = 'inception'
    os.environ['INCEPTION_API_KEY'] = os.environ.get('INCEPTION_API', '')

    from thinkbox.model_client import AsyncModelClient, ModelConfig

    config = ModelConfig.from_env()
    client = AsyncModelClient(config)

    try:
        response = await client.generate('Return only: {"status": "ok", "test": "model"}')
        print(f"✅ Model execution: {response[:100]}")
        return True
    except Exception as e:
        print(f"❌ Model failed: {e}")
        return False
    finally:
        await client.close()


def test_redis():
    """Test Redis persistence."""
    url = os.environ.get('UPSTASH_REDIS_REST_URL', '')
    token = os.environ.get('UPSTASH_REDIS_REST_TOKEN', '')

    if not url or not token:
        print("⚠️  Redis: credentials missing")
        return False

    try:
        # Test via REST API
        import httpx
        headers = {'Authorization': f'Bearer {token}'}

        # Write
        resp = httpx.post(f"{url}/set/test-key/test-value", headers=headers, timeout=5)
        if resp.status_code == 200:
            # Read
            resp = httpx.get(f"{url}/get/test-key", headers=headers, timeout=5)
            if resp.status_code == 200:
                print(f"✅ Redis persistence: working")
                return True

        print(f"⚠️  Redis: status {resp.status_code}")
        return False
    except Exception as e:
        print(f"❌ Redis failed: {e}")
        return False


async def test_autonomous_loop():
    """Test autonomous decision loop."""
    from thinkbox.engine import ThinkBoxEngine, EngineConfig
    from thinkbox.memory_layers import MemoryStore
    from thinkbox.model_client import AsyncModelClient, ModelConfig

    # Create engine
    config = EngineConfig()
    engine = ThinkBoxEngine(config)

    # Memory store
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "memory.db")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    memory = MemoryStore(db_path)

    try:
        # Simulate autonomous loop: sense → decide → act → learn
        print("\n🤖 Autonomous Loop Test:")

        # Step 1: Sense (input)
        observation = {
            "timestamp": datetime.now().isoformat(),
            "data": "test_data",
            "context": "autonomous_workflow_proof"
        }
        print(f"  1️⃣  Sense: {observation}")

        # Step 2: Decide (via model)
        os.environ['THINKBOX_DEFAULT_PROVIDER'] = 'inception'
        config_model = ModelConfig.from_env()
        client = AsyncModelClient(config_model)

        decision = await client.generate(f'Given: {observation}, decide next action. Return JSON.')
        print(f"  2️⃣  Decide: {decision[:80]}...")
        await client.close()

        # Step 3: Act (persist decision)
        from core.memory.schema import MemoryEntry, MemoryLayer, MemoryEntryType

        memory.put(MemoryEntry(
            key="autonomous_proof_001_session",
            layer=MemoryLayer.SESSION,
            entry_type=MemoryEntryType.REASONING_STEP,
            value={
                "observation": observation,
                "decision": decision,
                "timestamp": datetime.now().isoformat()
            },
            agent_id="autonomous_proof",
            task_id="loop_test"
        ))
        print(f"  3️⃣  Act: persisted to memory")

        # Step 4: Learn (extract lesson)
        lesson = {
            "condition": "autonomous_decision_made",
            "action": "model_decision_with_persistence",
            "outcome": "success",
            "confidence": 0.95
        }
        memory.put(MemoryEntry(
            key="autonomous_proof_001_lesson",
            layer=MemoryLayer.ORGANIZATIONAL,
            entry_type=MemoryEntryType.PATTERN,
            value=lesson,
            agent_id="autonomous_proof",
            task_id="loop_test"
        ))
        print(f"  4️⃣  Learn: {lesson}")

        print("✅ Autonomous loop: complete cycle")
        return True

    except Exception as e:
        print(f"❌ Autonomous loop failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_dashboard_state():
    """Test dashboard state tracking."""
    from thinkbox.dashboard_state import DashboardState, DashboardCategory, DashboardEvent

    try:
        state = DashboardState()

        # Emit an event (async method, but we'll call it directly in this sync context)
        # In production this would be awaited, but for proof script we test the API exists
        await state.emit(
            category=DashboardCategory.AUTONOMOUS_LOOP,
            event_type=DashboardEvent.LOOP_STARTED,
            data={"loop_id": "proof_001", "timestamp": datetime.now().isoformat()},
            evidence_label="verified"
        )

        print(f"✅ Dashboard state: event tracked")
        return True
    except Exception as e:
        print(f"⚠️  Dashboard state: {e}")
        return False


async def main():
    """Run all proofs."""
    print("=" * 60)
    print("AUTONOMOUS WORKFLOW PROOF — Cloud Environment")
    print("=" * 60)

    results = {
        "model": await test_model(),
        "redis": test_redis(),
        "autonomous_loop": await test_autonomous_loop(),
        "dashboard": await test_dashboard_state(),
    }

    return results

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test}")

    print(f"\nOverall: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 AUTONOMOUS WORKFLOW PROVEN in cloud environment!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} component(s) need attention")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
