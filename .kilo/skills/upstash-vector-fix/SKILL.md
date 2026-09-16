# Skill: upstash-vector-fix

**Description:** Debug and fix Upstash Vector write failures

# When to Use

Use when Upstash Vector writes fail (HTTP 422, silent failures, or missing vectors in upsert payloads).

# Prerequisites

- Read `data/findings/thinkboxmd_upstash_vector_defect.md` first
- Check `thinkbox/session.py::UpstashVectorSync` and `thinkbox/embedder.py`

# Workflow

## Step 1 — Verify Index Type

```bash
curl -X GET "$UPSTASH_VECTOR_REST_URL/info" \
  -H "Authorization: Bearer $UPSTASH_VECTOR_REST_TOKEN"
```

Check: `indexType` — must be `DENSE` with matching `dimension`.

## Step 2 — Verify Embedder

```python
from thinkbox.embedder import OpenAICompatEmbedder, DeterministicEmbedder
# Production:
embedder = OpenAICompatEmbedder()  # needs THINKBOX_OPENAI_COMPAT_API_KEY + BASE_URL
# Test stub:
embedder = DeterministicEmbedder()  # 1536-dim hash, test-only
vectors = embedder.embed(["test"])
assert len(vectors[0]) == 1536
```

## Step 3 — Verify Upsert Payload Shape

```python
from thinkbox.session import UpstashVectorSync, SessionContext
sync = UpstashVectorSync(embedder=embedder)
session = SessionContext("test", "local", "Ollama", "user")
# Check payload includes "vector" field
```

The upsert payload must contain:
- `id` — session ID
- `vector` — list of 1536 floats
- `metadata` — session info dict

## Step 4 — Fix Failures

If upsert fails with 422:
1. Confirm vector is included in payload
2. Confirm vector dimension matches index dimension
3. Confirm embedder produces valid floats (not null, not strings)

If no embedder available:
1. Set `THINKBOX_OPENAI_COMPAT_API_KEY` and `THINKBOX_OPENAI_COMPAT_BASE_URL`
2. Or pass `DeterministicEmbedder()` for tests
3. **Never** run production upsert without a real embedder

## Step 5 — Test

```bash
python3 -m unittest tests.unit.test_session_tracker.TestUpstashVectorSyncEmbedder -v
```

Expect: all 9 tests pass.

# Rules

- Fail closed: raise EmbeddingError, never return silent False
- Never use DeterministicEmbedder in production
- Always verify payload shape before claiming success
