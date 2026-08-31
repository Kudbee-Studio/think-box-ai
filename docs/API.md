# API Reference — Think Box AI

## REST Endpoints

### GET /health

Returns service health.

```json
{
  "status": "ok",
  "service": "think-box-ai",
  "version": "0.3.0",
  "provider": "OllamaProvider",
  "tools": 18,
  "sessions": 0
}
```

### GET /jobs

Lists all jobs.

```json
{
  "jobs": [
    {"id": "job_dogi_split_001", "hat": "researcher", "state": "done", "verdict": "unproven"}
  ]
}
```

### GET /jobs/{id}

Returns job details.

```json
{
  "id": "job_dogi_split_001",
  "intent": "...",
  "hat": "researcher",
  "inputs": {...},
  "plan": [...],
  "execution": [...],
  "artifacts": [...],
  "evaluation": {"verdict": "unproven"},
  "cost": {"box_minutes": 0, "gpu_minutes": 0, "http_calls": 0}
}
```

### GET /findings

Lists all findings.

```json
{
  "findings": ["dogi_indexer_split.md", "wallet_DDCkpBDN.md"]
}
```

### GET /tools

Lists all registered tools.

### POST /run

Executes a goal.

```json
{
  "goal": "List files in data/",
  "max_iterations": 20
}
```

### GET /stream

SSE streaming for a goal.

### WS /ws

WebSocket for interactive sessions.

## CLI Commands

See `thinkbox --help` for full command reference.

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
  "evaluation": {"verdict": "unproven", "reason": "", "confidence": 0.0},
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

## Hats

| Hat | Role |
|-----|------|
| researcher | HTTP, fixtures, findings |
| runner | Serve models on GPU |
| director | Orchestrate child jobs |
| camera | Media packs |
| jury | Evaluate verdicts |
