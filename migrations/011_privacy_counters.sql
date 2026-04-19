-- Migration 011: Privacy counters
-- Cumulative counter for <private>...</private> inline-tag redactions (P0.1).
CREATE TABLE IF NOT EXISTS privacy_counters (
    key        TEXT PRIMARY KEY,
    value      INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);

INSERT OR IGNORE INTO privacy_counters (key, value, updated_at)
VALUES ('private_redactions_total', 0, '1970-01-01T00:00:00Z');
