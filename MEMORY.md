# MEMORY.md — Think Box AI Project Notes

**Session:** agent_79e656bf-37c6-46f2-833e-1eb027b99152
**Branch:** session/agent_79e656bf-clean
**Domain:** thinkboxai.xyz
**Last Updated:** 2026-09-01

## Project Overview

Think Box AI is a control plane for Think Jobs — units of work that turn intent into verified outcomes. We also run a Doginals marketplace (thinkboxai.xyz) for trading DRC-20 tokens, Dogecoin inscriptions, and NFT collections.

## Key Repos (KudbeeZero)

| Repo | Purpose |
|------|---------|
| kudbee-doginals | Doginals protocol — minter, wallet, viewer server |
| kudbee-doginal-collections | Collection standards (inscriptions.json + meta.json) |
| fork--dogecoin-ordinals-drc-20 | DRC-20 wallet with bulk minting |
| kudbee-freetoken | Local MoE model serving |
| kudbee-kirocrew | Persistent workspace |

## DOGI Fixtures

- `15f3b73df7e5c072becb1d84191843ba080734805addfccb650929719080f62ei0`
- `0bd32d69ca2221ffc34d99aa14bccc2af10eedc7514770ae842ab9a72468743`
- `ee688262677b00d973d0aa18e40863e8ba984e4237ac6ef46dd53a5b0d380092`

## UpCloud GPU

- UUID: `00d832ec-8565-447b-86ac-74bf9bd41e57`
- Hostname: `gpu-ubuntu-20cpu-256gb-fi-hel2`
- Floating IP: `87.58.150.62`
- Plan: GPU-SPOT-20xCPU-256GB-3xL40S
- State: stopped (Kudbee shut down)
- SSH key: .ssh/thinkbox-agent (ed25519)
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

## Frontend Pages

Landing, Collections, Collection Detail, DRC-20 Tokens, Activity, Tracker, Inscribe, Wallet, Security, About, Blog, Search, 404

## Key Features

- **Provenance Wallet** — Full history per inscription, chain of custody
- **Risk Scoring** — A+ / B / C / F confidence ratings
- **Inscription Service** — Mint UI with 2% fee, bulk support
- **Security Education** — Wallet drain attack demo
- **Sales Tracker** — Real-time event monitoring with webhook alerts
- **SEO** — thinkboxai.xyz domain, full meta tags + schema

## Push Status

Clean branch pushed: `session/agent_79e656bf-clean`. No secrets.
PR #58 merged to main.

## Cost Constraints

- Budget: ~$340 remaining
- Do NOT create UpCloud CPU boxes ($430/mo unnecessary)
- GPU spot may be revoked — this is normal

## Next Owner Instructions

1. Read docs/AGENT_HANDOFF.md
2. Check STATUS.md for current state
3. Use Groq provider on box (not Inception)
4. Do NOT start/stop UpCloud servers
5. Commit each change, push if no secrets
6. Update STATUS/SESSION after each commit
