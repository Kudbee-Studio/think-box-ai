# Environment Variables — Model Execution

## Overview

Think Box AI supports multiple model providers through environment variables. This guide documents the correct setup for running the model.

## Core Configuration

### Default Provider Selection
```bash
export THINKBOX_DEFAULT_PROVIDER=inception  # or: openai_compat, ollama
export THINKBOX_DEFAULT_MODEL=mercury-2
```

### Inception API (Mercury-2)

Mercury-2 is a reasoning model requiring at least 3500 tokens for reasoning budget.

```bash
# Required
export INCEPTION_API_KEY=sk_xxxxxxxxxxxxxxxxxxxxxxx

# Optional (auto-detected)
export INCEPTION_BASE_URL=https://api.inceptionlabs.ai/v1
```

**Verification:**
```bash
python3 -c "
import asyncio, os
from thinkbox.model_client import AsyncModelClient, ModelConfig

async def test():
    os.environ['THINKBOX_DEFAULT_PROVIDER'] = 'inception'
    config = ModelConfig.from_env()
    client = AsyncModelClient(config)
    try:
        response = await client.generate('Say: 42')
        print(f'✅ Model OK: {response[:50]}')
    finally:
        await client.close()

asyncio.run(test())
"
```

### OpenAI-Compatible Providers (OpenAI, Groq, vLLM)

```bash
export THINKBOX_DEFAULT_PROVIDER=openai_compat
export THINKBOX_OPENAI_COMPAT_API_KEY=sk_xxxxxxx
export THINKBOX_OPENAI_COMPAT_BASE_URL=https://api.openai.com/v1
export THINKBOX_DEFAULT_MODEL=gpt-4o-mini
```

### Local Ollama

```bash
export THINKBOX_DEFAULT_PROVIDER=ollama
export THINKBOX_OLLAMA_BASE_URL=http://localhost:11434
export THINKBOX_DEFAULT_MODEL=llama3.1:8b
```

## Persistence & Vector Storage

### Upstash Redis
```bash
export UPSTASH_REDIS_REST_URL=https://certain-mongrel-xxxxx.upstash.io
export UPSTASH_REDIS_REST_TOKEN=your-token
```

### Upstash Vector (Session Memory)
```bash
export UPSTASH_VECTOR_REST_URL=https://xxxxx.upstash.io
export UPSTASH_VECTOR_REST_TOKEN=your-token
# Embedder configuration (if needed)
export THINKBOX_EMBED_MODEL=mercury-2
export THINKBOX_OPENAI_COMPAT_API_KEY=<key-for-embeddings>
```

## Important Notes

1. **API Key Naming**: Inception uses `INCEPTION_API_KEY` (with `_KEY` suffix). This is required by `ModelConfig.from_env()`.
2. **Mercury-2 Min Tokens**: Must set `max_tokens >= 3500` for reasoning to work. The code defaults this automatically.
3. **Fail-Closed Model Errors**: Model call failures raise `ModelCallError` and are never returned as simulated output.

## Checking Your Setup

```bash
# Show resolved configuration
python3 -c "
import os
from thinkbox.model_client import ModelConfig

config = ModelConfig.from_env()
print(f'Provider: {config.api_type}')
print(f'Model: {config.model}')
print(f'Base URL: {config.base_url}')
print(f'Max tokens: {config.max_tokens}')
print(f'Has API key: {bool(config.api_key)}')
"
```

## Testing with Bounded Calls

For testing without burning token budget:

```bash
python3 -c "
import asyncio, os
from thinkbox.model_client import AsyncModelClient, ModelConfig

async def test_bounded():
    config = ModelConfig.from_env()
    config.temperature = 0.2  # Lower temp for consistency
    config.max_tokens = 512   # Bounded output
    
    client = AsyncModelClient(config)
    try:
        response = await client.generate('What is 2+2? Respond in JSON.')
        print(f'Response: {response}')
    finally:
        await client.close()

asyncio.run(test_bounded())
"
```

## Troubleshooting

### `ModelCallError: HTTP 401: Incorrect API key`
- **Cause**: `INCEPTION_API_KEY` not set or incorrect
- **Fix**: Verify env var name is exactly `INCEPTION_API_KEY` (case-sensitive)
- **Test**: `echo $INCEPTION_API_KEY | wc -c` should be ~36 (35 + newline)

### `ModelCallError: openai_compat:mercury-2 timeout`
- **Cause**: Network issue or endpoint slow
- **Fix**: Check connectivity to `api.inceptionlabs.ai` and increase timeout in code if needed

### `None` returned for reasoning model
- **Cause**: `max_tokens` too low for Mercury-2 reasoning
- **Fix**: Ensure `max_tokens >= 3500` (set automatically by `ModelConfig.from_env()`)

## For Production

1. Store API keys in a secrets manager, not `.env` files
2. Rotate keys regularly
3. Monitor rate limits and adjust concurrency accordingly
4. Use governed execution (`GovernedEngine`) for audit trails
5. Test model provider failover for high availability

## Think Token extraction (apps/web, ADR 029)

Read only from the environment (the server also loads the repo-root `.env`). Never print, log or commit these.

| Variable | Purpose | Default |
|---|---|---|
| `INCEPTION_API_KEY_2` | Key for Think Token extraction and challenge with Mercury 2 (separate from `INCEPTION_API_KEY`, which the worker agent uses) | unset: the local model is used |
| `THINKBOX_TOKEN_MODEL` | Mercury model name for those calls | `mercury-2` |
| `THINKBOX_LOCAL_MODEL` | Already-installed Ollama model for the fallback (older name `KUDBEE_LOCAL_MODEL`); the app never pulls models | `qwen2.5:1.5b` |
| `THINKBOX_TOKEN_MODEL_CALLS_PER_RUN` | Cap on extraction + challenge model calls per run (a failed Mercury call is retried once and counts) | `10` |
| `THINKBOX_TOKEN_MODEL_CALLS_PER_DAY` | Cap on those calls per day | `200` |
| `KUDBEE_JANUS_ENABLED` | `1` or `true` turns on the optional Janus image service in the dashboard (`image_analyze`, `image_generate`, monitor check); `JANUS_BASE_URL` (default `http://127.0.0.1:8001`) says where it listens. Off by default because of CVE-2026-69112, see `docs/SECURITY.md` | off |
| `THINKBOX_TOKEN_RETRIEVAL` | `0` or `off` stops injecting accepted Think Tokens into the planner context (for A/B proof runs: `scripts/think-token-ab-live.mjs`); any other value leaves retrieval on | on |
| `THINKBOX_TOKEN_CLOCK` | Epoch milliseconds to use as "now" in Think Token retrieval scoring (the recency term); set it for evals and A/B runs so rankings do not drift with the date | real clock |
| `THINKBOX_EMBEDDINGS` | `off` (or `0`) disables local semantic retrieval; goals are then ranked lexically. Needs the optional `@huggingface/transformers` package | on |
| `THINKBOX_EMBED_MODEL` | Sentence-embedding model (Hugging Face id) used for lesson/goal vectors; vectors are stored per model | `Xenova/all-MiniLM-L6-v2` (about 23 MB, CPU, downloaded once, then offline) |
| `THINKBOX_EMBED_CACHE` | Directory for the downloaded model | `<KUDBEE_DATA_DIR or apps/web/data>/models` |
| `THINKBOX_RETRIEVER` | Ranker: `cosine` (default), `cosine-tiebreak` (cosine first, BM25 breaks ties within 0.02), `hybrid` (P3.6: BM25 + cosine + failure modes), or `lexical` (P3.2). The cosine rankers need vectors and fall back to lexical without them | `cosine` |
| `THINKBOX_EVIDENCE_CHECK` | `off` disables the final-answer check against this run's tool results (ADR 029 P3.9/P3.10); on by default | on |
| `KUDBEE_THINK_TOKEN_DB` | Path of the Think Token SQLite file | `<KUDBEE_DATA_DIR or apps/web/data>/think-tokens.db` |

Prompts for Mercury leave the machine: secrets and absolute paths are removed and inputs are size-capped first.
