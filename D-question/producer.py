"""
question_D/producer.py   (Level 2: replay readings.csv into the database at one row per second)

Run:  python question_D/producer.py --reset             # whole recording, 1 row/s (2 hours)
      python question_D/producer.py --reset --start 40 --rows 120     # a slice
      python question_D/producer.py --speed 20 --reset                # 20x faster, for quick tests

Rows keep their recording timestamps; the wall-clock arrival time is stored in ingested_at
by the database itself. Rows are scheduled against a fixed start time (not 'sleep 1 s' after
each insert), so the replay does not drift when an insert is slow.
"""
import argparse
import csv
import os
import time

from db import DEFAULT_DB, connect, init_db

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CSV = os.path.join(HERE, "..", "setup", "readings.csv")


def load_rows(csv_path=DEFAULT_CSV):
    """[(row_index, ts, hr, acc), ...] from readings.csv (labels are NOT sent to the database)."""
    with open(csv_path) as fh:
        return [(i, r["timestamp"], float(r["hr"]), float(r["acc"])) for i, r in enumerate(csv.DictReader(fh))]


def replay(db_path, rows, user_id=1, speed=1.0, progress_every=60, log=print, stop=None):
    con = connect(db_path)
    t0 = time.perf_counter()
    for k, (idx, ts, hr, acc) in enumerate(rows):
        if stop is not None and stop.is_set():
            break
        wait = t0 + k / speed - time.perf_counter()       # absolute schedule: row k at k/speed seconds
        if wait > 0:
            time.sleep(wait)
        con.execute("INSERT OR IGNORE INTO readings (user_id, ts, hr, acc) VALUES (?, ?, ?, ?)",
                    (user_id, ts, hr, acc))
        con.commit()
        if log and progress_every and (k + 1) % progress_every == 0:
            log(f"  sent {k + 1}/{len(rows)} rows (recording time {ts})")
    con.close()


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Replay readings.csv into the database.")
    p.add_argument("--db", default=DEFAULT_DB)
    p.add_argument("--csv", default=DEFAULT_CSV)
    p.add_argument("--user", type=int, default=1)
    p.add_argument("--speed", type=float, default=1.0, help="1.0 = one row per second (the assignment)")
    p.add_argument("--start", type=int, default=0, help="first row to send")
    p.add_argument("--rows", type=int, default=None, help="how many rows to send (default: all)")
    p.add_argument("--reset", action="store_true", help="delete and recreate the database first")
    a = p.parse_args()

    init_db(a.db, reset=a.reset).close()
    data = load_rows(a.csv)
    data = data[a.start:] if a.rows is None else data[a.start:a.start + a.rows]
    print(f"Replaying {len(data)} rows into {a.db} at {a.speed:g} row(s)/s "
          f"(about {len(data) / a.speed / 60:.1f} min). Ctrl+C to stop.")
    try:
        replay(a.db, data, a.user, a.speed)
    except KeyboardInterrupt:
        print("stopped")
    print("done")
