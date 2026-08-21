"""Migration 002: Memory events and prediction tracking.

Adds tables for the memory consolidation pipeline (Issue #8):
- memory_events      — raw captured events (actions, decisions, corrections, etc.)
- candidate_memories — extracted candidates pending validation
- prediction_memories — agent predictions with outcomes and trust scores

Uses PostgreSQL 19 temporal features (FOR PORTION OF) where applicable.

Run with: psql -U kudbee -d kudbee -f 002_memory_events.sql
"""

-- Memory events: raw captured events from agent execution
CREATE TABLE IF NOT EXISTS memory_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT now(),
    event_type TEXT NOT NULL CHECK (
        event_type IN ('action', 'decision', 'correction', 'failure', 'success', 'prediction')
    ),
    source TEXT NOT NULL DEFAULT 'agent' CHECK (source IN ('agent', 'user', 'system')),
    content TEXT NOT NULL,
    embedding vector(1536),  -- for semantic event search
    confidence REAL DEFAULT 1.0,
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_events_session ON memory_events(session_id);
CREATE INDEX IF NOT EXISTS idx_events_agent ON memory_events(agent_id);
CREATE INDEX IF NOT EXISTS idx_events_type ON memory_events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_timestamp ON memory_events(timestamp DESC);

-- IVFFlat index for semantic event search
CREATE INDEX IF NOT EXISTS idx_events_embedding
    ON memory_events USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 50);

-- Candidate memories: extracted from events, pending validation
CREATE TABLE IF NOT EXISTS candidate_memories (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    content TEXT NOT NULL,
    candidate_type TEXT NOT NULL CHECK (
        candidate_type IN ('fact', 'decision', 'preference', 'lesson', 'question', 'pattern')
    ),
    confidence REAL DEFAULT 0.0,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (
        status IN ('pending', 'approved', 'rejected', 'needs_review')
    ),
    source_events JSONB DEFAULT '[]'::jsonb,
    embedding vector(1536),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_candidates_session ON candidate_memories(session_id);
CREATE INDEX IF NOT EXISTS idx_candidates_status ON candidate_memories(status);
CREATE INDEX IF NOT EXISTS idx_candidates_type ON candidate_memories(candidate_type);

-- Prediction memories: agent predictions with outcomes and trust scores
CREATE TABLE IF NOT EXISTS prediction_memories (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    prediction TEXT NOT NULL,
    expected_outcome TEXT NOT NULL,
    confidence REAL DEFAULT 0.5,
    actual_outcome TEXT,
    was_correct BOOLEAN,
    feedback_source TEXT DEFAULT 'user',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    outcome_timestamp TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_predictions_agent ON prediction_memories(agent_id);
CREATE INDEX IF NOT EXISTS idx_predictions_session ON prediction_memories(session_id);
CREATE INDEX IF NOT EXISTS idx_predictions_correct ON prediction_memories(was_correct);

-- Update migration record
INSERT INTO schema_migrations (version, description)
VALUES (2, 'Memory events, candidate memories, and prediction tracking tables')
ON CONFLICT (version) DO NOTHING;
