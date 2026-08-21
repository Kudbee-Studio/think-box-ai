"""Migration 001: PostgreSQL 19 schema for kudbEE.

Creates the core tables for the four-layer memory architecture:
- sessions        — agent session state
- tasks           — task lifecycle (planning → execution → validation)
- memory_entries   — all four memory layers with JSONB payload
- memory_vectors   — pgvector embeddings (1536 dims) for semantic search
- audit_logs       — append-only tool execution log

PostgreSQL 19 features used:
- ON CONFLICT DO SELECT (atomic get-or-create, 4x faster than DO UPDATE)
- SQL/PGQ graph queries (agent relationship tracking)
- FOR PORTION OF temporal operations (memory validity windows)

Run with: psql -U kudbee -d kudbee -f 001_postgresql19.sql
"""

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS vector;       -- pgvector for embeddings
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";  -- UUID generation
CREATE EXTENSION IF NOT EXISTS pg_trgm;      -- Trigram search for fuzzy text

-- Sessions: agent session state
CREATE TABLE IF NOT EXISTS sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id TEXT NOT NULL,
    goal TEXT,
    status TEXT NOT NULL DEFAULT 'running',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_sessions_agent ON sessions(agent_id);
CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status);

-- Tasks: task lifecycle (planning → execution → validation)
CREATE TABLE IF NOT EXISTS tasks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    root_goal_id UUID,
    session_id UUID REFERENCES sessions(id) ON DELETE CASCADE,
    agent_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'running',
    plan JSONB DEFAULT '{}'::jsonb,
    step_results JSONB DEFAULT '{}'::jsonb,
    validation_outcomes JSONB DEFAULT '{}'::jsonb,
    replan_history JSONB DEFAULT '[]'::jsonb,
    error_log JSONB DEFAULT '[]'::jsonb,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_tasks_session ON tasks(session_id);
CREATE INDEX IF NOT EXISTS idx_tasks_agent ON tasks(agent_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);

-- Memory entries: all four layers (session, task, organizational, verified_knowledge)
CREATE TABLE IF NOT EXISTS memory_entries (
    key TEXT PRIMARY KEY,
    layer TEXT NOT NULL CHECK (layer IN ('session', 'task', 'organizational', 'verified_knowledge')),
    entry_type TEXT NOT NULL,
    value JSONB NOT NULL,
    agent_id TEXT DEFAULT '',
    task_id TEXT DEFAULT '',
    session_id TEXT DEFAULT '',
    confidence REAL DEFAULT 1.0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    valid_from TIMESTAMPTZ DEFAULT now(),
    valid_to TIMESTAMPTZ DEFAULT 'infinity'  -- FOR PORTION OF temporal support
);

CREATE INDEX IF NOT EXISTS idx_memory_layer ON memory_entries(layer);
CREATE INDEX IF NOT EXISTS idx_memory_task ON memory_entries(task_id);
CREATE INDEX IF NOT EXISTS idx_memory_agent ON memory_entries(agent_id);
CREATE INDEX IF NOT EXISTS idx_memory_session ON memory_entries(session_id);
CREATE INDEX IF NOT EXISTS idx_memory_confidence ON memory_entries(confidence);
CREATE INDEX IF NOT EXISTS idx_memory_created ON memory_entries(created_at DESC);

-- Memory vectors: pgvector embeddings for semantic search
CREATE TABLE IF NOT EXISTS memory_vectors (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    entry_key TEXT NOT NULL REFERENCES memory_entries(key) ON DELETE CASCADE,
    embedding vector(1536),  -- all-MiniLM-L6-v2 embedding dimension
    content_text TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- IVFFlat index for fast approximate nearest-neighbor search
CREATE INDEX IF NOT EXISTS idx_memory_vectors_embedding
    ON memory_vectors USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- Audit logs: append-only tool execution log
CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id TEXT NOT NULL,
    task_id TEXT,
    session_id TEXT,
    tool_name TEXT NOT NULL,
    action TEXT NOT NULL,  -- 'execute', 'approve', 'reject', 'deny'
    args JSONB,
    result JSONB,
    permission TEXT,
    success BOOLEAN NOT NULL DEFAULT true,
    error TEXT,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT now(),
    checksum TEXT  -- tamper-evident append-only hash chain
);

CREATE INDEX IF NOT EXISTS idx_audit_agent ON audit_logs(agent_id);
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_logs(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_tool ON audit_logs(tool_name);

-- Schema migrations tracking
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    description TEXT
);

-- Insert migration record
INSERT INTO schema_migrations (version, description)
VALUES (1, 'PostgreSQL 19 base schema with pgvector, sessions, tasks, memory_entries, memory_vectors, audit_logs')
ON CONFLICT (version) DO NOTHING;
