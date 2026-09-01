# STATUS.md — Think Box AI

**Session:** agent_79e656bf-37c6-46f2-833e-1eb027b99152
**Branch:** session/agent_79e656bf-clean
**Domain:** thinkboxai.xyz
**Phase:** Enterprise Build (Phase 8)

## Tools: 18 registered & verified

file_read, file_write, shell_exec, http_request, memory_query, fs_read, fs_write, fs_list, http_get, memory_put, memory_get, memory_search, indexer_health, doge_tx, doginals_inscription, compare_inscription, parse_drc20, load_fixture

## Frontend Pages (12 total)

| Page | Path | Status |
|------|------|--------|
| Landing | / | ✅ |
| Collections | /collections/ | ✅ |
| Collection Detail | /collections/detail.html | ✅ |
| DRC-20 Tokens | /tokens/ | ✅ |
| Activity | /activity/ | ✅ |
| Tracker | /tracker/ | ✅ |
| Inscribe | /inscribe/ | ✅ |
| Wallet | /wallet/ | ✅ |
| Security | /security/ | ✅ |
| About | /about/ | ✅ |
| Blog | /blog/ | ✅ |
| Search | /search/ | ✅ |
| 404 | /404.html | ✅ |

## CLI Commands

```
thinkbox job list/show/submit/queue/diff/run/cancel/retry
thinkbox findings list/show/preview/export
thinkbox config show/set/profile
thinkbox memory search/show/list/remember/forget/context
thinkbox box status/health
thinkbox doctor / init / watch
Global: --json --plain --quiet --verbose --dry-run --no-color
```

## Job Queue (7 jobs)

| ID | Hat | Verdict |
|----|-----|---------|
| job_dogi_split_001 | researcher | unproven |
| job_compare_dogi_dbit | researcher | unproven |
| job_inscription_001 | researcher | unproven |
| job_wallet_scan_001 | researcher | blocked |
| job_gpu_find_models | runner | blocked |
| job_gpu_serve_20b | runner | blocked |
| job_director_wallet_report_001 | director | blocked |

## Test Results

**Runner:** scripts/run_tests.py (unittest, no pytest needed)
**Result:** 41+ tests, 2 errors (provider tests hit real API — expected)

## Backend API v0.3

```
GET  /health, /jobs, /jobs/{id}, /findings, /tools
POST /run
GET  /stream (SSE)
WS   /ws
```

## Local Indexing

SQLite + FTS5 at data/thinkbox.db.
CLI: thinkbox memory search/show/list/remember/forget/context

## SEO

- Meta tags, Open Graph, Twitter Cards on all pages
- Schema.org JSON-LD structured data
- Sitemap.xml + robots.txt
- Canonical URLs → thinkboxai.xyz
- Target keywords: Doginals marketplace, DRC-20, Dogecoin inscriptions

## Source Reachability

| Source | HTTP | Notes |
|--------|------|-------|
| api.doginals.org | 200 | Health only |
| api.github.com | 200 | OK |
| dogechain.info | 403 | Cloudflare |
| wonky-ord.dogeord.io | — | DNS dead |
| ordinalswallet.com | — | Timeout |
| api.inception.ai | ❌ | TLS reject (banned) |

## UpCloud GPU

| Field | Value |
|-------|-------|
| UUID | 00d832ec-8565-447b-86ac-74bf9bd41e57 |
| Hostname | gpu-ubuntu-20cpu-256gb-fi-hel2 |
| Floating IP | 87.58.150.62 |
| State | stopped |
| Models | 20B + 120B on attached disks |

## Blocked

- GPU stopped (Kudbee must start)
- SSH blocked (firewall drop-all)
- No LLM on box
- Wallet APIs not public
