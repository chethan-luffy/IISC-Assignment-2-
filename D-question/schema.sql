-- question_D/schema.sql
-- Same design as question_C/schema.sql, with three additions needed for the live system:
--   readings.ingested_at   wall-clock time the row arrived (lets me measure pipeline latency)
--   alerts.event_start_ts  when the detector believes the event started
--   alerts.detected_ts     recording time of the reading that triggered the alert
-- Wall-clock columns use SQLite's own clock (UTC, millisecond precision), so ingested_at and
-- created_at come from the same clock and can be subtracted.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    user_id  INTEGER PRIMARY KEY,
    name     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS readings (
    user_id      INTEGER NOT NULL REFERENCES users(user_id),
    ts           TEXT    NOT NULL,                  -- recording time 'YYYY-MM-DD HH:MM:SS'
    hr           REAL    NOT NULL,
    acc          REAL    NOT NULL,
    ingested_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now')),
    PRIMARY KEY (user_id, ts)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS alerts (
    alert_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL REFERENCES users(user_id),
    alert_type      TEXT    NOT NULL CHECK (alert_type IN ('spike', 'dropout')),
    event_start_ts  TEXT    NOT NULL,
    detected_ts     TEXT    NOT NULL,
    hr              REAL,
    z               REAL,
    detector        TEXT    NOT NULL,
    created_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now')),
    UNIQUE (user_id, alert_type, detected_ts)       -- re-processing the same reading never duplicates an alert
);

CREATE INDEX IF NOT EXISTS idx_alerts_user_ts ON alerts (user_id, detected_ts);
