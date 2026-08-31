# STATUS.md — Think Box AI

**Session:** agent_79e656bf-37c6-46f2-833e-1eb027b99152
**Branch:** session/agent_79e656bf-clean
**Box:** wanted-tuna-71803 (idle)
**Phase:** Production Hardening

## Tools: 18 registered & verified

file_read, file_write, shell_exec, http_request, memory_query, fs_read, fs_write, fs_list, http_get, memory_put, memory_get, memory_search, indexer_health, doge_tx, doginals_inscription, compare_inscription, parse_drc20, load_fixture

## CLI Commands

```
thinkbox job list/show/submit/queue/diff/run
thinkbox findings list/show/preview
thinkbox config show/set/profile
thinkbox box status/health
thinkbox serve / watch
Global: --json --plain --quiet --verbose --dry-run --no-color
```

## Job Queue (7 jobs)

| ID | Hat | Verdict | Location |
|----|-----|---------|----------|
| job_dogi_split_001 | researcher | unproven | jobs/done/ |
| job_compare_dogi_dbit | researcher | unproven | jobs/done/ |
| job_inscription_001 | researcher | unproven | jobs/done/ |
| job_wallet_scan_001 | researcher | blocked | jobs/blocked/ |
| job_gpu_find_models | runner | blocked | jobs/blocked/ |
| job_gpu_serve_20b | runner | blocked | jobs/blocked/ |
| job_director_wallet_report_001 | director | blocked | jobs/blocked/ |

## Test Results

**Runner:** `scripts/run_tests.py` (unittest, no pytest needed)
**Result:** 41 tests, 2 errors (provider tests hit real API — expected)
**Job Validation:** `scripts/check_jobs.py` — all pass

## Local Indexing

SQLite + FTS5 at `data/thinkbox.db`.

```
thinkbox memory search/show/list/remember/forget/context
```

- Project-scoped isolation via SHA-256 hash
- Auto-sync via FTS5 triggers
- BM25 ranking
- Sessions + messages + project memory

## Backend API v0.3

```
GET  /health          — status, provider, tools
GET  /jobs            — list all jobs
GET  /jobs/{id}       — job details
GET  /findings        — list findings
GET  /tools           — list tools
POST /run             — run a goal
GET  /stream          — SSE streaming
WS   /ws              — WebSocket
```

## Governance

Audit log, permission checker, approval gate.
Policy: AUTO_APPROVE_READ (default), MANUAL, AUTO_APPROVE_ALL.

## Source Reachability

| Source | HTTP | Notes |
|--------|------|-------|
| api.doginals.org | 200 | Health only; wallet/inscription 404 |
| api.github.com | 200 | OK |
| dogechain.info | 403 | Cloudflare anti-bot |
| wonky-ord.dogeord.io | — | DNS dead |
| ordinalswallet.com | — | Timeout |
| api.inception.ai | ❌ | TLS SNI reject (banned) |

## UpCloud GPU

| Field | Value |
|-------|-------|
| UUID | 00d832ec-8565-447b-86ac-74bf9bd41e57 |
| Hostname | gpu-ubuntu-20cpu-256gb-fi-hel2 |
| Floating IP | 87.58.150.62 |
| State | stopped |
| SSH Key | .ssh/thinkbox-agent (ed25519) |
| Models | 20B + 120B on attached disks |

## Firewall

Default: drop-all inbound/outbound. Console works. SSH :22 blocked.

## Public Packet

`public/index.html` — JOB #0001 + catalog + verdict legend
`public/job-0001/` — complete job packet
`public/job-0002/` — compare job packet
`public/job-0003/` — inscription job packet
`public/job-0004/` — wallet job packet
`public/verdicts.md` — verdict registry
`public/HOW_TO_QUEUE.md` — how to submit jobs
`public/findings.md` — findings browser

## Shell Completion

`scripts/completions/thinkbox.bash` — source in .bashrc
`scripts/completions/thinkbox.zsh` — source in .zshrc

## Config Profiles

`.env.ollama` — local Ollama
`.env.freetoken` — FreeToken on GPU

## Provider Order

1. Ollama (local)
2. FreeToken on GPU (87.58.150.62:1919 when started)
3. OpenAI-compatible

## Blocked

- GPU stopped (Kudbee must start from panel)
- SSH blocked (firewall drop-all + need firewall rule from Kudbee IP)
- No LLM on box (Ollama not installed)
- Wallet APIs not public
