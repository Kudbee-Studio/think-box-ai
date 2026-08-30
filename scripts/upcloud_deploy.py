"""Docker Compose stack for KUDBEE on UpCloud.

Deploy this on the main UpCloud instance (kudbee-host-v1) to run:
- API Gateway (FastAPI)
- PostgreSQL (persistent state)
- Redis (session/cache)
- Nginx reverse proxy with TLS
- Agent orchestrator
"""

# docker-compose.yml content for UpCloud deployment
DOCKER_COMPOSE = """
version: "3.9"

services:
  # ── Reverse Proxy & TLS ──────────────────────────────────────
  gateway:
    image: caddy:2-alpine
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile
      - caddy_data:/data
      - caddy_config:/config
    networks:
      - frontend
    depends_on:
      - api

  # ── API Gateway ──────────────────────────────────────────────
  api:
    build:
      context: .
      dockerfile: Dockerfile.api
    restart: unless-stopped
    environment:
      - DATABASE_URL=postgresql://kudbee:${DB_PASSWORD}@postgres:5432/kudbee
      - REDIS_URL=redis://redis:6379/0
      - MODEL_ROUTER_OLLAMA_URL=http://ollama:11434
      - THINKBOX_UPCLOUD_API_TOKEN=${UPCLOUD_API_TOKEN}
      - KUDBEE_AGENT_DIR=/var/lib/kudbee/agents
      - KUDBEE_ENCRYPTION_KEY=${ENCRYPTION_KEY}
    volumes:
      - agent_data:/var/lib/kudbee/agents
    networks:
      - frontend
      - backend
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy

  # ── Agent Orchestrator ───────────────────────────────────────
  orchestrator:
    build:
      context: .
      dockerfile: Dockerfile.orchestrator
    restart: unless-stopped
    environment:
      - DATABASE_URL=postgresql://kudbee:${DB_PASSWORD}@postgres:5432/kudbee
      - REDIS_URL=redis://redis:6379/0
      - WORKER_CONCURRENCY=4
      - SANDBOX_MODE=local  # or firecracker for microVM
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - agent_data:/var/lib/kudbee/agents
    networks:
      - backend
    depends_on:
      - api
      - redis

  # ── PostgreSQL ───────────────────────────────────────────────
  postgres:
    image: postgres:16-alpine
    restart: unless-stopped
    environment:
      - POSTGRES_USER=kudbee
      - POSTGRES_PASSWORD=${DB_PASSWORD}
      - POSTGRES_DB=kudbee
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init.sql:/docker-entrypoint-initdb.d/init.sql
    networks:
      - backend
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U kudbee"]
      interval: 5s
      timeout: 5s
      retries: 5

  # ── Redis ────────────────────────────────────────────────────
  redis:
    image: redis:7-alpine
    restart: unless-stopped
    command: redis-server --appendonly yes --requirepass ${REDIS_PASSWORD}
    volumes:
      - redis_data:/data
    networks:
      - backend
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "${REDIS_PASSWORD}", "ping"]
      interval: 5s
      timeout: 5s
      retries: 5

  # ── Ollama (CPU fallback or GPU with runtime: nvidia) ────────
  ollama:
    image: ollama/ollama:latest
    restart: unless-stopped
    volumes:
      - ollama_models:/root/.ollama
    networks:
      - backend
    # Uncomment for GPU server:
    # deploy:
    #   resources:
    #     reservations:
    #       devices:
    #         - driver: nvidia
    #           count: all
    #           capabilities: [gpu]

networks:
  frontend:
    driver: bridge
  backend:
    driver: bridge
    internal: true

volumes:
  caddy_data:
  caddy_config:
  postgres_data:
  redis_data:
  agent_data:
  ollama_models:
"""

CADDYFILE = """
# Caddy reverse proxy for KUDBEE
{
    email {$TLS_EMAIL:-admin@kudbee.studio}
}

{$DOMAIN:-localhost} {
    reverse_proxy api:8000 {
        header_up X-Real-IP {remote}
        header_up X-Forwarded-For {remote}
        header_up X-Forwarded-Proto {scheme}
    }

    # WebSocket support
    @websocket {
        header Connection *Upgrade*
        header Upgrade websocket
    }
    reverse_proxy @websocket api:8000

    # Security headers
    header {
        X-Content-Type-Options nosniff
        X-Frame-Options DENY
        X-XSS-Protection "1; mode=block"
        Strict-Transport-Security "max-age=31536000; includeSubDomains"
        Referrer-Policy "strict-origin-when-cross-origin"
    }

    # Rate limiting (built into Caddy 2.7+)
    rate_limit {
        zone static_example {
            key static
            events 100
            window 1m
        }
    }

    log {
        output file /data/access.log {
            roll_size 10mb
            roll_keep 5
        }
    }
}
"""

COMPOSE_ENV = """
# .env for KUDBEE UpCloud deployment
DB_PASSWORD=change-me-in-production
REDIS_PASSWORD=change-me-too
ENCRYPTION_KEY=generate-with-openssl-rand-hex-32
UPCLOUD_API_TOKEN=ucat_01M15R0CYV33FZ1G410MX8FPTA
DOMAIN=kudbee.studio
TLS_EMAIL=admin@kudbee.studio
"""

INIT_SQL = """
-- KUDBEE PostgreSQL schema
CREATE SCHEMA IF NOT EXISTS kudbee;

CREATE TABLE IF NOT EXISTS kudbee.tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    tier VARCHAR(20) NOT NULL DEFAULT 'free',
    api_key_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS kudbee.agents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES kudbee.tenants(id),
    name VARCHAR(255) NOT NULL,
    model_config JSONB NOT NULL DEFAULT '{}',
    status VARCHAR(20) NOT NULL DEFAULT 'created',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_active TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS kudbee.think_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES kudbee.tenants(id),
    agent_id UUID REFERENCES kudbee.agents(id),
    claim TEXT NOT NULL,
    score FLOAT DEFAULT 1.0,
    grounded BOOLEAN DEFAULT true,
    author VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS kudbee.challenges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    token_id UUID REFERENCES kudbee.think_tokens(id),
    challenge_type VARCHAR(20) NOT NULL,
    outcome FLOAT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS kudbee.audit_log (
    id BIGSERIAL PRIMARY KEY,
    tenant_id UUID,
    agent_id UUID,
    action VARCHAR(100) NOT NULL,
    outcome VARCHAR(20),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_tokens_tenant ON kudbee.think_tokens(tenant_id);
CREATE INDEX idx_agents_tenant ON kudbee.agents(tenant_id);
CREATE INDEX idx_audit_tenant_time ON kudbee.audit_log(tenant_id, created_at);
"""


def write_deployment_files(base_path: str = ".") -> None:
    """Write all deployment files to disk."""
    import os

    files = {
        "docker-compose.yml": DOCKER_COMPOSE,
        "Caddyfile": CADDYFILE,
        ".env.example": COMPOSE_ENV,
        "init.sql": INIT_SQL,
    }

    for filename, content in files.items():
        filepath = os.path.join(base_path, filename)
        with open(filepath, "w") as f:
            f.write(content.strip() + "\n")
        print(f"Written: {filepath}")


if __name__ == "__main__":
    write_deployment_files()
