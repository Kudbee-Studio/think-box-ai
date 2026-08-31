# STATUS.md — Think Box AI Research Agent

**Session:** agent_79e656bf-37c6-46f2-833e-1eb027b99152
**Branch:** session/agent_79e656bf-clean
**Last Commit:** dacca97
**GPU State:** stopped (Kudbee shut down on purpose)

## What Works

### Tools (18 registered)
| # | Tool | Status |
|---|------|--------|
| 1-5 | file_read/write, shell_exec, http_request, memory_query | ✅ |
| 6-8 | fs_read/write/list | ✅ |
| 9 | http_get | ✅ |
| 10-12 | memory_put/get/search | ✅ |
| 13 | indexer_health | ✅ |
| 14-17 | doge_tx, doginals_inscription, compare_inscription, parse_drc20 | ✅ |
| 18 | load_fixture | ✅ |

### Backend
- /health returns OK
- /run, /stream, /ws endpoints implemented

## DOGI Proof Result

**Status:** Partial — tools work, inscription data inaccessible via public APIs.
Finding: `data/findings/dogi_indexer_split.md`

## UpCloud GPU

| Field | Value |
|-------|-------|
| UUID | 00d832ec-8565-447b-86ac-74bf9bd41e57 |
| Hostname | gpu-ubuntu-20cpu-256gb-fi-hel2 |
| Floating IP | 87.58.150.62 |
| State | stopped |
| Models | 20B + 120B on attached disks |

**Next:** Kudbee will start from panel, SSH with real key, find model paths, serve 20B.

## Provider Order

1. Ollama (local)
2. FreeToken on GPU (87.58.150.62:1919 when started)
3. OpenAI-compatible
