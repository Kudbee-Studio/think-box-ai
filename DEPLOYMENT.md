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

# Option B: Inception API (Mercury 2, ~1M free tokens)
export THINKBOX_DEFAULT_PROVIDER=openai_compat
export THINKBOX_OPENAI_COMPAT_API_KEY=sk_63c907f6e5c65a4fd03d1bafcd81e895
export THINKBOX_OPENAI_COMPAT_BASE_URL=https://api.inception.ai/v1
export THINKBOX_DEFAULT_MODEL=mercury-2

# 4. Run
python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000

# 5. Test
curl http://localhost:8000/health
curl -X POST http://localhost:8000/run \
  -H "Content-Type: application/json" \
  -d '{"goal": "List files in data/ directory"}'
```

## Upstash Box Limitations

The Upstash Box sandbox has a **transparent TLS proxy** that blocks outbound HTTPS
to hosts not in its whitelist. HTTP works, HTTPS does not.

**Workaround for testing:**
- Run the backend locally (where HTTPS works)
- Use the box for code development, git operations, and testing non-HTTPS tools
- The box CAN reach: GitHub API, HTTP endpoints
- The box CANNOT reach: Inception API, most HTTPS APIs

**To enable HTTPS on a new box**, configure `attachHeaders`:
```python
box = Box.create(
    runtime="python",
    attach_headers={
        "api.inception.ai": {"Authorization": "Bearer <REDACTED>"},
    },
)
```
The host proxy will then allow TLS connections to `api.inception.ai`.

## Inception API (Mercury 2)

- Endpoint: `https://api.inception.ai/v1`
- Key: `sk_63c907f6e5c65a4fd03d1bafcd81e895`
- Model: `mercury-2`
- ~1,000,000 tokens available
- OpenAI-compatible format
- Supports tool/function calling

## Tools Available (17 total)

| Tool | Purpose |
|------|---------|
| fs_read / fs_write / fs_list | Filesystem access (jailed to repo + data/) |
| http_get | HTTP GET with rate limiting (400ms/host) |
| memory_put / memory_get / memory_search | SQLite research memory |
| doge_tx | Fetch Dogecoin transaction |
| doginals_inscription | Fetch inscription from indexer |
| compare_inscription | Compare across multiple indexers |
| parse_drc20 | Parse DRC-20 JSON operations |
| load_fixture | Load test data from fixtures/ |
| shell_exec | Execute shell commands |
| file_read / file_write | Legacy file tools |
| http_request / memory_query | Legacy HTTP and memory tools |
