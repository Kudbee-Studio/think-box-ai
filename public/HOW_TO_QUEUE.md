# How to Queue a Think Job

Drop a JSON file in `jobs/queue/` to schedule work.

## Format

A Think Job needs these fields:

```json
{
  "id": "job_your_name_001",
  "intent": "What you want to prove or disprove",
  "hat": "researcher",
  "inputs": { "inscription_id": "..." },
  "plan": ["step one", "step two"],
  "capabilities": { "tools": ["http_get"], "needs_gpu": false },
  "execution": [],
  "artifacts": [],
  "evaluation": { "verdict": "unproven", "reason": "", "confidence": 0.0 }
}
```

## Hat choices

| Hat | When | Needs GPU |
|-----|------|-----------|
| researcher | HTTP, fixtures, findings | no |
| runner | serve models on GPU | yes (blocked until START) |

## Lifecycle

1. Drop JSON in `jobs/queue/`
2. Worker picks it up, moves to `jobs/active/`
3. Runs allowed tools
4. Moves to `jobs/done/` or `jobs/blocked/`
5. `jobs/INDEX.md` rebuilds automatically

## What runs now

- **Researcher jobs** — run immediately on the box (HTTP to live hosts only)
- **Runner jobs** — stay blocked until Kudbee starts GPU + provides SSH key

## Sources allowed

- api.doginals.org (health only)
- api.github.com

## Sources blocked

- dogechain.info (Cloudflare 403)
- wonky-ord.dogeord.io (DNS dead)
- api.inception.ai (TLS fail — never use)
- ordinalswallet.com (timeout)

## Verdicts

| Verdict | Meaning |
|---------|---------|
| succeeded | proof complete |
| failed | proof failed |
| unproven | APIs insufficient |
| blocked | needs human or GPU |

Do not upgrade `blocked` or `unproven` to `succeeded`.
