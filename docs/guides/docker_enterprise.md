# Docker — enterprise operator guide

Hermetic containers for the Think Box AI API and optional control-plane static assets.
**Four-state:** images built in CI or locally prove **CODE COMPLETE / TEST VERIFIED** only — not LIVE VERIFIED.

## Images

| File | Purpose |
|------|---------|
| [Dockerfile](../../Dockerfile) | Production-style API (`uvicorn backend.main:app` on `:8000`) |
| [Dockerfile.hermetic](../../Dockerfile.hermetic) | Slim image running `scripts/verify_kilo_spine.py` (fast spine, no `--e2e`) |

## Quick start

```bash
export THINKBOX_API_KEY="$(python3 -c "import secrets; print('tb_' + secrets.token_urlsafe(24))")"
docker compose up api -d --build
curl -sS http://127.0.0.1:8000/health
```

### Full stack (API + static control plane on :8080)

```bash
docker compose --profile full up -d --build
open http://127.0.0.1:8080/control-plane/think_job_status.html
```

### Hermetic spine inside a container

```bash
docker compose --profile hermetic run --rm spine-verify
```

## Contract verification (no daemon required)

```bash
python3 scripts/verify_docker_contract.py
```

## Local LLM profile (optional)

```bash
docker compose --profile local-llm up -d ollama
```

## Security notes

- Never bake API keys into images; use `THINKBOX_API_KEY` at runtime.
- Do not expose `:8000` or model ports (`:8001`) on public interfaces without a reverse proxy and auth.
- See [deployment.md](deployment.md) for TLS and nginx production patterns.
