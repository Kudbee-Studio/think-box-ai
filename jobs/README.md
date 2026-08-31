# Job Queue

Drop a Think Job JSON file into `jobs/queue/` to schedule work.

## Directory Structure

```
jobs/
  schema.json          # Think Job schema
  job_*.json           # Job definitions
  queue/               # Waiting to run
  active/              # Currently running (max 1)
  done/                # Completed
  blocked/             # Needs human or GPU
```

## How to Schedule

1. Create a JSON file with Think Job fields (id, intent, hat, inputs, plan, capabilities, execution, artifacts, evaluation)
2. Drop it in `jobs/queue/`
3. The agent picks it up, runs allowed tools, writes execution[] and artifacts[]
4. Move to `jobs/done/` (success) or `jobs/blocked/` (needs human)

## Job Lifecycle

```
queue → active → done
              → blocked (needs human/GPU)
```

## GPU Jobs

GPU jobs stay `blocked` until Kudbee:
1. Starts the GPU (UUID ...e57)
2. Provides SSH key path
3. Writes START

Then they move to `queue` → `active` → `done`.

## Verdicts

- `succeeded` — proof complete
- `failed` — proof failed
- `unproven` — APIs insufficient
- `blocked` — needs human/GPU
