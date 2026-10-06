"""
question_C/benchmark_inserts.py   (evidence for Level 3)

Measures how many readings per second this machine can write to the readings table when
  (a) every reading is committed on its own (a naive "INSERT per reading" design)
  (b) readings are written in batches of 1,000 rows
The result is compared with the load the system needs: 1,000 writes/s (1,000 users) and
100,000 writes/s (100,000 users). Numbers depend on your computer; run it on yours.

Run:  python question_C/benchmark_inserts.py
"""
import os
import sqlite3
import tempfile
import time

import numpy as np

N = 7200            # rows per test (= 2 hours of one user)
BATCH = 1000
HERE = os.path.dirname(os.path.abspath(__file__))
schema = open(os.path.join(HERE, "schema.sql")).read()
rng = np.random.default_rng(2504)
hr = rng.normal(70, 3, N)
acc = rng.random(N)


def fresh_db(path):
    if os.path.exists(path):
        os.remove(path)
    con = sqlite3.connect(path)
    con.executescript(schema)
    con.execute("INSERT INTO users (user_id, name) VALUES (1, 'bench')")
    con.commit()
    return con


def rows():
    return [(1, f"2026-10-06 {i // 3600:02d}:{(i // 60) % 60:02d}:{i % 60:02d}", float(hr[i]), float(acc[i])) for i in range(N)]


data = rows()
tmp = tempfile.mkdtemp()

# (a) one commit per reading
con = fresh_db(os.path.join(tmp, "a.db"))
t0 = time.perf_counter()
for r in data:
    con.execute("INSERT INTO readings (user_id, ts, hr, acc) VALUES (?, ?, ?, ?)", r)
    con.commit()
a = N / (time.perf_counter() - t0)
con.close()

# (b) one commit per batch of 1,000 rows
con = fresh_db(os.path.join(tmp, "b.db"))
t0 = time.perf_counter()
for i in range(0, N, BATCH):
    con.executemany("INSERT INTO readings (user_id, ts, hr, acc) VALUES (?, ?, ?, ?)", data[i:i + BATCH])
    con.commit()
b = N / (time.perf_counter() - t0)
con.close()

print(f"(a) one commit per reading : {a:>12,.0f} rows/s")
print(f"(b) batches of {BATCH:<5}       : {b:>12,.0f} rows/s   ({b / a:.0f}x faster)")
print()
for users in (1_000, 100_000):
    need = users  # 1 reading per user per second
    print(f"{users:>7,} users need {need:>7,} writes/s -> "
          f"(a) headroom {a / need:>8.2f}x   (b) headroom {b / need:>8.2f}x   (this single SQLite file, this machine)")
