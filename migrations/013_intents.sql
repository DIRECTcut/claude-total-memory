-- ══════════════════════════════════════════════════════════
-- v8.x — User intents (captured via UserPromptSubmit hook)
--
-- Each row = one user prompt as it was submitted to Claude Code.
-- Lets us trace "what the user asked" without mining transcripts,
-- enables intent search / analytics without needing LLM extraction.
-- ══════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS intents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    project TEXT,
    prompt TEXT NOT NULL,
    created_at TEXT NOT NULL,     -- ISO-8601 UTC
    turn_index INTEGER,           -- 0-based counter per session
    prompt_hash TEXT NOT NULL     -- sha256, for dedup
);

CREATE INDEX IF NOT EXISTS idx_intents_session ON intents(session_id);
CREATE INDEX IF NOT EXISTS idx_intents_project ON intents(project, created_at);
CREATE INDEX IF NOT EXISTS idx_intents_hash ON intents(prompt_hash);

INSERT OR IGNORE INTO migrations (version, description)
VALUES ('013', 'User intents table — captures prompts from UserPromptSubmit hook');
