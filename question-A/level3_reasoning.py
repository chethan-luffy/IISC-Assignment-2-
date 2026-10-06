"""
Question A, Level 3: reason with your results

BEFORE running this file you must have committed question_A/PREDICTION.md
(git add question_A/PREDICTION.md && git commit -m "Level 3 prediction" && git push).

Run:  python question_A/level3_reasoning.py

What it does
  1. Doubles the rolling z-score window (60 s -> 120 s; also 30/240/480 for context)
     and reports drift recall, so it can be compared with the prediction.
  2. Measures the largest |z| reached inside each drift (the method's own logic).
  3. Plots one anomaly that EACH method missed (z-score and Isolation Forest).
"""
import os
import subprocess
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.ensemble import IsolationForest

import common as C
from features import build_features
from zscore_detector import rolling_zscore_detector

# ---- proof that the prediction was committed first (soft check) ----
try:
    out = subprocess.run(["git", "log", "--format=%H %cI", "--", "question_A/PREDICTION.md"],
                         capture_output=True, text=True, cwd=os.path.join(C.HERE, "..")).stdout.strip()
    print("PREDICTION.md commit:", out.splitlines()[-1] if out else "NOT COMMITTED YET -> commit it before trusting this run!")
except Exception:
    print("git not available: make sure PREDICTION.md was committed before this run.")
print()

d = C.load()
hr, acc, events = d["hr"], d["acc"], d["events"]

# ---------------------------------------------------------------- 1. window sweep
rows = []
cache = {}
for W in [30, 60, 120, 240, 480]:
    flags, mean, std = rolling_zscore_detector(hr, acc, window=W)
    cache[W] = (flags, mean, std)
    p = flags.astype(int)
    rec = {t: C.type_recall(events, p, t) for t in C.TYPES}
    fa_w, _ = C.walking_false_alarms(p, d["walk"])
    fp_other = int(((p == 1) & (d["label"] == 0) & ~d["walk"]).sum())
    rows.append({
        "window_s": W,
        "drift_recall_sec": rec["drift"][0], "drift_events_found": rec["drift"][1],
        "spike_recall_sec": rec["spike"][0], "dropout_recall_sec": rec["dropout"][0],
        "walking_FA_s": fa_w, "other_FP_s": fp_other,
    })
sweep = pd.DataFrame(rows)
sweep.to_csv(f"{C.RESULTS}/level3_window_sweep.csv", index=False)
print("Rolling z-score: effect of the window size")
print(sweep.to_string(index=False, float_format=lambda v: f"{v:.3f}"))

r60 = sweep.loc[sweep.window_s == 60, "drift_recall_sec"].item()
r120 = sweep.loc[sweep.window_s == 120, "drift_recall_sec"].item()
print(f"\nPREDICTION CHECK  drift recall W=60: {r60:.3%}   W=120: {r120:.3%}   change: {100 * (r120 - r60):+.2f} percentage points")

# ---------------------------------------------------------------- 2. max |z| inside each drift
print("\nLargest z reached inside each silent drift (threshold is 3.0):")
print(f"{'drift start':>12}{'max z, W=60':>14}{'max z, W=120':>15}")
drifts = [e for e in events if e[0] == "drift"]
for _, s, l in sorted(drifts, key=lambda e: e[1]):
    vals = []
    for W in (60, 120):
        _, m, sd = cache[W]
        z = (hr[s:s + l] - m[s:s + l]) / sd[s:s + l]
        vals.append(np.nanmax(z) if np.isfinite(z).any() else np.nan)
    print(f"{s:>12d}{vals[0]:>14.2f}{vals[1]:>15.2f}")
print("Theory: for a noise-free ramp the trailing-window z can never exceed sqrt(3) = 1.73.")

# ---------------------------------------------------------------- 3. missed anomalies
# Isolation Forest (same settings as Level 1)
X = build_features(hr, acc)
Xv = X.to_numpy()
iforest = IsolationForest(n_estimators=200, contamination=0.05, random_state=C.S).fit(Xv)
if_pred = (iforest.predict(Xv) == -1).astype(int)
if_score = -iforest.score_samples(Xv)
if_thr = np.sort(if_score)[-int(0.05 * len(if_score))]

zs_flags, zs_mean, zs_std = cache[60]


def worst_missed(pred):
    tab = C.event_table(events, pred)
    return min(tab, key=lambda e: (e["flagged_s"], -e["length"]))


def pad(e, m=150):
    return max(0, e["start"] - m), min(len(hr), e["start"] + e["length"] + m)


# --- z-score missed anomaly
e = worst_missed(zs_flags.astype(int))
a, b = pad(e)
tt = np.arange(a, b)
z = (hr - zs_mean) / zs_std
fig, ax = plt.subplots(2, 1, figsize=(13, 7), sharex=True)
ax[0].plot(tt, hr[a:b], color="steelblue", lw=1, label="HR")
ax[0].plot(tt, zs_mean[a:b], color="green", lw=1.2, label="rolling baseline (mean of last 60 resting s)")
ax[0].fill_between(tt, (zs_mean - 3 * zs_std)[a:b], (zs_mean + 3 * zs_std)[a:b], color="green", alpha=0.15, label="+/- 3 std band")
ax[0].axvspan(e["start"], e["start"] + e["length"], color="orange", alpha=0.25, label=f"true {e['type']}")
ax[0].set_ylabel("HR (bpm)")
ax[0].set_title(f"Missed by rolling z-score: {e['type']} at t={e['start']} s ({e['flagged_s']} of {e['length']} s flagged)")
ax[0].legend(loc="upper left", fontsize=8)
ax[1].plot(tt, z[a:b], color="purple", lw=1)
ax[1].axhline(3, color="red", ls="--", lw=1)
ax[1].axhline(-3, color="red", ls="--", lw=1)
ax[1].axvspan(e["start"], e["start"] + e["length"], color="orange", alpha=0.25)
ax[1].set_ylabel("z-score")
ax[1].set_xlabel("time (s)")
plt.tight_layout()
plt.savefig(f"{C.RESULTS}/level3_missed_zscore.png", dpi=120)
print(f"\nz-score missed: {e}")

# --- Isolation Forest missed anomaly
e2 = worst_missed(if_pred)
a, b = pad(e2)
tt = np.arange(a, b)
normal = d["label"] == 0
lo, hi = np.percentile(X["resid_m60"][normal & ~d["walk"]], [1, 99])
fig, ax = plt.subplots(3, 1, figsize=(13, 9), sharex=True)
ax[0].plot(tt, hr[a:b], color="steelblue", lw=1)
ax[0].axvspan(e2["start"], e2["start"] + e2["length"], color="orange", alpha=0.25, label=f"true {e2['type']}")
fl = np.flatnonzero(if_pred[a:b]) + a
ax[0].scatter(fl, hr[fl], color="magenta", s=10, label="IF flag")
ax[0].set_ylabel("HR (bpm)")
ax[0].set_title(f"Missed by Isolation Forest: {e2['type']} at t={e2['start']} s ({e2['flagged_s']} of {e2['length']} s flagged)")
ax[0].legend(loc="upper left", fontsize=8)
ax[1].plot(tt, X["resid_m60"].to_numpy()[a:b], color="teal", lw=1)
ax[1].axhspan(lo, hi, color="gray", alpha=0.2, label="normal range (1st-99th percentile)")
ax[1].set_ylabel("feature resid_m60")
ax[1].legend(loc="upper left", fontsize=8)
ax[2].plot(tt, if_score[a:b], color="gray", lw=1)
ax[2].axhline(if_thr, color="magenta", ls="--", label="flag threshold")
ax[2].set_ylabel("IF anomaly score")
ax[2].set_xlabel("time (s)")
ax[2].legend(loc="upper left", fontsize=8)
for a_ in ax:
    a_.axvspan(e2["start"], e2["start"] + e2["length"], color="orange", alpha=0.15)
plt.tight_layout()
plt.savefig(f"{C.RESULTS}/level3_missed_iforest.png", dpi=120)
print(f"Isolation Forest missed: {e2}")

# ---------------------------------------------------------------- window sweep plot
fig, ax = plt.subplots(figsize=(7, 4))
ax.plot(sweep.window_s, 100 * sweep.drift_recall_sec, "o-", label="drift")
ax.plot(sweep.window_s, 100 * sweep.spike_recall_sec, "s-", label="spike")
ax.plot(sweep.window_s, 100 * sweep.dropout_recall_sec, "^-", label="drop-out")
ax.set_xscale("log")
ax.set_xticks(sweep.window_s)
ax.set_xticklabels(sweep.window_s)
ax.set_xlabel("z-score window (s)")
ax.set_ylabel("recall (% of anomalous seconds)")
ax.set_title("Recall vs window size")
ax.legend()
plt.tight_layout()
plt.savefig(f"{C.RESULTS}/level3_window_sweep.png", dpi=120)
print(f"\nSaved plots/tables to {C.RESULTS}")
