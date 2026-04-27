-- v10.1 — Async enrichment queue (inbox/outbox style).
--
-- When MEMORY_ASYNC_ENRICHMENT=true, save_knowledge returns immediately
-- after the cheap pipeline steps (privacy filter / canonical tags /
-- INSERT / embed / graph auto-link). The expensive LLM-bound steps
-- (quality gate, entity dedup audit, contradiction detector, episodic
-- linking, wiki refresh) are deferred to a background worker that
-- consumes this queue.
--
-- Failure semantics: rows can be re-claimed if the worker crashes
-- mid-task (status flips back via stale_after timer). Each row carries
-- an immutable snapshot of payload data so the worker does not have to
-- re-read knowledge content (which a concurrent supersede could change).

CREATE TABLE IF NOT EXISTS enrichment_queue (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    knowledge_id    INTEGER NOT NULL,                  -- target row
    session_id      TEXT,
    project         TEXT NOT NULL DEFAULT 'general',
    ktype           TEXT NOT NULL,                     -- mirror of knowledge.type
    content_snapshot TEXT NOT NULL,                    -- post-sanitize content
    tags_snapshot   TEXT NOT NULL DEFAULT '[]',        -- canonicalised tag list (JSON)
    importance      TEXT NOT NULL DEFAULT 'medium',
    skip_quality    INTEGER NOT NULL DEFAULT 0,        -- propagate caller intent
    status          TEXT NOT NULL DEFAULT 'pending'
                       CHECK (status IN ('pending', 'processing', 'done', 'failed')),
    attempts        INTEGER NOT NULL DEFAULT 0,
    last_error      TEXT,
    enqueued_at     TEXT NOT NULL,
    started_at      TEXT,
    finished_at     TEXT
);

CREATE INDEX IF NOT EXISTS idx_eq_status     ON enrichment_queue(status);
CREATE INDEX IF NOT EXISTS idx_eq_knowledge  ON enrichment_queue(knowledge_id);
CREATE INDEX IF NOT EXISTS idx_eq_enqueued   ON enrichment_queue(enqueued_at);

-- Knowledge.status gets a new soft-drop marker so the async quality
-- gate can flag low-quality records after the fact without losing them.
-- The check constraint on knowledge.status uses default-allowed values
-- (no enum), so we only need an index for fast filtering on recall.
CREATE INDEX IF NOT EXISTS idx_knowledge_status_quality
    ON knowledge(status) WHERE status = 'quality_dropped';
