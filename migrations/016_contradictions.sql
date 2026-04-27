-- v10.0.0 — Contradiction-detection audit log.
--
-- Beever Atlas runs contradiction detection as a post-pipeline service:
-- for every new fact it pulls existing facts with overlapping entity tags,
-- asks an LLM whether they contradict, and either auto-supersedes (≥0.8) or
-- flags `potential_contradiction` (0.5-0.8). We mirror that idea but keep
-- the supersession on the existing `knowledge.superseded_by` chain so the
-- rest of the recall stack (timeline, version history) keeps working.
--
-- This table holds the audit trail — every comparison the detector ran,
-- whether it acted on it or not. Lets us tune the threshold against real
-- LLM verdicts later, and gives the dashboard a "potential contradictions
-- waiting for review" panel for the medium-confidence band.

CREATE TABLE IF NOT EXISTS contradiction_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at      TEXT NOT NULL,
    new_knowledge_id   INTEGER NOT NULL,                     -- the just-saved record
    candidate_knowledge_id INTEGER NOT NULL,                  -- the pre-existing one we compared against
    cosine_similarity  REAL NOT NULL,                         -- pre-LLM filter score
    llm_confidence  REAL,                                     -- 0.0–1.0 from the comparator
    decision        TEXT NOT NULL CHECK (decision IN
                        ('superseded', 'flagged', 'rejected', 'skip', 'error')),
    reason          TEXT,
    provider        TEXT,
    model           TEXT,
    latency_ms      INTEGER
);

CREATE INDEX IF NOT EXISTS idx_contradiction_log_new       ON contradiction_log(new_knowledge_id);
CREATE INDEX IF NOT EXISTS idx_contradiction_log_candidate ON contradiction_log(candidate_knowledge_id);
CREATE INDEX IF NOT EXISTS idx_contradiction_log_decision  ON contradiction_log(decision);
CREATE INDEX IF NOT EXISTS idx_contradiction_log_created   ON contradiction_log(created_at);
