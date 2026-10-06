"""
Question D, Level 3: measure the delay from anomaly start to alert.

BEFORE running this file you must have committed question_D/PREDICTION.md.

Run:  python question_D/level3_measure_delay.py            # replays at 10x speed (about 2 min)
      python question_D/level3_measure_delay.py --speed 1  # real time (about 20 min)

Delay is split into two parts so the main source can be named with evidence:
  1. DETECTION delay: recording seconds between the event start and the reading that triggers
     the alert. This is the confirmation rule (2 readings, or 4 identical readings).
  2. PIPELINE latency: wall-clock time between that reading arriving in the database
     (ingested_at) and the alert row being written (created_at). This is engine polling + write.
The dashboard adds up to its refresh interval on top (not measured here, default 2 s).

Part A is deterministic (offline, every event of the whole recording).
Part B runs the REAL stack: producer thread -> SQLite -> alert engine thread -> alerts table.
"""
import argparse
import csv
import os
import statistics
import subprocess
import tempfile
import threading
import time

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from alert_engine import run_engine
from db import FMT, connect, init_db, parse_ms, parse_ts
from evaluate import load_recording, match, run_offline
from producer import replay

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "results")
os.makedirs(RESULTS, exist_ok=True)

ap = argparse.ArgumentParser()
ap.add_argument("--speed", type=float, default=10.0, help="replay speed for Part B (1 = real time)")
ap.add_argument("--lead", type=int, default=45, help="seconds replayed before each event")
ap.add_argument("--tail", type=int, default=20, help="seconds replayed after each event")
args = ap.parse_args()

# soft proof that the prediction was committed first
try:
    out = subprocess.run(["git", "log", "--format=%cI", "--", "question_D/PREDICTION.md"],
                         capture_output=True, text=True, cwd=os.path.join(HERE, "..")).stdout.strip()
    print("PREDICTION.md commit:", out.splitlines()[-1] if out else "NOT COMMITTED YET -> commit it before trusting this run!")
except Exception:
    print("git not available: make sure PREDICTION.md was committed before this run.")
print()

ts, hr, acc, events = load_recording()
targets = [e for e in events if e[0] in ("spike", "dropout")]


def stats(vals):
    return statistics.mean(vals), max(vals)


# ------------------------------------------------------------------ Part A: offline detection delay
alerts, _ = run_offline(ts, hr, acc)
base, _ = match(events, alerts, ts)
alerts_f, _ = run_offline(ts, hr, acc, fast_z=10)
fast, _ = match(events, alerts_f, ts)

print("PART A: detection delay in recording time (deterministic, all spike and drop-out events)")
print(f"{'type':<9}{'start':>7}{'confirm rule':>14}{'fast path':>11}")
for b, f in zip(base, fast):
    print(f"{b['type']:<9}{b['start_idx']:>7}{b['delay_s']:>13.0f}s{f['delay_s']:>10.0f}s")
bd = [r["delay_s"] for r in base]
fd = [r["delay_s"] for r in fast]
print(f"\nconfirmation rule : average {stats(bd)[0]:.2f} s, worst {stats(bd)[1]:.0f} s")
print(f"fast path (single reading if |z|>10 or reading 0): average {stats(fd)[0]:.2f} s, worst {stats(fd)[1]:.0f} s")
for kind in ("spike", "dropout"):
    print(f"  {kind:<8} confirm {statistics.mean(r['delay_s'] for r in base if r['type'] == kind):.2f} s   "
          f"fast {statistics.mean(r['delay_s'] for r in fast if r['type'] == kind):.2f} s")

# ------------------------------------------------------------------ Part B: the real pipeline
keep = set()
for kind, s, l in targets:
    keep.update(range(max(0, s - args.lead), min(len(hr), s + l + args.tail)))
rows = [(i, ts[i].strftime(FMT), hr[i], acc[i]) for i in sorted(keep)]

tmp = tempfile.mkdtemp()                       # local temp folder: WAL needs a normal local disk
db = os.path.join(tmp, "measure.db")
init_db(db, reset=True).close()
stop = threading.Event()
engine = threading.Thread(target=run_engine, kwargs=dict(db_path=db, poll_s=0.2, stop=stop, log=lambda *_: None), daemon=True)
engine.start()
print(f"\nPART B: real pipeline, replaying {len(rows)} rows at {args.speed:g}x "
      f"(about {len(rows) / args.speed:.0f} s). Please wait...")
replay(db, rows, speed=args.speed, progress_every=0, log=None)
time.sleep(1.0)
stop.set()
engine.join(timeout=3)

con = connect(db, readonly=True)
live = con.execute(
    "SELECT a.alert_type, a.detected_ts, a.created_at, r.ingested_at "
    "FROM alerts a JOIN readings r ON r.user_id = a.user_id AND r.ts = a.detected_ts ORDER BY a.detected_ts").fetchall()
con.close()
ts_index = {t.strftime(FMT): i for i, t in enumerate(ts)}

result = []
used = set()
for kind, s, l in targets:
    hit = None
    for k, (atype, det, created, ingested) in enumerate(live):
        i = ts_index[det]
        if atype == kind and s <= i < s + l and k not in used:
            hit = (k, det, created, ingested)
            break
    if not hit:
        result.append({"type": kind, "start_idx": s, "detection_s": None, "pipeline_ms": None})
        continue
    used.add(hit[0])
    detection = (parse_ts(hit[1]) - ts[s]).total_seconds()
    pipeline = (parse_ms(hit[2]) - parse_ms(hit[3])).total_seconds() * 1000
    result.append({"type": kind, "start_idx": s, "detection_s": detection, "pipeline_ms": pipeline})

print(f"\n{'type':<9}{'start':>7}{'detection (s)':>15}{'pipeline (ms)':>15}{'total (s)':>11}")
for r in result:
    if r["detection_s"] is None:
        print(f"{r['type']:<9}{r['start_idx']:>7}{'MISSED':>15}")
        continue
    r["total_s"] = r["detection_s"] + r["pipeline_ms"] / 1000
    print(f"{r['type']:<9}{r['start_idx']:>7}{r['detection_s']:>15.0f}{r['pipeline_ms']:>15.0f}{r['total_s']:>11.2f}")

ok = [r for r in result if r["detection_s"] is not None]
det = [r["detection_s"] for r in ok]
pipe = [r["pipeline_ms"] for r in ok]
tot = [r["total_s"] for r in ok]
print(f"\nEvents measured: {len(ok)}/{len(result)}")
print(f"Detection delay (recording seconds): average {stats(det)[0]:.2f} s, worst {stats(det)[1]:.0f} s")
print(f"Pipeline latency (wall clock)      : average {stats(pipe)[0]:.0f} ms, worst {stats(pipe)[1]:.0f} ms")
print(f"Total start-to-alert (real time, at 1 reading/s): average {stats(tot)[0]:.2f} s, worst {stats(tot)[1]:.2f} s")
print(f"Share of the average delay that is the confirmation rule: {100 * stats(det)[0] / stats(tot)[0]:.0f} %")
print("The dashboard adds up to its refresh interval (default 2 s) before the alert is VISIBLE.")

print("\nPREDICTION CHECK (see PREDICTION.md)")
print(f"  average delay about 1.4 s, worst <= 2 (max 3): measured {stats(tot)[0]:.2f} s / {stats(tot)[1]:.2f} s")
print(f"  pipeline latency 100-300 ms: measured average {stats(pipe)[0]:.0f} ms")
print(f"  fast path: spike and zero drop-out to about 0 s: measured average {stats(fd)[0]:.2f} s (worst {stats(fd)[1]:.0f} s)")

with open(os.path.join(RESULTS, "level3_delay_table.csv"), "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["type", "start_idx", "detection_s", "pipeline_ms", "total_s", "fast_path_detection_s"])
    for r, f in zip(result, fast):
        w.writerow([r["type"], r["start_idx"], r.get("detection_s"), r.get("pipeline_ms"), r.get("total_s"), f["delay_s"]])

# ------------------------------------------------------------------ plot
fig, ax = plt.subplots(figsize=(12, 4.5))
x = range(len(ok))
ax.bar(x, [r["detection_s"] for r in ok], color="#2563eb", label="detection (confirmation rule), recording seconds")
ax.bar(x, [r["pipeline_ms"] / 1000 for r in ok], bottom=[r["detection_s"] for r in ok], color="#f59e0b",
       label="pipeline (poll + write), wall seconds")
ax.scatter(x, fd[:len(ok)], color="#16a34a", zorder=3, label="fast path (single reading) detection delay")
ax.axhline(5, color="red", ls="--", lw=1)
ax.text(len(ok) - 0.5, 5.05, "5 s requirement", ha="right", color="red", fontsize=9)
ax.set_xticks(list(x))
ax.set_xticklabels([f"{r['type'][:2]}@{r['start_idx']}" for r in ok], rotation=60, fontsize=8)
ax.set_ylabel("seconds from event start to alert")
ax.set_ylim(0, 6)
ax.set_title("Level 3: where the alert delay comes from")
ax.legend(loc="upper left", fontsize=8)
plt.tight_layout()
plt.savefig(os.path.join(RESULTS, "level3_delay.png"), dpi=120)
print(f"\nSaved table and plot to {RESULTS}")
