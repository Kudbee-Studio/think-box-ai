# kudbEE Agent OS

## Local Runtime

The interactive web runtime lives in `apps/web` and serves the Agent OS at
`http://localhost:3000/`.

```bash
cd apps/web
npm install
node --experimental-strip-types server.ts
```

Ollama is discovered through `OLLAMA_BASE_URL`, which defaults to
`http://127.0.0.1:11434` for local development. The smallest tested model is:

```bash
ollama serve
ollama pull smollm2:135m
```

## Docker

Build and start the private Ollama plus Agent OS stack:

```bash
docker compose --profile agent-os up -d --build
docker compose --profile agent-os exec ollama ollama pull smollm2:135m
```

The Agent OS is published on port `3000`. Ollama is private to the Compose
network. Runtime data is persisted in the `agent_os_data` volume.

## Image Understanding and Generation

The terminal's image controls and `image_analyze` / `image_generate` plugins
use the CPU-only Janus-Pro-1B sidecar. It is an opt-in service separate from
SmolLM and downloads its model weights on first inference. Start it alongside
the Agent OS with:

```bash
docker compose --profile agent-os --profile images up -d --build
```

For an existing local Agent OS process, start only the image service and keep
`JANUS_BASE_URL` at its default `http://127.0.0.1:8001`:

```bash
docker compose --profile images up -d --build janus
```

Image analysis accepts PNG, JPEG, WebP, and GIF files up to 12 MB. Generated
images and analyzed uploads are saved in the session workspace. Janus-Pro runs
in float32 on CPU; allow several gigabytes of free RAM and expect image
generation to take substantially longer than text inference. Do not start the
image profile when the machine is low on memory. The worker uses Janus code
from the upstream repository and downloads model weights from Hugging Face;
review the upstream code and model licenses before deployment.

## Dashboard Features

The dashboard includes:

- WebSocket session status and session ID
- Model discovery and refresh
- Tasks, thoughts, and plugin activity
- Plugin `Test` controls
- `/help`, `/plugins`, `/models`, `/status`, `/clear`, and `/plugin NAME JSON`
  terminal commands
- RSS/Atom feed parsing through the `rss_feed` network plugin
- Connections monitor and `Test middleware` control
- Lower-right system health: runtime, WebSocket, session, models, plugins,
  uptime, and memory
- Session-scoped file and repository upload controls where enabled
- CPU Janus-Pro image analysis and generation controls when the `images`
  Compose profile is running

## Plugin Testing

The plugin test buttons send `plugin_execute` over the active WebSocket. Example
RSS input:

```json
{"url":"https://hnrss.org/frontpage","limit":5}
```

Plugin results are rendered in the terminal and emitted as `plugin_call` and
`plugin_result` thoughts. Successful and failed executions are recorded in the
active session memory with the plugin name, input, result, and timestamp.

## Tasks, Images, and Git

Tasks are session-scoped and shared between terminal commands and the dashboard.
The workflow adds ten operator improvements: create/list/show/search, lifecycle
status, priority, assignee, due dates with overdue tracking, tags, blocked
reasons, notes, a per-task activity timeline, and task image attachments. Use
terminal keywords such as:

```text
/task add "Review launch readiness" priority=high assignee=maya due=2026-10-01 tags=release,ops
/task list status=open priority=high q=launch
/task show TASK_ID
/task start TASK_ID
/task done TASK_ID
/task block TASK_ID Waiting for security review
/task priority TASK_ID critical
/task assign TASK_ID maya
/task due TASK_ID 2026-10-01
/task tag TASK_ID release,ops
/task note TASK_ID Confirmed with security
```

Use the dashboard filters and task-card actions to search, start, complete, or
block the same tasks. Attach raster images from a task card; they are stored in
the session workspace and shown in the task activity.

Connect public repositories from the Files panel or terminal:

```text
/git clone https://github.com/org/repo.git
/git status repositories/repo
/git log repositories/repo
/git diff repositories/repo
/git branch repositories/repo
```

Git clone is limited to credential-free public HTTPS URLs on GitHub, GitLab,
Bitbucket, and Codeberg. Status, log, diff summary, and branch are read-only and
restricted to repositories inside the active session workspace. Private-repo
credentials, push, commit, and arbitrary Git arguments are not accepted.

## Middleware Testing

`Test middleware` calls:

- `GET /api/health`
- `GET /api/sdk/capabilities`
- Ollama `GET /api/tags`

The result is displayed in the terminal, emitted as a middleware thought, and
stored in the active session memory when a session ID is present.

## Health Endpoints

```text
GET /api/health
GET /api/monitor
GET /api/middleware/test
GET /api/models
```

`/api/health` reports readiness, session count, plugin count, uptime, RSS
memory, Node version, and dry-run state. `/api/monitor` reports component
latency and the connection-monitor agent identity.

## Safety Boundaries

The web runtime is not production-safe by itself. Before public exposure, add
authentication, WebSocket authorization, approval gates for `shell_exec` and
`file_write`, network egress allowlists, upload scanning, rate limiting, and a
TLS reverse proxy. Keep Ollama private.
