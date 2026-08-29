# KUDBEE — Implementation Roadmap

**Project:** Think Box AI — Local-first agent execution environment with token tracking
**Architecture:** Python backend (asyncio + SQLite) + CLI + provider abstraction
**Status:** Phase 1 — CLI, tokens, and provider router complete

---

## Current State (Phase 1 Complete)

### Core Modules
- [x] `core/foundation/` — config, logging, errors, bootstrap
- [x] `core/memory/` — SQLite store, session/task/org adapters, schemas
- [x] `core/governance/` — audit log, permissions, approval gate
- [x] `core/providers/` — ModelProvider protocol, OpenAI-compatible provider, router
- [x] `core/tools/` — registry, decorator, 5 built-in tools
- [x] `core/runtime/` — Agent, ThinkBox, Planner, Actor, Observer
- [x] `tests/unit/` — 69 tests passing
- [x] `tests/integration/` — CLI, tokens, router tests passing

### CLI Commands
- [x] `thinkbox create` — Generate Think Box ID
- [x] `thinkbox exec` — Execute command via LocalExecProvider
- [x] `thinkbox evidence` — Show execution evidence
- [x] `thinkbox tokens` — List tokens for a box
- [x] `thinkbox token-score` — Print Elo score + last challenge
- [x] `thinkbox challenge-jury` — LLM jury challenge
- [x] `thinkbox challenge-human` — Manual scoring
- [x] `thinkbox list` — List all boxes
- [x] `thinkbox status` — Box status
- [x] `thinkbox clear-cache` — Clear provider cache

### Token System
- [x] Mint on exec success (ok=true)
- [x] Elo scoring with typed challenges
- [x] Exec challenge (weight 3)
- [x] Jury challenge (weight 2)
- [x] Human challenge (weight 2)
- [ ] Replay challenge (weight 1) — future

### Provider Router
- [x] Multi-provider routing with priority ordering
- [x] Automatic failover on error
- [x] Snapshot hashing for dedup
- [x] In-memory + persistent SQLite cache with TTL

---

## Open PRs

| PR | Branch | Description |
|----|--------|-------------|
| #38 | docs/thinkbox-infrastructure-access | Firecracker boot + block proof |
| #41 | feat/thinkbox-cli | CLI commands |
| #42 | feat/think-tokens | Tokens + exec challenge |
| #43 | feat/think-tokens-jury | Jury challenge |
| #44 | feat/provider-router | Provider router + improvements |

---

## Next Cues (after merge)

| ID | Cue | Repo | Status |
|----|-----|------|--------|
| F | Lease transplant off dashboard-update | inception_lightning-v1 | OPEN |
| G | Fuel-gage Think Box page | fuel-gage | LATER |
| H | Extract testLM router | think-box-ai | LATER |
| I-J | GPU gpt-oss / Lemonade-CUDA | new server | Human starts VM |
| K-O | Index, Redis, BYOK, absorber, music | various | LATER |

---

## Architecture Decisions

### Token Scoring
- Elo with typed weights: exec=3, jury=2, human=2, replay=1
- Floor 0, cap 100, η=0.25
- Only mint on verified execution (evidence ok=true)

### Provider Independence
- ModelProvider protocol in `core/providers/base.py`
- Provider selected by configuration, not code
- Router enables multi-provider failover without runtime changes

### Evidence-First Design
- Every execution leaves an evidence row (append-only JSONL)
- Tokens minted only when evidence confirms success
- Challenges scored against evidence, not claims

---

## File Locations

| Component | Path |
|-----------|------|
| Evidence | `~/.local/share/thinkbox/evidence/<box_id>.jsonl` |
| Database | `~/.local/share/thinkbox/thinkbox.db` |
| Snapshot cache | `~/.local/share/thinkbox/snapshot_cache.db` |
| Config | Environment variables or `pyproject.toml` |
