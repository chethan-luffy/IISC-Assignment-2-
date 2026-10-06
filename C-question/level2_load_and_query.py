"""
Question C, Level 2: load readings.csv as three users into SQLite and run three SQL queries.

Run:  python question_C/level2_load_and_query.py

Steps
  1. Create wearables.db from schema.sql.
  2. Load readings.csv three times as three users, each with a different time offset.
  3. Raise alerts per user with the Question A rolling z-score detector, merging
     consecutive flagged seconds into ONE alert per event.
  4. Run the three hand-written queries in queries.sql and print / save the output.
Seed S = 2504 (the data and detector are deterministic).
"""
import os
import re
import sqlite3
import sys
import time

import numpy as np
import pandas as pd
# 1. Standard library imports must come first
import os
import sys

# 2. PASTE THE 'HERE' VARIABLE DEFINITION EXACTLY HERE:
HERE = os.path.dirname(os.path.abspath(__file__))

# 3. Use 'HERE' to connect to your Question A folder path dynamically
sys.path.append(os.path.abspath(os.path.join(HERE, '..', 'question-A')))

# 4. Your module imports come next
try:
    from zscore_detector import rolling_zscore_detector
    print("✅ Successfully linked and imported the custom Z-Score detector from Question A!")
except ModuleNotFoundError:
    from level2_rolling_zscore import numpy_rolling_zscore as rolling_zscore_detector
    print("✅ Successfully linked and imported the custom Z-Score detector from level2_custom!")

# 5. Your database path logic uses the variable right below
DB = os.path.join(HERE, "wearables.db")

RESULTS = os.path.join(HERE, "results")
os.makedirs(RESULTS, exist_ok=True)
FMT = "%Y-%m-%d %H:%M:%S"

# three users: same recording, different clock offsets (my choice)
USERS = [
    (1, "user_1 (offset 0)", 0),
    (2, "user_2 (+45 min)", 45 * 60),
    (3, "user_3 (-26 h, yesterday)", -26 * 3600),
]
DETECTOR = "rolling_zscore_w60"


def build_alerts(ts, hr, flags, base_mean, merge_gap=5):
    """One alert per event: flagged seconds closer than merge_gap seconds are merged."""
    idx = np.flatnonzero(flags)
    if len(idx) == 0:
        return []
    groups = np.split(idx, np.flatnonzero(np.diff(idx) > merge_gap) + 1)
    out = []
    for g in groups:
        a, b = g[0], g[-1]
        seg = hr[a:b + 1]
        if np.ptp(seg) < 1e-9 or seg.max() <= 0:
            kind = "dropout"                         # stuck or zero sensor
        else:
            ref = base_mean[a] if np.isfinite(base_mean[a]) else np.nanmedian(hr)
            kind = "spike" if seg.mean() > ref else "sudden_drop"
        out.append((ts[a], ts[b], kind))
    return out


# ------------------------------------------------------------------ 1. create db
if os.path.exists(DB):
    os.remove(DB)
con = sqlite3.connect(DB)
with open(os.path.join(HERE, "schema.sql")) as fh:
    con.executescript(fh.read())

# ------------------------------------------------------------------ 2. load readings
df = pd.read_csv(os.path.join(HERE, "..", "setup", "readings.csv"), parse_dates=["timestamp"])
hr, acc = df["hr"].to_numpy(float), df["acc"].to_numpy(float)

flags, base_mean, _ = rolling_zscore_detector(hr, acc, window=60)

t0 = time.perf_counter()
n_read = n_alert = 0
for uid, name, offset in USERS:
    con.execute("INSERT INTO users (user_id, name) VALUES (?, ?)", (uid, name))
    ts = (df["timestamp"] + pd.Timedelta(seconds=offset)).dt.strftime(FMT).to_numpy()
    con.executemany("INSERT INTO readings (user_id, ts, hr, acc) VALUES (?, ?, ?, ?)",
                    zip([uid] * len(df), ts, hr, acc))
    n_read += len(df)
    # ------------------------------------------------------------ 3. alerts
    alerts = build_alerts(ts, hr, flags, base_mean)
    con.executemany("INSERT INTO alerts (user_id, ts_start, ts_end, alert_type, detector) VALUES (?, ?, ?, ?, ?)",
                    [(uid, a, b, k, DETECTOR) for a, b, k in alerts])
    n_alert += len(alerts)
con.commit()
print(f"Loaded {n_read:,} readings for {len(USERS)} users and {n_alert} alerts in {time.perf_counter() - t0:.2f} s")

page_size = con.execute("PRAGMA page_size").fetchone()[0]
pages = con.execute("PRAGMA page_count").fetchone()[0]
print(f"Database file: {page_size * pages / 1e6:.2f} MB  ({page_size * pages / n_read:.1f} bytes per reading row, "
      f"including the small alerts table)\n")

print("Alerts by user and type:")
for row in con.execute("SELECT user_id, alert_type, COUNT(*) FROM alerts GROUP BY user_id, alert_type ORDER BY user_id, alert_type"):
    print("  ", row)
print()

# ------------------------------------------------------------------ 4. run the queries
sql = open(os.path.join(HERE, "queries.sql")).read()
blocks = [b for b in sql.split(";") if "SELECT" in b]
titles = re.findall(r"^-- (Q\d\..*?)(?: -+)?$", sql, flags=re.M)


def fmt_table(cols, rows):
    widths = [max(len(str(c)), *(len(str(r[i])) for r in rows)) if rows else len(str(c)) for i, c in enumerate(cols)]
    line = "  ".join(str(c).ljust(w) for c, w in zip(cols, widths))
    out = [line, "  ".join("-" * w for w in widths)]
    out += ["  ".join(str(v).ljust(w) for v, w in zip(r, widths)) for r in rows]
    return "\n".join(out)


report = []
for title, block in zip(titles, blocks):
    cur = con.execute(block)
    cols = [c[0] for c in cur.description]
    rows = cur.fetchall()
    text = f"{title}\n{fmt_table(cols, rows)}\n({len(rows)} rows)\n"
    print(text)
    report.append(text)

with open(os.path.join(RESULTS, "level2_query_outputs.txt"), "w") as fh:
    fh.write("\n".join(report))
con.close()
print(f"Saved query outputs to {RESULTS}/level2_query_outputs.txt")
