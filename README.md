# Think Box AI

## kudbEE Agent OS

The interactive Agent OS runs from `apps/web` and is available at
`http://localhost:3000/` during local development. It provides a WebSocket
agent session, live thoughts and tasks, plugin execution, middleware health
checks, RSS/Atom ingestion, model discovery through Ollama, and system-health
telemetry.

```bash
cd apps/web
npm install
node --experimental-strip-types server.ts
```

The smallest tested local model is `smollm2:135m`:

```bash
ollama serve
ollama pull smollm2:135m
```

See [docs/guides/agent_os.md](docs/guides/agent_os.md) for plugin testing,
session memories, uploads, middleware checks, and Docker deployment.
