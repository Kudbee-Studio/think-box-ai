# HANDOFF PROMPT — Think Box AI

Paste this entire block as the first message to a new agent:

---

You are working in the think-box-ai repo on a new session branch.

## Identity

- Repo: think-box-ai
- Main branch: `main` (protected, never commit here)
- Your branch: create `session/agent_<your-session-id>` or use the one assigned
- Domain: thinkboxai.xyz (purchased, DNS not yet configured)
- GPU: UUID `00d832ec-8565-447b-86ac-74bf9bd41e57` (STOPPED — power human-only)
- Upstash Box: `wanted-tuna-71803` (idle, Python runtime)

## Environment Variables Available

```
CURSOR_API_KEY=$CURSOR_API_KEY
INCEPTION_API_KEY=$INCEPTION_API_KEY
UPSTASH_BOX_API_KEY=$UPSTASH_BOX_API_KEY
THINKBOX_UPCLOUD_API_TOKEN=$THINKBOX_UPCLOUD_API_TOKEN
```

## First Things to Read (in order)

1. `MISSION.md` — what we are
2. `STATUS.md` — current state
3. `MEMORY.md` — durable facts
4. `SESSION.md` — last commit, next owner
5. `WORK_QUEUE.md` — what's pending
6. `BEST_PRACTICES.md` — how to operate
7. `AGENTS.md` — operating contract
8. `docs/AGENT_HANDOFF.md` — for the next agent

## Workflow Rules (NON-NEGOTIABLE)

### Branching
1. Always work on your session branch — never commit to main
2. Create a new clean branch if secrets leak (never rewrite public history without approval)
3. Push after every commit if `git log -p --all | grep -E 'sk_|gsk_|password'` is empty

### Committing
1. One commit per feature/fix — don't bundle unrelated changes
2. Format: `type(scope): description` (feat, fix, docs, refactor, chore)
3. No "fix stuff" or "wip" messages
4. Always describe WHAT and WHY

### Security
1. NEVER commit secrets — no API keys, SSH private keys, tokens
2. Scan before push: `git log -p --all | grep -E 'sk_|gsk_|password'`
3. Use environment variables — never hardcode credentials
4. If secret is committed: remove immediately, rotate key, notify Kudbee

### Documentation (update after EVERY change)
- `STATUS.md` — tools, jobs, verdicts, blocked items
- `MEMORY.md` — durable facts, infrastructure
- `SESSION.md` — last commit hash, phase, next owner
- `WORK_QUEUE.md` — check off completed, add new

### Handoff (before stopping)
1. All changes committed and pushed
2. All index files updated
3. No secrets in git history
4. Tests pass
5. Next owner knows exactly where to pick up

## Cursor Integration

The Cursor SDK (`@cursor/sdk`) is available for spawning agents programmatically.

```bash
export CURSOR_API_KEY="$CURSOR_API_KEY"
```

Use Cursor for:
- Cloud agents (parallel execution, survives disconnect)
- Local agents (fast, works on current tree)
- Sub-agent spawning from CLI

DO NOT call `api.inception.ai` from Cursor cloud agents — TLS fails from AWS.

## Inception API (Mercury 2)

- Endpoint: `https://api.inception.ai/v1`
- Key: `$INCEPTION_API_KEY` (local only — TLS fails from AWS/Upstash boxes)
- Model: `mercury-2`
- ~1M tokens available
- Use for local development and CLI inference

## Current Project State

### Frontend (14 pages)
Landing, Collections, Collection Detail, DRC-20 Tokens, Activity, Tracker, Inscribe, Wallet, Security, About, Blog, Blog Post, Search, Sitemap, 404

### Backend API v1.0
```
GET  /health, /metrics
GET  /api/v1/jobs, /api/v1/jobs/{id}
POST /api/v1/jobs, /api/v1/jobs/{id}/run
DELETE /api/v1/jobs/{id}
GET  /api/v1/findings, /api/v1/findings/{name}
GET  /api/v1/tools
WS   /ws
```

### CLI v4 Commands
```
thinkbox job list/show/create/submit/run/cancel/retry/diff
thinkbox memory remember/recall/search/context/list/forget
thinkbox cursor run/list/logs
thinkbox inception run/models/usage
thinkbox queue status/add/batch/drain
thinkbox spawn researcher/runner
thinkbox config show/set/profile
thinkbox findings list/show/preview
thinkbox doctor / init / watch / serve
```

### GPU Queue
Priority queue at `data/gpu_queue.jsonl`. Pre-built templates ready for GPU execution. When Kudbee starts GPU, queue drains automatically.

### Memory Systems
- `thinkbox_memory.db` — agents memory (SQLite + FTS5)
- `cli_memory.db` — persistent CLI memory
- `memory/` — Obsidian-compatible vault (drop files → indexed)
- Auto-recall injects relevant memories into context

## What to Work On Next

Check `WORK_QUEUE.md` for the full priority list. Top items:

1. **Populate agents memory** — Fill `thinkbox_memory.db` with project facts
2. **GPU job templates** — Build 50+ pre-defined jobs for GPU execution
3. **Inception API integration** — Wire Mercury 2 into CLI (`thinkbox inception run`)
4. **Cursor SDK agents** — Spawn cloud agents from CLI
5. **Skills marketplace** — Installable plugin packages
6. **Testing** — Expand coverage to 80%+
7. **Documentation** — API reference, setup guides

## Blocked (cannot fix)

- GPU stopped (Kudbee must start from UpCloud panel)
- SSH blocked (firewall drop-all + need firewall rule from Kudbee IP)
- No LLM on box (Ollama not installed)
- Wallet APIs not public
- Vector search needs pip (no pip on box)

## Source Blocklist

| Source | Reason |
|--------|--------|
| api.inception.ai | CDN SNI reject from AWS IPs |
| wonky-ord.dogeord.io | DNS dead |
| ordinalswallet.com | Timeout |
| dogechain.info | Cloudflare 403 |

## UpCloud Facts

| Field | Value |
|-------|-------|
| UUID | `00d832ec-8565-447b-86ac-74bf9bd41e57` |
| Hostname | `gpu-ubuntu-20cpu-256gb-fi-hel2` |
| Floating IP | `87.58.150.62` |
| Plan | GPU-SPOT-20xCPU-256GB-3xL40S |
| State | **STOPPED** (power human-only) |
| SSH Key | `.ssh/thinkbox-agent` (ed25519) |
| Models | 20B + 120B on attached disks |
| Firewall | Drop all inbound (console works) |

## Verification Commands

```bash
# Check GPU state
curl -s "https://api.upcloud.com/1.3/server" -H "Authorization: Bearer $THINKBOX_UPCLOUD_API_TOKEN"

# Test box connectivity
curl -s "https://us-east-1.box.upstash.com/v2/box/wanted-tuna-71803" -H "X-Box-Api-Key: $UPSTASH_BOX_API_KEY"

# Scan for secrets before push
git log -p --all | grep -E 'sk_|gsk_|password' && echo "FOUND" || echo "CLEAN"

# Run tests
python3 scripts/run_tests.py

# Validate jobs
python3 scripts/check_jobs.py
```

## Your Goal

Build production-quality features. Follow the workflow exactly. Leave the next agent better informed than you found them. Document everything. No shortcuts.

If you deviate from these rules, you will be corrected. Follow them.

