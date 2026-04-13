-- ══════════════════════════════════════════════════════════
-- Claude Super Memory v5.0 — Database Migration
-- Run: sqlite3 ~/.claude-memory/memory.db < migrations/001_v5_schema.sql
-- ══════════════════════════════════════════════════════════

-- ══════════════════════════════════════════
-- KNOWLEDGE GRAPH
-- ══════════════════════════════════════════

CREATE TABLE IF NOT EXISTS graph_nodes (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,                 -- rule|convention|prohibition|skill|procedure|episode|fact|solution|decision|lesson|concept|pattern|technology|repo|article|doc|person|project|company|blindspot|competency|preference
    name TEXT NOT NULL,
    content TEXT,
    properties JSON,
    source TEXT,                        -- claude_md|skill|memory|auto|user
    importance REAL DEFAULT 0.5,
    first_seen_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    last_seen_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    mention_count INTEGER DEFAULT 1,
    status TEXT DEFAULT 'active'
);

CREATE INDEX IF NOT EXISTS idx_graph_nodes_type ON graph_nodes(type);
CREATE INDEX IF NOT EXISTS idx_graph_nodes_name ON graph_nodes(name);
CREATE INDEX IF NOT EXISTS idx_graph_nodes_status ON graph_nodes(status);
CREATE INDEX IF NOT EXISTS idx_graph_nodes_importance ON graph_nodes(importance);

CREATE TABLE IF NOT EXISTS graph_edges (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES graph_nodes(id) ON DELETE CASCADE,
    target_id TEXT NOT NULL REFERENCES graph_nodes(id) ON DELETE CASCADE,
    relation_type TEXT NOT NULL,        -- is_a|part_of|has_part|works_at|works_on|owns|uses|depends_on|alternative_to|integrates_with|replaced_by|provides|requires|composable_with|solves|causes|contradicts|supersedes|generalizes|example_of|governs|enforced_by|applies_to|led_to|preceded_by|struggles_with|prefers|mentioned_with
    weight REAL DEFAULT 1.0,
    context TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    last_reinforced_at TEXT,
    reinforcement_count INTEGER DEFAULT 0,
    UNIQUE(source_id, target_id, relation_type)
);

CREATE INDEX IF NOT EXISTS idx_graph_edges_source ON graph_edges(source_id);
CREATE INDEX IF NOT EXISTS idx_graph_edges_target ON graph_edges(target_id);
CREATE INDEX IF NOT EXISTS idx_graph_edges_type ON graph_edges(relation_type);
CREATE INDEX IF NOT EXISTS idx_graph_edges_weight ON graph_edges(weight);

-- Link existing knowledge records to graph nodes
CREATE TABLE IF NOT EXISTS knowledge_nodes (
    knowledge_id INTEGER REFERENCES knowledge(id) ON DELETE CASCADE,
    node_id TEXT REFERENCES graph_nodes(id) ON DELETE CASCADE,
    role TEXT DEFAULT 'related',        -- provides|requires|mentions|governs|related
    strength REAL DEFAULT 1.0,
    PRIMARY KEY (knowledge_id, node_id)
);

CREATE INDEX IF NOT EXISTS idx_knowledge_nodes_kid ON knowledge_nodes(knowledge_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_nodes_nid ON knowledge_nodes(node_id);

-- ══════════════════════════════════════════
-- EPISODE STORE
-- ══════════════════════════════════════════

CREATE TABLE IF NOT EXISTS episodes (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    project TEXT,
    timestamp TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),

    -- Narrative
    narrative TEXT NOT NULL,
    approaches_tried JSON,
    key_insight TEXT,

    -- Outcome
    outcome TEXT NOT NULL CHECK (outcome IN ('breakthrough', 'failure', 'routine', 'discovery')),
    impact_score REAL DEFAULT 0.5 CHECK (impact_score >= 0.0 AND impact_score <= 1.0),
    frustration_signals INTEGER DEFAULT 0,
    user_corrections JSON,

    -- Context
    concepts JSON,
    entities JSON,
    tools_used JSON,
    duration_minutes INTEGER,

    -- Relations
    similar_to JSON,
    led_to TEXT,
    contradicts TEXT,

    -- Metadata
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    embedding_id TEXT
);

CREATE INDEX IF NOT EXISTS idx_episodes_project ON episodes(project);
CREATE INDEX IF NOT EXISTS idx_episodes_outcome ON episodes(outcome);
CREATE INDEX IF NOT EXISTS idx_episodes_impact ON episodes(impact_score);
CREATE INDEX IF NOT EXISTS idx_episodes_session ON episodes(session_id);
CREATE INDEX IF NOT EXISTS idx_episodes_timestamp ON episodes(timestamp);

-- ══════════════════════════════════════════
-- SKILL STORE
-- ══════════════════════════════════════════

CREATE TABLE IF NOT EXISTS skills (
    id TEXT PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    trigger_pattern TEXT NOT NULL,

    -- Procedure
    steps JSON NOT NULL,
    anti_patterns JSON,

    -- Metrics
    times_used INTEGER DEFAULT 0,
    success_rate REAL DEFAULT 0.0,
    avg_steps_to_solve REAL,

    -- Evolution
    version INTEGER DEFAULT 1,
    learned_from JSON,
    last_refined_at TEXT,

    -- Context
    projects JSON,
    stack JSON,
    related_skills JSON,

    -- Status
    status TEXT DEFAULT 'draft' CHECK (status IN ('draft', 'active', 'mastered', 'deprecated')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_skills_status ON skills(status);
CREATE INDEX IF NOT EXISTS idx_skills_name ON skills(name);

CREATE TABLE IF NOT EXISTS skill_uses (
    id TEXT PRIMARY KEY,
    skill_id TEXT NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    episode_id TEXT REFERENCES episodes(id),
    success BOOLEAN NOT NULL,
    steps_used INTEGER,
    notes TEXT,
    used_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_skill_uses_skill ON skill_uses(skill_id);
CREATE INDEX IF NOT EXISTS idx_skill_uses_date ON skill_uses(used_at);

-- ══════════════════════════════════════════
-- SELF MODEL
-- ══════════════════════════════════════════

CREATE TABLE IF NOT EXISTS competencies (
    domain TEXT PRIMARY KEY,
    level REAL DEFAULT 0.5 CHECK (level >= 0.0 AND level <= 1.0),
    confidence REAL DEFAULT 0.3 CHECK (confidence >= 0.0 AND confidence <= 1.0),
    based_on INTEGER DEFAULT 0,
    trend TEXT DEFAULT 'unknown' CHECK (trend IN ('improving', 'stable', 'declining', 'stable_low', 'unknown')),
    last_updated TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS blind_spots (
    id TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    domains JSON,
    evidence JSON,
    severity REAL DEFAULT 0.5 CHECK (severity >= 0.0 AND severity <= 1.0),
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'resolved', 'monitoring')),
    discovered_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    resolved_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_blind_spots_status ON blind_spots(status);

CREATE TABLE IF NOT EXISTS user_model (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    confidence REAL DEFAULT 0.5,
    evidence_count INTEGER DEFAULT 1,
    last_updated TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- ══════════════════════════════════════════
-- INGESTION QUEUE
-- ══════════════════════════════════════════

CREATE TABLE IF NOT EXISTS ingest_queue (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,               -- telegram|file_watch|webhook|url|claude_mcp
    content_type TEXT NOT NULL,         -- text|image|pdf|url|code|audio
    raw_content BLOB,
    text_content TEXT,
    metadata JSON,
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'stored', 'error')),
    error_message TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    processed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_ingest_status ON ingest_queue(status);
CREATE INDEX IF NOT EXISTS idx_ingest_created ON ingest_queue(created_at);

-- ══════════════════════════════════════════
-- REFLECTION
-- ══════════════════════════════════════════

CREATE TABLE IF NOT EXISTS reflection_reports (
    id TEXT PRIMARY KEY,
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL,
    type TEXT NOT NULL CHECK (type IN ('session', 'periodic', 'weekly', 'manual')),

    -- Stats
    new_nodes INTEGER DEFAULT 0,
    patterns_found INTEGER DEFAULT 0,
    skills_refined INTEGER DEFAULT 0,
    rules_proposed INTEGER DEFAULT 0,
    contradictions INTEGER DEFAULT 0,
    archived INTEGER DEFAULT 0,

    -- Content
    focus_areas JSON,
    key_findings JSON,
    proposed_changes JSON,

    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_reflection_type ON reflection_reports(type);
CREATE INDEX IF NOT EXISTS idx_reflection_period ON reflection_reports(period_end);

CREATE TABLE IF NOT EXISTS pending_proposals (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL CHECK (type IN ('rule', 'skill', 'claude_md_update', 'blind_spot')),
    content TEXT NOT NULL,
    evidence JSON,
    confidence REAL,
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    reviewed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_proposals_status ON pending_proposals(status);
CREATE INDEX IF NOT EXISTS idx_proposals_type ON pending_proposals(type);

-- ══════════════════════════════════════════
-- MIGRATION METADATA
-- ══════════════════════════════════════════

CREATE TABLE IF NOT EXISTS migrations (
    version TEXT PRIMARY KEY,
    description TEXT,
    applied_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

INSERT OR IGNORE INTO migrations (version, description)
VALUES ('001', 'Super Memory v5.0 — Knowledge Graph, Episodes, Skills, Self Model, Reflection');
