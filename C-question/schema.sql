-- question_C/schema.sql
-- Schema for the wearable monitoring system (1,000 users, 1 reading per second).
-- Written so it runs unchanged in SQLite (used in Level 2). MySQL notes are in comments.

PRAGMA foreign_keys = ON;

-- One row per person / device.
CREATE TABLE IF NOT EXISTS users (
    user_id     INTEGER PRIMARY KEY,
    name        TEXT    NOT NULL,
    created_at  TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Raw sensor readings: the big table (86.4 million rows per day for 1,000 users).
-- PRIMARY KEY (user_id, ts) serves two purposes:
--   * it rejects a duplicate reading if a device re-sends a batch (idempotent writes)
--   * it clusters each user's readings by time, so "user X, last hour" is a range scan
-- WITHOUT ROWID stores the table AS that primary-key index (like MySQL InnoDB), so no
-- second index and no hidden row id are needed.
-- ts format: 'YYYY-MM-DD HH:MM:SS' (sortable text in SQLite).
-- MySQL version: user_id INT UNSIGNED, ts TIMESTAMP (4 bytes), hr SMALLINT UNSIGNED, acc FLOAT,
-- partitioned by day on ts so old days can be dropped or archived cheaply.
CREATE TABLE IF NOT EXISTS readings (
    user_id  INTEGER NOT NULL REFERENCES users(user_id),
    ts       TEXT    NOT NULL,
    hr       REAL    NOT NULL,   -- heart rate in bpm (0 = sensor drop-out)
    acc      REAL    NOT NULL,   -- accelerometer magnitude
    PRIMARY KEY (user_id, ts)
) WITHOUT ROWID;

-- Alerts: tiny compared with readings (hundreds per user per day, not 86,400).
-- One alert covers one detected event (ts_start..ts_end), not one row per second.
CREATE TABLE IF NOT EXISTS alerts (
    alert_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(user_id),
    ts_start    TEXT    NOT NULL,
    ts_end      TEXT    NOT NULL,
    alert_type  TEXT    NOT NULL CHECK (alert_type IN ('spike', 'dropout', 'sudden_drop', 'drift')),
    detector    TEXT    NOT NULL,                 -- which detector/version raised it
    created_at  TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- "alerts for user X in a time range" (dashboard, per-user last-24-hours query)
CREATE INDEX IF NOT EXISTS idx_alerts_user_ts ON alerts (user_id, ts_start);
-- "alerts across all users in a time range" (operations view)
CREATE INDEX IF NOT EXISTS idx_alerts_ts ON alerts (ts_start);
