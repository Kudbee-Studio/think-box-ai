# STATUS.md — Think Box AI

**Session:** agent_79e656bf-37c6-46f2-833e-1eb027b99152
**Branch:** session/agent_79e656bf-clean
**Box:** wanted-tuna-71803 (idle)

## Tools: 18 registered & verified

file_read, file_write, shell_exec, http_request, memory_query, fs_read, fs_write, fs_list, http_get, memory_put, memory_get, memory_search, indexer_health, doge_tx, doginals_inscription, compare_inscription, parse_drc20, load_fixture

## Job Queue

| ID | Hat | Verdict | Location |
|----|-----|---------|----------|
| job_dogi_split_001 | researcher | unproven | jobs/done/ |
| job_wallet_scan_001 | researcher | blocked | jobs/blocked/ |
| job_gpu_find_models | runner | blocked | jobs/blocked/ |
| job_gpu_serve_20b | runner | blocked | jobs/blocked/ |

### Wallet Verdicts (DDCkpBDN5hkbYJyUqeyVmCV9s8mEoxGFc8)
| Asset | Verdict |
|-------|---------|
| dogi 21m ticker | blocked |
| dbit | blocked |
| dcex | blocked |
| dogx | blocked |
| Doge Runestone | blocked |
| DogeBuds | blocked |
| Dogemaps | blocked |

Reason: api.doginals.org wallet endpoints not public.

## Source Reachability

| Source | HTTP | Notes |
|--------|------|-------|
| api.doginals.org | 200 | Health only; wallet/inscription endpoints 404 |
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
| SSH key | unknown until laptop |
| Models | 20B + 120B on attached disks |

## Tests

**Status:** Test file added (`tests/unit/test_jobs.py`). Cannot run — pytest not installed (no pip).
**Coverage:** schema loads, template validates, runner blocked when GPU stopped, all verdicts valid.

## Public Page

Path: `public/index.html`
How-to: `public/HOW_TO_QUEUE.md`

GitHub Pages guess: enable Pages on `session/agent_79e656bf-clean` branch, `/public` folder (or `/docs`).
URL would be: `https://kudbee-studio.github.io/think-box-ai/`
Cannot change repo settings from here — Kudbee must enable in Settings → Pages.
