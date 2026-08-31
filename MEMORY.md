# MEMORY.md — Think Box AI Project Notes

**Session:** agent_79e656bf-37c6-46f2-833e-1eb027b99152
**Branch:** session/agent_79e656bf-clean

## Project Overview

Think Box AI is a control plane for Think Jobs. Researcher Hat first.
18 tools, SQLite memory, agent loop with XML tool calls.

## DOGI Fixtures

- `15f3b73df7e5c072becb1d84191843ba080734805addfccb650929719080f62ei0`
- `0bd32d69ca2221f3fc34d99aa14bccc2af10eedc7514770ae842ab9a72468743`
- `ee688262677b00d973d0aa18e40863e8ba984e4237ac6ef46dd53a5b0d380092`

## UpCloud GPU

- UUID: `00d832ec-8565-447b-86ac-74bf9bd41e57`
- Hostname: `gpu-ubuntu-20cpu-256gb-fi-hel2`
- Floating IP: `87.58.150.62`
- Plan: GPU-SPOT-20xCPU-256GB-3xL40S
- State: stopped (Kudbee shut down)
- SSH key: unknown until laptop
- Models: 20B + 120B on attached data disks

## Source Blocklist

| Source | Reason |
|--------|--------|
| api.inception.ai | CDN SNI reject |
| wonky-ord.dogeord.io | DNS dead |
| ordinalswallet.com | Timeout |
| dogechain.info | Cloudflare 403 |

## Provider Order

1. Ollama (local)
2. FreeToken on GPU (87.58.150.62:1919)
3. OpenAI-compatible

## Push Status

Clean branch pushed: `session/agent_79e656bf-clean`. No secrets.
