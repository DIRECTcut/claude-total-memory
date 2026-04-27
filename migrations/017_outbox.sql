-- v10.0.0 — Outbox / WriteIntent journal for save_knowledge.
--
-- Beever Atlas wraps its persister in a "WriteIntent in MongoDB" pattern: a
-- durability journal that ensures facts/entities are never partially
-- written, with a `WriteReconciler` background task that retries
-- incomplete intents at startup.
--
-- We mirror the idea but stay within SQLite. Every save_knowledge call
-- creates a row here BEFORE doing real work; the row is marked
-- `committed` at the end. If the process dies in between, the
-- reconciler in Store.__init__ replays the payload through
-- save_knowledge(_from_outbox=True) on the next startup.
--
-- The `payload_json` column stores the full original argument set
-- (content, ktype, project, tags, context, branch, importance, coref).
-- Together with the existing dedup path, replays are idempotent: a
-- successful re-run finds the previously inserted row by content+type+
-- project hash and updates `last_confirmed` instead of double-inserting.

CREATE TABLE IF NOT EXISTS write_intents (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    intent_uuid     TEXT NOT NULL UNIQUE,           -- short uuid4 for log correlation
    session_id      TEXT,
    content_hash    TEXT NOT NULL,                  -- sha1 of (type || project || content)
    payload_json    TEXT NOT NULL,                  -- full save_knowledge args
    status          TEXT NOT NULL DEFAULT 'pending'
                       CHECK (status IN ('pending','committed','failed','superseded')),
    knowledge_id    INTEGER,                        -- set on commit
    attempts        INTEGER NOT NULL DEFAULT 0,
    last_error      TEXT,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    committed_at    TEXT
);

CREATE INDEX IF NOT EXISTS idx_write_intents_status     ON write_intents(status);
CREATE INDEX IF NOT EXISTS idx_write_intents_hash       ON write_intents(content_hash);
CREATE INDEX IF NOT EXISTS idx_write_intents_session    ON write_intents(session_id);
CREATE INDEX IF NOT EXISTS idx_write_intents_created    ON write_intents(created_at);
