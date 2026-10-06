"""
question_D/alert_engine.py   (Level 2: my own alert logic, no ML library)

StreamAlertEngine.update(ts, hr, acc) is called once per new reading and returns an
Alert or None. It is the streaming version of the Question A rolling z-score:

  * keeps the last `window` normal resting readings (circular buffer, running sums)
  * moving gate: while acc is high the person is walking, so no alerts and no baseline update
  * SPIKE   : HR is above the baseline by more than z_thresh sigma for `confirm` readings in a row
  * DROPOUT : HR reads <= 0 (same z test), or `flat_len` identical readings in a row (stuck sensor)
  * A sudden NON-ZERO drop is not alerted (it is how a silent drift ends, see Question A)

Requirement 1: alert within 5 s of a spike or drop-out starting.
   With 1 reading per second the alert needs `confirm` = 2 readings (spike, zero drop-out)
   or `flat_len` = 4 identical readings (stuck sensor), so the delay is 1 to 2 s.
Requirement 2: the same event must not raise a repeat alert within 60 s.
   After an alert of one type, further alerts of that type are suppressed for `cooldown_s`
   seconds of RECORDING time (so it works the same at any replay speed).

Optional fast path (fast_z): alert on a single reading when |z| > fast_z or the reading is 0.
Used in Level 3 to show how much confirmation costs.

run_engine() polls the database for new readings and writes alerts to the alerts table.
Run:  python question_D/alert_engine.py
"""
import argparse
import math
import sqlite3
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta

from db import DEFAULT_DB, init_db, parse_ts, FMT


@dataclass
class Alert:
    alert_type: str            # 'spike' or 'dropout'
    event_start_ts: datetime   # when the detector believes the event began
    detected_ts: datetime      # recording time of the reading that triggered the alert
    hr: float
    z: float


class StreamAlertEngine:
    def __init__(self, window=60, z_thresh=3.0, confirm=2, min_samples=30, flat_len=4,
                 acc_thresh=0.5, acc_hold=3, max_breach=15, std_floor=0.5,
                 cooldown_s=60, fast_z=None):
        self.window, self.z_thresh, self.confirm = window, z_thresh, confirm
        self.min_samples, self.flat_len = min_samples, flat_len
        self.acc_thresh, self.max_breach, self.std_floor = acc_thresh, max_breach, std_floor
        self.cooldown_s, self.fast_z = cooldown_s, fast_z

        self.buf = [0.0] * window          # circular buffer of accepted readings
        self.count = 0
        self.head = 0
        self.s1 = 0.0                      # running sum
        self.s2 = 0.0                      # running sum of squares
        self.recent_hr = deque(maxlen=flat_len)
        self.recent_acc = deque(maxlen=acc_hold)
        self.streak = 0                    # consecutive breaches
        self.breach_run = 0
        self.first_breach_ts = None
        self.last_alert = {}               # alert type -> recording time of its last alert
        self.suppressed = 0                # alerts blocked by the 60 s cooldown

    # ---- baseline buffer ------------------------------------------------------------
    def _push(self, x):
        if self.count == self.window:
            old = self.buf[self.head]
            self.s1 -= old
            self.s2 -= old * old
        else:
            self.count += 1
        self.buf[self.head] = x
        self.s1 += x
        self.s2 += x * x
        self.head = (self.head + 1) % self.window

    def _reset_baseline(self):
        self.count, self.head, self.s1, self.s2 = 0, 0, 0.0, 0.0

    # ---- one new reading --------------------------------------------------------------
    def update(self, ts, hr, acc):
        self.recent_hr.append(hr)
        self.recent_acc.append(acc)

        # moving gate: walking is normal
        if max(self.recent_acc) > self.acc_thresh:
            self.streak, self.breach_run, self.first_breach_ts = 0, 0, None
            return None

        flat = (len(self.recent_hr) == self.flat_len
                and max(self.recent_hr) - min(self.recent_hr) < 1e-9)

        z, breach = None, False
        if self.count >= self.min_samples:
            mean = self.s1 / self.count
            std = max(math.sqrt(max(self.s2 / self.count - mean * mean, 0.0)), self.std_floor)
            z = (hr - mean) / std
            breach = abs(z) > self.z_thresh

        if breach:
            if self.streak == 0:
                self.first_breach_ts = ts
            self.streak += 1
            self.breach_run += 1
        else:
            self.streak, self.breach_run, self.first_breach_ts = 0, 0, None

        # decide whether this reading confirms an event
        kind, start = None, ts
        if flat:
            kind, start = "dropout", ts - timedelta(seconds=self.flat_len - 1)
        elif breach:
            confirmed = self.streak >= self.confirm or (
                self.fast_z is not None and (abs(z) > self.fast_z or hr <= 0))
            if confirmed:
                start = self.first_breach_ts
                if hr <= 0:
                    kind = "dropout"
                elif z > 0:
                    kind = "spike"            # a non-zero downward breach is not alerted

        alert = None
        if kind is not None:
            last = self.last_alert.get(kind)
            if last is None or (ts - last).total_seconds() >= self.cooldown_s:
                self.last_alert[kind] = ts
                alert = Alert(kind, start, ts, hr, z if z is not None else float("nan"))
            else:
                self.suppressed += 1          # same kind of event inside the cooldown

        # only normal readings update the baseline
        if not flat and not breach:
            self._push(hr)
        elif breach and self.breach_run > self.max_breach:
            self._reset_baseline()            # a long breach is a new level, relearn
            self._push(hr)
            self.streak, self.breach_run = 0, 0
        return alert


# ----------------------------------------------------------------------------------------
def run_engine(db_path=DEFAULT_DB, user_id=1, poll_s=0.2, stop=None, log=print):
    """Poll the database for new readings, run the engine, insert alerts."""
    con = init_db(db_path)                 # creates the tables if the producer has not started yet
    engine = StreamAlertEngine()
    last_ts = ""
    while stop is None or not stop.is_set():
        try:
            rows = con.execute("SELECT ts, hr, acc FROM readings WHERE user_id = ? AND ts > ? ORDER BY ts",
                               (user_id, last_ts)).fetchall()
        except sqlite3.OperationalError as e:      # e.g. database briefly locked: try again
            log(f"database busy ({e}); retrying")
            time.sleep(1)
            continue
        for ts, hr, acc in rows:
            last_ts = ts
            a = engine.update(parse_ts(ts), hr, acc)
            if a:
                con.execute(
                    "INSERT OR IGNORE INTO alerts (user_id, alert_type, event_start_ts, detected_ts, hr, z, detector) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (user_id, a.alert_type, a.event_start_ts.strftime(FMT), a.detected_ts.strftime(FMT),
                     a.hr, a.z, "stream_zscore_v1"))
                con.commit()
                log(f"ALERT {a.alert_type:<7} user {user_id} detected at {a.detected_ts:%H:%M:%S}  hr={a.hr:.1f}  z={a.z:.1f}")
        time.sleep(poll_s)
    con.close()


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Streaming alert engine: reads new rows from the database.")
    p.add_argument("--db", default=DEFAULT_DB)
    p.add_argument("--user", type=int, default=1)
    p.add_argument("--poll", type=float, default=0.2, help="seconds between database polls")
    args = p.parse_args()
    print(f"Alert engine watching {args.db} for user {args.user} (Ctrl+C to stop)")
    try:
        run_engine(args.db, args.user, args.poll)
    except KeyboardInterrupt:
        print("stopped")
