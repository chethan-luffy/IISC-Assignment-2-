"""
question_D/db.py   shared database helpers (SQLite, WAL mode so the producer, the alert
engine and the dashboard can all use the same file at the same time).
"""
import os
import sqlite3
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB = os.path.join(HERE, "live.db")
FMT = "%Y-%m-%d %H:%M:%S"
FMT_MS = "%Y-%m-%d %H:%M:%S.%f"


def connect(path=DEFAULT_DB, readonly=False):
    if readonly:
        return sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5)
    con = sqlite3.connect(path, timeout=10)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=NORMAL")
    return con


def init_db(path=DEFAULT_DB, reset=False):
    if reset:
        for suffix in ("", "-wal", "-shm"):
            if os.path.exists(path + suffix):
                os.remove(path + suffix)
    con = connect(path)
    with open(os.path.join(HERE, "schema.sql")) as fh:
        con.executescript(fh.read())
    con.execute("INSERT OR IGNORE INTO users (user_id, name) VALUES (1, 'user_1')")
    con.commit()
    return con


def parse_ts(s):
    return datetime.strptime(s, FMT)


def parse_ms(s):
    return datetime.strptime(s, FMT_MS)
