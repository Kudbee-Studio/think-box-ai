# MEMORY.md — Think Box AI Project Notes

**Session:** agent_79e656bf-37c6-46f2-833e-1eb027b99152
**Branch:** session/agent_79e656bf-37c6-46f2-833e-1eb027b99152
**Created:** 2026-08-31

## Project Overview

Think Box AI is a research agent for proving/disproving indexer consensus
on inscription chains (Doginals, DRC-20, BRC-20, Runes).

## DOGI Fixtures

Test inscription IDs (from user-provided canonical data):
- `15f3b73df7e5c072becb1d84191843ba080734805addfccb650929719080f62ei0`
- `0bd32d69ca2221f3fc34d99aa14bccc2af10eedc7514770ae842ab9a72468743`
- `ee688262677b00d973d0aa18e40863e8ba984e4237ac6ef46dd53a5b0d380092`

These are used to verify the DOGI indexer-split thesis (21M vs 2.1B supply).

## Source Allowlist (reachable from box)

| Source | Use For |
|--------|---------|
| api.doginals.org | Health check, indexer status |
| api.github.com | Git operations, code |

## Source Blocklist

| Source | Reason |
|--------|--------|
| api.inception.ai | CDN SNI reject from AWS IPs |
| wonky-ord.dogeord.io | DNS dead |
| ordinalswallet.com | Connection timeout |
| dogechain.info | Cloudflare 403 anti-bot |

## Provider Order

1. **Ollama** (preferred) — local models, install with `ollama pull llama3.1:8b`
2. **FreeToken** — GPU server at `http://87.58.150.62:1919/v1` when started by Kudbee
3. **OpenAI-compatible** — any standard provider with valid key

## UpCloud Notes

- UUID: `00d832ec-8565-447b-86ac-74bf9bd41e57` (ends in e57, not e51)
- Power state: HUMAN ONLY
- Floating IP: 87.58.150.62
- Plan: GPU-SPOT-20xCPU-256GB-3xL40S
- Do NOT start/stop without Kudbee authorization

## GPU Server Plan (when started by Kudbee)

1. SSH BatchMode to 87.58.150.62
2. Find models: `lsblk`, `df -h`, `find /mnt /data /models /home -iname '*gguf' -o -iname 'config.json'`
3. Pick server:
   - GGUF → llama.cpp or ollama
   - MoE HF → `ft serve --host 0.0.0.0 --port 1919 --model <path>`
4. Health check: `curl 127.0.0.1:1919/v1/models` or `/api/tags`
5. Wire think-box: `openai_compat` → `http://87.58.150.62:1919/v1`
6. Use tmux/systemd so SSH drop doesn't kill server
7. 20B model for DOGI proof, 120B for later work

## Provider Order

1. **Ollama** (preferred on box) — local, install with `ollama pull llama3.1:8b`
2. **FreeToken** on GPU — `http://87.58.150.62:1919/v1` when started
3. **OpenAI-compatible** — any standard provider

## Architecture

- Agent loop: `core/runtime/loop.py`
- Tools: `core/tools/*.py` (18 total)
- Providers: `core/providers/*.py`
- Backend: `backend/main.py` (FastAPI)
- Memory: `core/tools/memory.py` (SQLite)

## Next Owner Instructions

1. Check STATUS.md for current state
2. Check data/findings/ for proof results
3. Use Ollama provider on box or FreeToken on GPU
4. Do NOT start/stop UpCloud servers
5. Commit locally, push may be rejected (write PUSH.md)
