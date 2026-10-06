"""
Question A, Level 2: code it yourself

  * zscore_detector.py : rolling z-score, NumPy only
  * my_metrics.py      : own precision / recall / F1, NumPy only
  * this file          : runs both, then PROVES my metric function equals
                         scikit-learn's on my data (scikit-learn is imported
                         only inside the verification step, never in the detector).

Run:  python question_A/level2_rolling_zscore.py
"""
import numpy as np
import common as C
from my_metrics import precision_recall_f1
from zscore_detector import rolling_zscore_detector

WINDOW = 60

d = C.load()
flags, mean, std = rolling_zscore_detector(d["hr"], d["acc"], window=WINDOW)
pred = flags.astype(int)

print(f"Rolling z-score detector (NumPy only), window={WINDOW} s, threshold=3.0, seed S={C.S}\n")
rows = C.per_type_table(d["atype"], d["label"], pred, precision_recall_f1)
C.print_table(rows)

wfa_s, wfa_b = C.walking_false_alarms(pred, d["walk"])
print(f"\nFalse alarms during walking: {wfa_s} seconds in {wfa_b} bursts")

print("\nEvent-level view:")
for t in C.TYPES:
    sec, evt = C.type_recall(d["events"], pred, t)
    n_ev = sum(1 for e in d["events"] if e[0] == t)
    delays = [e["delay_s"] for e in C.event_table(d["events"], pred) if e["type"] == t and e["detected"]]
    avg = f"{np.mean(delays):.1f}s" if delays else "-"
    print(f"  {t:<8} events found {round(evt * n_ev)}/{n_ev}   second-level recall {sec:.2f}   avg delay to first flag {avg}")

# ---------------------------------------------------------------------------
# Verification: my P/R/F1 vs scikit-learn on the same predictions
# ---------------------------------------------------------------------------
from sklearn.metrics import precision_score, recall_score, f1_score  # verification only

print("\nVerification against scikit-learn (own value | sklearn value):")
all_ok = True
for name, p, r, f, *_ in rows:
    if name == "overall":
        y, yp = d["label"], pred
    else:
        m = C.type_subset(d["atype"], name)
        y, yp = (d["atype"][m] == name).astype(int), pred[m]
    sp = precision_score(y, yp, zero_division=0)
    sr = recall_score(y, yp, zero_division=0)
    sf = f1_score(y, yp, zero_division=0)
    ok = np.allclose([p, r, f], [sp, sr, sf], atol=1e-12)
    all_ok &= ok
    print(f"  {name:<8} P {p:.6f} | {sp:.6f}   R {r:.6f} | {sr:.6f}   F1 {f:.6f} | {sf:.6f}   -> {'MATCH' if ok else 'DIFFERENT'}")
assert all_ok, "own metrics differ from scikit-learn"
print("\nAll metrics match scikit-learn.")

# save results
with open(f"{C.RESULTS}/level2_metrics.csv", "w") as fh:
    fh.write("type,precision,recall,f1,TP,FP,FN\n")
    for r in rows:
        fh.write(",".join([r[0]] + [f"{v:.6f}" for v in r[1:4]] + [str(v) for v in r[4:]]) + "\n")

# plot
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

t = np.arange(len(pred)) / 60
fig, ax = plt.subplots(figsize=(16, 5))
ax.plot(t, d["hr"], lw=0.5, color="steelblue")
colors = {"spike": "red", "dropout": "black", "drift": "orange"}
for k, s, l in d["events"]:
    ax.axvspan(s / 60, (s + l) / 60, color=colors[k], alpha=0.25)
w = d["walk"].astype(int)
edges = np.flatnonzero(np.diff(np.r_[0, w, 0]))
for a, b in zip(edges[::2], edges[1::2]):
    ax.axvspan(a / 60, b / 60, color="green", alpha=0.10)
idx = np.flatnonzero(pred)
ax.scatter(t[idx], d["hr"][idx], s=6, color="magenta", zorder=3, label="z-score flag")
ax.set_title(f"Level 2: rolling z-score (window {WINDOW} s)")
ax.set_xlabel("time (min)")
ax.set_ylabel("HR (bpm)")
ax.legend(loc="upper right")
plt.tight_layout()
plt.savefig(f"{C.RESULTS}/level2_flags.png", dpi=120)
