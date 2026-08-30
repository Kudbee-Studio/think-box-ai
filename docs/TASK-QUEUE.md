# KUDBEE Action Items (Prioritized)

## Priority 1: CRITICAL - Infrastructure Access

### 1.1 Add SSH key to kud-bee os server
**Issue:** Cannot SSH to kud-bee os (87.58.149.167) - key not provisioned
**Action:** Use UpCloud web console emergency console → add SSH public key
**Public Key:** `ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAILZ6oDsNJowkIO3rrU7EbqvSvifZZTEKKfW44hotnZBc kilo-agent@kudbee`

### 1.2 Enable IPv6 on GPU server (if needed)
**Note:** IPv6 is per-interface toggle in UpCloud. Current config only has IPv4.
**Action:** Add IPv6 interface if UpCloud zone supports it.

## Priority 2: HIGH - Production Deployment

### 2.1 Deploy Next.js dashboard with SSE streaming
**Why:** Real-time agent activity monitoring
**Tech:** Next.js + Server-Sent Events (SSE) + ReadableStream pattern
**Files:** `apps/web/dashboard/` (new)
```typescript
// Route Handler streaming pattern from Next.js docs
export async function GET() {
  const stream = new ReadableStream({
    async start(controller) {
      // Stream agent activity
      controller.enqueue(encoder.encode(`data: ${JSON.stringify(agentStatus)}\n\n`));
    }
  });
  return new Response(stream, { headers: { 'Content-Type': 'text/event-stream' } });
}
```

### 2.2 Set up Redis as SIM index
**Why:** Zero-hallucination context delivery for agents
**Schema:**
```bash
HSET sim:agents:director state active gpu 0
HSET sim:tasks:queue task:123 '{"priority":1,"status":"pending"}'
SET sim:metrics:gpu0 '{"utilization":94,"memory_used":16549}'
```

### 2.3 Deploy embedding model on GPU 1
**Model:** BAAI/bge-small-en-1.5 (small, fast)
**Port:** 8001
**Purpose:** Semantic search across knowledge base

### 2.4 Deploy fast agent model on GPU 2
**Model:** Qwen2.5-3B-Instruct
**Port:** 8002
**Purpose:** Rapid micro-agent spawns

## Priority 3: MEDIUM - Tooling & Observability

### 3.1 Install Netdata for real-time monitoring
**Why:** See all 3 GPUs, CPU, RAM, network in real-time
```bash
bash <(curl -Ss https://my-netdata.io/kickstart.sh)
```

### 3.2 Create update skill (automated status reports)
**Script:** `kudbee_update.py` (already created)
**Schedule:** Cron every 5 minutes
**Output:** Human-readable report to console + JSON to Redis

### 3.3 Implement MCP tool registry
**Why:** Tools are interchangeable capabilities
**Schema:**
```json
{
  "tool_id": "image.generate",
  "provider": "SDXL",
  "gpu": 1,
  "input": {"prompt": "string", "width": 1024},
  "output": {"image": "base64"}
}
```

## Priority 4: LOW - Future Enhancements

### 4.1 Create Terraform module for infrastructure as code
### 4.2 Set up GitHub Actions CI/CD pipeline
### 4.3 Deploy Unity game (KUDBEE Runner)

---

**Next immediate action:** SSH to kud-bee os via web console and add our key.
