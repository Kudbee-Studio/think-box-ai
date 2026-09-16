# Skill: burst-execute

**Description:** Execute THINK Burst protocol — bounded reasoning bursts on gpt-oss-20b

# When to Use

Use when running THINK burst evaluations — comparing reasoning vs disruptor outputs, capturing reasoning channels, and measuring model quality under bounded budgets.

# Prerequisites

- Valid governance token (burst refuses to start without one)
- `openai/gpt-oss-20b` model available at `http://127.0.0.1:8001` (loopback only)
- Auth: `Authorization: Bearer EMPTY`

# Workflow

## Step 1 — Offline Test

```bash
python3 examples/think_burst_demo.py
python3 -m unittest tests.unit.test_burst -v
```

## Step 2 — Live Burst

```bash
python3 -m thinkbox.burst --live --pairs N --minutes M --max-calls C --budget X
```

Parameters:
- `--pairs N` — number of reasoning/disruptor pairs
- `--minutes M` — time limit
- `--max-calls C` — hard stop on API calls
- `--budget X` — hard stop on spend

**The runner refuses to start without a governance token and hard-stops on any limit.**

## Step 3 — Review Output

Check:
- Grounded vs ungrounded ratio
- Reasoning channel capture (delta.reasoning / reasoning fields)
- Governance token ID recorded per call
- Evidence text in ActionLedger

## Step 4 — Safety

- **Never expose :8000/:8001 publicly**
- Use HTTP/1.0 if curl hangs: `curl -sS --http1.0 -m 20 ...`
- Founder starts and STOPS think-v2 (never terminates)
- Cloud Bot / CloudShell holds SSM access

# Environment Variables

| Variable | Purpose |
|----------|---------|
| `THINKBOX_DEFAULT_PROVIDER` | Provider (openai_compat) |
| `THINKBOX_DEFAULT_MODEL` | Model (gpt-oss-20b) |
| Governance token | Required to start burst |

# Rules

- Never bind :8000/:8001 to public interfaces
- Always use governance token — no anonymous bursts
- Hard stops are enforced — do not bypass
- Capture reasoning fields when present — never drop them
