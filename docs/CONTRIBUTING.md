# Contributing to Think Box AI

## Workflow

1. **One commit per feature/fix** — don't bundle unrelated changes
2. **Commit message format:** `feat:`, `fix:`, `docs:`, `chore:`, `refactor:`
3. **Push after each commit** — if no secrets in history
4. **Update STATUS.md** — what changed, what works, what's blocked
5. **Update SESSION.md** — last commit hash, phase name
6. **Rebuild INDEX.md** — after any job move: `python3 scripts/gen_index.py stopped`

## Rules

- No Groq, no Inception (banned providers)
- No `gsk_`, `sk-`, or API keys in commits
- No force-push to main
- No starting/stopping UpCloud GPU (human-only)
- No SSH key generation (Kudbee provides)

## Testing

```bash
# Run all tests (no pytest needed)
python3 scripts/run_tests.py

# Validate job files
python3 scripts/check_jobs.py

# Health check
python3 scripts/health_check.py
```

## CLI

```bash
# Test locally
python3 -m think_box_ai.cli job list
python3 -m think_box_ai.cli findings list
python3 -m think_box_ai.cli config show
```

## Job Submission

```bash
# Interactive wizard
python3 -m think_box_ai.cli job submit

# From template
python3 -m think_box_ai.cli job submit wallet_scan

# Run worker
python3 scripts/run_job.py
```

## Code Style

- Follow existing patterns
- No comments unless asked
- Type hints for public functions
- Docstrings for modules
