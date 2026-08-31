# STATUS.md — Think Box AI Research Agent

**Session:** agent_79e656bf-37c6-46f2-833e-1eb027b99152
**Branch:** session/agent_79e656bf-clean
**Last Commit:** 6175f8b
**Box:** wanted-tuna-71803 (idle)

## Tools: 18 registered & verified this session

file_read, file_write, shell_exec, http_request, memory_query, fs_read, fs_write, fs_list, http_get, memory_put, memory_get, memory_search, indexer_health, doge_tx, doginals_inscription, compare_inscription, parse_drc20, load_fixture

## DOGI Proof

**Status:** Honest proof completed.
**Finding:** `data/findings/dogi_indexer_split.md`

### Source Results
| Source | HTTP | Notes |
|--------|------|-------|
| api.doginals.org | 200 | Health only; inscription endpoints 404 |
| dogechain.info | 403 | Cloudflare anti-bot |
| wonky-ord.dogeord.io | — | DNS dead |
| ordinalswallet.com | — | Timeout |
| api.inception.ai | ❌ | TLS SNI reject (banned) |

**Conclusion:** Indexer-split thesis unprovable via public APIs.

## Researcher Hat

Contract: `data/findings/RESEARCHER_HAT.md`

## UpCloud GPU

| Field | Value |
|-------|-------|
| UUID | 00d832ec-8565-447b-86ac-74bf9bd41e57 |
| Hostname | gpu-ubuntu-20cpu-256gb-fi-hel2 |
| Floating IP | 87.58.150.62 |
| State | stopped |
| SSH key | unknown until laptop |
| Models | 20B + 120B on attached disks |

## Provider Order

1. Ollama (local)
2. FreeToken on GPU (87.58.150.62:1919 when started)
3. OpenAI-compatible
