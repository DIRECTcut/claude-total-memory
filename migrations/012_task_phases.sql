-- ══════════════════════════════════════════════════════════
-- v8.0 — Task phases state machine
-- Explicit phase tracking for tasks (van → plan → creative → build → reflect → archive).
-- Inspired by vanzan01/cursor-memory-bank (memory #3606).
-- ══════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS task_phases (
    task_id TEXT NOT NULL,
    phase TEXT NOT NULL,            -- van | plan | creative | build | reflect | archive
    entered_at TEXT NOT NULL,       -- ISO-8601 UTC
    exited_at TEXT,                 -- null = current
    artifacts_json TEXT,            -- JSON: { "files": [...], "decisions": [...], "links": [...] }
    notes TEXT,
    PRIMARY KEY (task_id, phase, entered_at)
);

CREATE INDEX IF NOT EXISTS idx_task_phases_task ON task_phases(task_id);
CREATE INDEX IF NOT EXISTS idx_task_phases_current ON task_phases(task_id) WHERE exited_at IS NULL;
