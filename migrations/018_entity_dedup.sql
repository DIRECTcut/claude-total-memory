-- v10.0.0 — Pre-write entity dedup audit log.
--
-- Beever Atlas's CrossBatchValidator pre-computes Jina embeddings for
-- extracted entity names and runs cosine similarity against the known
-- entity vectors before the LLM validator runs. Matched candidates are
-- offered to the LLM as merge hints so "Atlas" → "Beever Atlas" without
-- a second name appearing in Neo4j.
--
-- We do the same for incoming `tags` on save_knowledge: any tag that is
-- not already a canonical topic is checked against existing graph_nodes
-- via embedding cosine. When a match crosses MEMORY_ENTITY_DEDUP_THRESHOLD
-- (default 0.85), the tag is rewritten to the canonical entity name and
-- the action is logged here.
--
-- The log lets the dashboard surface "this save merged 'StockFlow' →
-- 'vitamin_all' — was that correct?" to the user, and gives us data to
-- tune the threshold against false positives.

CREATE TABLE IF NOT EXISTS entity_dedup_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at      TEXT NOT NULL,
    knowledge_id    INTEGER,                    -- nullable: pre-insert decisions log here too
    project         TEXT,
    input_tag       TEXT NOT NULL,              -- the free-form tag the user submitted
    matched_node_id TEXT,                       -- graph_nodes.id of the canonical entity
    canonical_name  TEXT,                       -- the canonical name we rewrote to
    similarity      REAL NOT NULL,              -- cosine similarity of the match
    threshold       REAL NOT NULL,
    decision        TEXT NOT NULL CHECK (decision IN ('merged', 'considered', 'no_match', 'error')),
    reason          TEXT
);

CREATE INDEX IF NOT EXISTS idx_entity_dedup_log_decision ON entity_dedup_log(decision);
CREATE INDEX IF NOT EXISTS idx_entity_dedup_log_created  ON entity_dedup_log(created_at);
CREATE INDEX IF NOT EXISTS idx_entity_dedup_log_knowledge ON entity_dedup_log(knowledge_id);
