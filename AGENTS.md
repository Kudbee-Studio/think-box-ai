# AGENTS.md — operating contract

Read MISSION.md and ROADMAP.md before doing work.

## Identity

- Repo: think-box-ai
- Branch: `session/agent_79e656bf-clean` unless Kudbee names another
- Upstash box: reuse `wanted-tuna-71803`. Do not create a second box.
- GPU: UUID `00d832ec-8565-447b-86ac-74bf9bd41e57`
- Hostname: `gpu-ubuntu-20cpu-256gb-fi-hel2`
- Floating IP (SSH / serve): `87.58.150.62`
- Plan: GPU-SPOT-20xCPU-256GB-3xL40S, fi-hel2
- Default GPU state: **stopped**. Power is human-only.

## Hard bans

- Do not create, delete, or resize servers.
- Do not start or stop the GPU unless Kudbee writes START or STOP.
- Do not invent SSH keys (`kilo-upcloud` is not valid).
- Do not commit `.env`, `gsk_`, or API tokens.
- Do not call `api.inception.ai` from AWS/Upstash.
- Do not use Groq.
- Do not detach the floating IP or data disks.
- Do not fill the 50GB boot disk with models.
- Do not force-push `main`.

## Think Job rules

One Job, one hat, one verdict. Use `unproven` or `blocked` when APIs or the GPU are down. Do not upgrade that to `succeeded`.

Required Job fields: id, intent, hat, inputs, plan, capabilities, execution, artifacts, evaluation.

## Hats this week

- `researcher` — HTTP, fixtures, findings. Allowed on Upstash/laptop with no GPU.
- `runner` — serve 20B on UpCloud. Only after START + key + paths written.
- No director / camera / jury until researcher has two completed Jobs.

## Providers

| Provider | Role | Agent may |
|---|---|---|
| Upstash | control plane, tools | resume existing box, HTTP to live hosts |
| Laptop | SSH + git | when Kudbee is at a PC |
| UpCloud | weights + serve | GET status always; start/stop only if told |

Live HTTP: `api.doginals.org`, GitHub.
Dead/blocked: wonky-ord DNS, dogechain CF 403 from box, Inception TLS 112.

## Memory files to keep true

- `STATUS.md` — tools, last test, verdicts
- `MEMORY.md` — durable project facts
- `SESSION.md` — session id, commit, next owner
- `data/infra_upcloud.ini` — uuid, IPs, state, model paths, key path
- `data/findings/` — L4 artifacts
- `PUSH.md` — only if push fails
- `data/thinkbox.db` — local indexing database (SQLite + FTS5)

## Indexing rules

- Project memory is scoped by `project_hash` (SHA-256 of repo path)
- Sessions auto-sync to FTS5 via triggers
- Memory `source` field: auto | explicit | correction
- Corrections take precedence over auto memory
- Use `thinkbox memory search` for recall
- Use `thinkbox memory context` for startup injection

## Done means

Print: branch, commit, box/GPU state, Jobs written, blocked list. Then halt. No code dump unless asked.
