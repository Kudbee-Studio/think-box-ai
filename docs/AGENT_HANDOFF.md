# Agent Handoff — Think Box AI

**Session:** agent_79e656bf-37c6-46f2-833e-1eb027b99152
**Branch:** session/agent_79e656bf-clean
**Last Updated:** 2026-08-31

## Quick Start

```bash
# Branch
git checkout session/agent_79e656bf-clean

# Install
pip install -r backend/requirements.txt

# Run tests (no pytest needed)
python3 scripts/run_tests.py

# Validate jobs
python3 scripts/check_jobs.py

# CLI
python3 -m think_box_ai.cli --help
python3 -m think_box_ai.cli job list

# Backend
python3 -m uvicorn backend.main:app --port 8000
```

## Project Structure

```
think-box-ai/
  think_box_ai/          # Main package
    cli.py               # CLI entry point
    commands/            # CLI command modules
      job.py, findings.py, config.py, box.py, watch.py
    ui/                  # Terminal rendering
      colors.py, table.py, progress.py, prompt.py
    utils/               # Output formatting
      output.py, format.py
    token.py             # Think Token (legacy)
  core/                  # Core runtime
    foundation/          # Config, logging, bootstrap, errors
    runtime/             # Agent loop, planner, actor
    tools/               # Tool registry, fs, http, memory, doginals
    providers/           # Ollama, OpenAI-compatible
    memory/              # SQLite store, session/task adapters
    governance/          # Audit, approval, policy
  backend/               # FastAPI server
    main.py              # REST + WebSocket + SSE
  jobs/                  # Job queue
    schema.json          # Think Job schema
    templates/           # Reusable job templates
    queue/               # Waiting jobs
    active/              # Currently running
    done/                # Completed
    blocked/             # Needs human/GPU
  data/
    findings/            # Research artifacts
    fixtures/            # Test data
    raw/                 # Raw API responses
    infra_upcloud.ini    # Infrastructure state
  scripts/               # Utility scripts
    run_tests.py         # Test runner (no pytest)
    check_jobs.py        # Job validation
    gen_index.py         # INDEX.md generator
    run_job.py           # Queue worker
    validate_jobs.py     # Schema validation
  public/                # Public-facing pages
    index.html           # JOB #0001 + catalog
    HOW_TO_QUEUE.md      # How to submit jobs
    job-0001/            # Complete job packet
  docs/                  # Documentation
```

## Key Files

| File | Purpose |
|------|---------|
| AGENTS.md | Operating contract, hard bans, rules |
| STATUS.md | Current state, tools, jobs, blocked |
| SESSION.md | Session info, last commit, next owner |
| MISSION.md | What we are, what we're not |
| ROADMAP.md | Now/Next/Later phases |
| jobs/INDEX.md | Auto-generated job catalog |

## Workflow Rules

1. **Commit after each meaningful change** — one commit per feature/fix
2. **Push if no secrets** — `git log -p --all | grep -E 'gsk_|sk-'` must be empty
3. **Update STATUS.md** — what changed, what works, what's blocked
4. **Update SESSION.md** — last commit hash, phase name
5. **Rebuild INDEX.md** — after any job move: `python3 scripts/gen_index.py stopped`
6. **No force-push main** — only push current session branch
7. **No Groq, no Inception** — banned providers
8. **No GPU start/stop** — power is human-only

## Current Phase: Production Hardening

### Done
- CLI v2 with global flags, colors, JSON output
- Job queue with worker, templates, catalog
- Governance audit log
- Backend API v0.3 with job/findings endpoints
- Test runner (no pytest)
- Public packet for JOB #0001

### In Progress
- Shell completion generation
- Job dependencies (parent/child)
- Actual receipts/metrics
- Config profiles

### Blocked
- GPU stopped (Kudbee must start)
- SSH blocked (firewall drop-all, no key)
- No LLM on box (Ollama not installed)
- Wallet APIs not public

## Infrastructure

| Resource | Value |
|----------|-------|
| GPU UUID | 00d832ec-8565-447b-86ac-74bf9bd41e57 |
| GPU Hostname | gpu-ubuntu-20cpu-256gb-fi-hel2 |
| GPU Floating IP | 87.58.150.62 |
| GPU State | stopped |
| Upstash Box | wanted-tuna-71803 |
| SSH Key | .ssh/thinkbox-agent (ed25519) |

## Job Schema

Every job needs: `id, intent, hat, inputs, plan, capabilities, execution, artifacts, evaluation`.

Verdicts: `succeeded | failed | unproven | blocked`.

Hats: `researcher | runner | director | camera | jury`.

## Provider Order

1. Ollama (local)
2. FreeToken on GPU (87.58.150.62:1919)
3. OpenAI-compatible

## Next Owner Checklist

1. Read this file + AGENTS.md + STATUS.md
2. `git log --oneline -5` to see recent commits
3. `python3 scripts/check_jobs.py` to validate
4. Pick up from "In Progress" or "Blocked" sections
5. Commit each change, push if no secrets
