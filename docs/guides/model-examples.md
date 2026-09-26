# Model Execution Examples

Real-world examples for executing models through Think Box AI. All examples assume environment variables are configured (see `environment-variables.md`).

---

## Basic Execution

### Simple Synchronous Call

```python
import asyncio
from thinkbox.model_client import AsyncModelClient, ModelConfig

async def basic_call():
    config = ModelConfig.from_env()
    client = AsyncModelClient(config)
    
    try:
        response = await client.generate("What is 2+2?")
        print(f"Response: {response}")
    finally:
        await client.close()

asyncio.run(basic_call())
```

### Streaming Response

```python
async def streaming_call():
    config = ModelConfig.from_env()
    client = AsyncModelClient(config)
    
    try:
        async for token in client.stream("Explain quantum computing in 3 sentences"):
            print(token, end="", flush=True)
        print()  # Newline at end
    finally:
        await client.close()

asyncio.run(streaming_call())
```

---

## Autonomous Workflow Pattern

The complete Sense → Decide → Act → Learn cycle:

```python
import asyncio
from datetime import datetime
from thinkbox.model_client import AsyncModelClient, ModelConfig
from core.memory.store import MemoryStore
from core.memory.schema import MemoryEntry, MemoryLayer, MemoryEntryType

async def autonomous_loop(goal: str, observations: list[str]):
    """Run one cycle of autonomous decision loop."""
    config = ModelConfig.from_env()
    client = AsyncModelClient(config)
    memory = MemoryStore("./data/memory.db")
    
    try:
        # Step 1: SENSE — Observe the current state
        print("📥 SENSE: Observing...")
        current_observation = observations[-1]  # Latest observation
        
        # Store observation in SESSION memory
        memory.put(MemoryEntry(
            key=f"observation_{datetime.now().timestamp()}",
            layer=MemoryLayer.SESSION,
            entry_type=MemoryEntryType.REASONING_STEP,
            value={"observation": current_observation}
        ))
        
        # Step 2: DECIDE — Get model's decision
        print("🤖 DECIDE: Consulting model...")
        prompt = f"""
        Goal: {goal}
        Current observation: {current_observation}
        
        What is the next action? Return JSON:
        {{
            "action": "...",
            "reasoning": "...",
            "confidence": 0.0-1.0
        }}
        """
        
        decision = await client.generate(prompt)
        print(f"Decision: {decision[:100]}...")
        
        # Step 3: ACT — Execute the decision
        print("⚙️  ACT: Recording decision...")
        memory.put(MemoryEntry(
            key=f"decision_{datetime.now().timestamp()}",
            layer=MemoryLayer.SESSION,
            entry_type=MemoryEntryType.REASONING_STEP,
            value={"decision": decision, "goal": goal}
        ))
        
        # Step 4: LEARN — Extract and record lesson
        print("📚 LEARN: Extracting lesson...")
        lesson_prompt = f"""
        Based on goal "{goal}" and decision "{decision}", 
        what should we remember for next time?
        Return JSON: {{"lesson": "...", "applies_to": "..."}}
        """
        
        lesson = await client.generate(lesson_prompt)
        
        # Store as organizational pattern (append-only)
        memory.put(MemoryEntry(
            key=f"pattern_{goal.replace(' ', '_')}_{datetime.now().timestamp()}",
            layer=MemoryLayer.ORGANIZATIONAL,
            entry_type=MemoryEntryType.PATTERN,
            value={
                "goal": goal,
                "lesson": lesson,
                "timestamp": datetime.now().isoformat()
            }
        ))
        
        print("✅ Autonomous cycle complete")
        
    finally:
        await client.close()
        memory.close()

# Run it
asyncio.run(autonomous_loop(
    goal="Optimize response latency",
    observations=[
        "Baseline latency: 850ms",
        "Tried caching: 220ms",
        "Added connection pooling: 180ms"
    ]
))
```

---

## Batch Processing

Process multiple prompts efficiently:

```python
async def batch_process(prompts: list[str]) -> list[str]:
    """Process multiple prompts with a single client."""
    config = ModelConfig.from_env()
    client = AsyncModelClient(config)
    
    try:
        results = []
        for i, prompt in enumerate(prompts):
            print(f"Processing {i+1}/{len(prompts)}...", end="\r")
            response = await client.generate(prompt)
            results.append(response)
        
        print(f"\n✅ Processed {len(prompts)} prompts")
        return results
        
    finally:
        await client.close()

# Usage
prompts = [
    "What is machine learning?",
    "Explain neural networks briefly",
    "What is an embedding?"
]

responses = asyncio.run(batch_process(prompts))
for prompt, response in zip(prompts, responses):
    print(f"\nQ: {prompt}")
    print(f"A: {response[:100]}...")
```

---

## Error Handling

Graceful error handling with retry logic:

```python
import asyncio
from thinkbox.model_client import AsyncModelClient, ModelConfig, ModelCallError

async def call_with_retry(prompt: str, max_retries: int = 3) -> str | None:
    """Call model with exponential backoff on transient errors."""
    config = ModelConfig.from_env()
    client = AsyncModelClient(config)
    
    try:
        for attempt in range(max_retries):
            try:
                return await client.generate(prompt)
            except ModelCallError as e:
                if e.retryable and attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff
                    print(f"Retrying in {wait_time}s (attempt {attempt + 1})...")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    print(f"❌ Failed: {e}")
                    return None
    finally:
        await client.close()

# Usage
result = asyncio.run(call_with_retry("Briefly explain AI"))
if result:
    print(f"✅ Success: {result[:100]}...")
```

---

## Testing Without Tokens

Dry-run the autonomous loop without calling the model:

```python
def test_autonomous_workflow_dry_run():
    """Validate workflow without calling model."""
    from core.memory.store import MemoryStore
    from core.memory.schema import MemoryEntry, MemoryLayer, MemoryEntryType
    
    memory = MemoryStore(":memory:")  # In-memory for testing
    
    # Simulate Sense step
    memory.put(MemoryEntry(
        key="obs_1",
        layer=MemoryLayer.SESSION,
        entry_type=MemoryEntryType.REASONING_STEP,
        value={"observation": "cache miss rate: 30%"}
    ))
    
    # Simulate Decide step (mock decision)
    mock_decision = '{"action": "enable_compression", "confidence": 0.85}'
    memory.put(MemoryEntry(
        key="dec_1",
        layer=MemoryLayer.SESSION,
        entry_type=MemoryEntryType.REASONING_STEP,
        value={"decision": mock_decision}
    ))
    
    # Simulate Learn step
    memory.put(MemoryEntry(
        key="pattern_1",
        layer=MemoryLayer.ORGANIZATIONAL,
        entry_type=MemoryEntryType.PATTERN,
        value={"lesson": "compression reduces cache misses"}
    ))
    
    # Verify all steps stored
    assert memory.count(MemoryLayer.SESSION) == 2
    assert memory.count(MemoryLayer.ORGANIZATIONAL) == 1
    
    print("✅ Dry-run workflow validates successfully")

test_autonomous_workflow_dry_run()
```

---

## Concurrent Goals

Execute multiple goals in parallel with shared budget:

```python
import asyncio
from thinkbox.model_client import AsyncModelClient, ModelConfig

async def concurrent_goals(goals: list[str], shared_budget: int = 10000):
    """Execute multiple goals concurrently."""
    config = ModelConfig.from_env()
    client = AsyncModelClient(config)
    
    async def execute_goal(goal: str):
        try:
            response = await client.generate(f"Solve: {goal}")
            return {"goal": goal, "status": "success", "result": response[:50]}
        except Exception as e:
            return {"goal": goal, "status": "error", "error": str(e)}
    
    try:
        # Run all goals concurrently
        results = await asyncio.gather(*[execute_goal(g) for g in goals])
        
        successes = sum(1 for r in results if r["status"] == "success")
        print(f"✅ {successes}/{len(goals)} goals completed")
        
        return results
        
    finally:
        await client.close()

# Usage
goals = [
    "What is machine learning?",
    "Explain deep learning",
    "Describe transformers"
]

results = asyncio.run(concurrent_goals(goals))
for result in results:
    print(f"\n{result['goal']}: {result['status']}")
```

---

## Performance Monitoring

Track model execution metrics:

```python
import time
import asyncio
from thinkbox.model_client import AsyncModelClient, ModelConfig

async def call_with_metrics(prompt: str) -> dict:
    """Call model and track performance metrics."""
    config = ModelConfig.from_env()
    client = AsyncModelClient(config)
    
    start_time = time.time()
    
    try:
        response = await client.generate(prompt)
        
        elapsed = time.time() - start_time
        
        return {
            "success": True,
            "response": response,
            "latency_ms": int(elapsed * 1000),
            "response_length": len(response)
        }
    except Exception as e:
        elapsed = time.time() - start_time
        return {
            "success": False,
            "error": str(e),
            "latency_ms": int(elapsed * 1000)
        }
    finally:
        await client.close()

# Usage
metrics = asyncio.run(call_with_metrics("Explain AI in one sentence"))
if metrics["success"]:
    print(f"✅ {metrics['latency_ms']}ms | {metrics['response_length']} chars")
else:
    print(f"❌ {metrics['latency_ms']}ms | {metrics['error']}")
```

---

## Integration with Proof Script

The `scripts/prove_autonomous_workflow.py` combines all these patterns:

```bash
# Run the full proof
python3 scripts/prove_autonomous_workflow.py

# Expected: 4/4 tests PASS
```

Check its source for the canonical implementation of these patterns.

