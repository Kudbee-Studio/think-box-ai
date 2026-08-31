# DEPLOYMENT.md — Running Think Box AI

## Quick Start (Local Machine)

```bash
# 1. Clone and branch
git clone https://github.com/Kudbee-Studio/think-box-ai.git
cd think-box-ai
git checkout session/agent_79e656bf-37c6-46f2-833e-1eb027b99152

# 2. Install dependencies
pip install -r backend/requirements.txt

# 3. Configure (choose one)
# Option A: Local Ollama
ollama pull llama3.1:8b
# Default config works — just run.

# Option B: FreeToken on GPU (when started by Kudbee)
export THINKBOX_DEFAULT_PROVIDER=openai_compat
export THINKBOX_OPENAI_COMPAT_BASE_URL=http://87.58.150.62:1919/v1
export THINKBOX_DEFAULT_MODEL=qwen/qwen3.6-27b

# Option C: OpenAI-compatible (generic)
export THINKBOX_DEFAULT_PROVIDER=openai_compat
export THINKBOX_OPENAI_COMPAT_API_KEY=sk-...
export THINKBOX_OPENAI_COMPAT_BASE_URL=https://api.openai.com/v1
export THINKBOX_DEFAULT_MODEL=gpt-4o-mini

# 4. Run
python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000

# 5. Test
curl http://localhost:8000/health
curl -X POST http://localhost:8000/run \
  -H "Content-Type: application/json" \
  -d '{"goal": "List files in data/ directory"}'
```

## Upstash Box Limitations

The Upstash Box sandbox has limited HTTPS outbound access.

**Box CAN reach:**
- api.github.com
- api.doginals.org (health only)

**Box CANNOT reach:**
- api.inception.ai (CDN SNI reject)
- wonky-ord.dogeord.io (DNS dead)
- ordinalswallet.com (timeout)
- dogechain.info (Cloudflare 403)

**Workaround:** Run the backend locally or use GPU server for model inference.

## Provider Status (as of 2026-08-31)

| Provider | Box | Cloud | Notes |
|----------|-----|-------|-------|
| Ollama (local) | ❌ Not installed | ❌ Not installed | Install locally |
| FreeToken (GPU) | ❌ No GPU | ✅ When started | At 87.58.150.62:1919 |
| OpenAI | ✅ Reachable | ✅ Reachable | Needs valid key |

**Provider order:** Ollama → FreeToken → OpenAI-compatible

## Tools Available (18 total)

| Tool | Purpose |
|------|---------|
| fs_read / fs_write / fs_list | Filesystem access (jailed to repo + data/) |
| http_get | HTTP GET with rate limiting (400ms/host) |
| memory_put / memory_get / memory_search | SQLite research memory |
| indexer_health | Check which indexers are reachable |
| doge_tx | Fetch Dogecoin transaction |
| doginals_inscription | Fetch inscription from indexer |
| compare_inscription | Compare across multiple indexers |
| parse_drc20 | Parse DRC-20 JSON operations |
| load_fixture | Load test data from fixtures/ |
| shell_exec | Execute shell commands |
| file_read / file_write | Legacy file tools |
| http_request / memory_query | Legacy HTTP and memory tools |
