-- v10.0.0 — Quality gate audit log + importance levels
--
-- Two changes in one migration because they are introduced together by the
-- Phase A wave:
--
-- 1. `knowledge.importance` — critical|high|medium|low (default medium).
--    Used by fusion.py to boost the final RRF score so a P0 deployment
--    decision does not get drowned by trivia at recall time.
--
-- 2. `quality_gate_log` — every save that the quality gate rejects (and
--    optionally accepts, when MEMORY_QUALITY_LOG_ALL=1) is journaled here.
--    The audit trail lets us tune the prompt and threshold against real
--    rejection data instead of guessing.

ALTER TABLE knowledge ADD COLUMN importance TEXT NOT NULL DEFAULT 'medium';

-- Defensive index — recall_modes filters by importance for boost lookup.
CREATE INDEX IF NOT EXISTS idx_knowledge_importance ON knowledge(importance);

CREATE TABLE IF NOT EXISTS quality_gate_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at      TEXT NOT NULL,
    decision        TEXT NOT NULL CHECK (decision IN ('pass', 'drop', 'skip', 'error')),
    score_total     REAL,
    score_specificity REAL,
    score_actionability REAL,
    score_verifiability REAL,
    threshold       REAL NOT NULL,
    project         TEXT,
    type            TEXT,
    content_chars   INTEGER NOT NULL,
    content_preview TEXT NOT NULL,
    reason          TEXT,
    knowledge_id    INTEGER,                                  -- set on 'pass'
    provider        TEXT,
    model           TEXT,
    latency_ms      INTEGER
);

CREATE INDEX IF NOT EXISTS idx_quality_gate_log_decision ON quality_gate_log(decision);
CREATE INDEX IF NOT EXISTS idx_quality_gate_log_created  ON quality_gate_log(created_at);
