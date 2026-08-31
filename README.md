# Think Box AI — Think Job Control Plane

**Think Box AI** turns human intent into verified outcomes by running narrow Think Jobs on replaceable machines, then keeping the proof.

---

## Quick Start

```bash
# Clone
git clone https://github.com/Kudbee-Studio/think-box-ai.git
cd think-box-ai
git checkout session/agent_79e656bf-clean

# CLI
python3 -m think_box_ai.cli --help
python3 -m think_box_ai.cli job list
python3 -m think_box_ai.cli doctor

# Run tests (no pytest needed)
python3 scripts/run_tests.py

# Validate jobs
python3 scripts/check_jobs.py

# Backend
python3 -m uvicorn backend.main:app --port 8000
```

## What It Does

1. **Think Jobs** — Units of work: intent → plan → execution → artifacts → verdict
2. **Researcher Hat** — HTTP, fixtures, findings (runs on any box)
3. **Local Indexing** — SQLite + FTS5 for sessions and project memory
4. **Public Packets** — Human-readable proof files for each job

## CLI Commands

```
thinkbox job list/show/submit/queue/diff/run/cancel/retry
thinkbox findings list/show/preview/export
thinkbox config show/set/profile
thinkbox memory search/show/list/remember/forget/context
thinkbox box status/health
thinkbox doctor / init / watch
```

## Job Schema

```json
{
  "id": "job_name_001",
  "intent": "What this job proves",
  "hat": "researcher",
  "inputs": {},
  "plan": ["step 1", "step 2"],
  "capabilities": {"tools": [...], "needs_gpu": false},
  "execution": [],
  "artifacts": [],
  "evaluation": {"verdict": "unproven"},
  "cost": {"box_minutes": 0, "gpu_minutes": 0, "http_calls": 0}
}
```

## Verdicts

| Verdict | Meaning |
|---------|---------|
| succeeded | Proof complete |
| failed | Proof failed |
| unproven | APIs insufficient |
| blocked | Needs human/GPU |

## Project Structure

```
think-box-ai/
  think_box_ai/          # CLI + commands + UI + utils
  core/                  # Runtime, tools, providers, indexing, governance
  backend/               # FastAPI server
  jobs/                  # Queue, templates, completed, blocked
  data/                  # Findings, fixtures, raw, thinkbox.db
  scripts/               # Test runner, worker, health check
  public/                # Public-facing job pages
  docs/                  # Architecture, API, indexing, handoff
```

## License

MIT
