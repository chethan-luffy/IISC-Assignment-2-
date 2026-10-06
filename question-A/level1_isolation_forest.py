"""
Question A, Level 1: Isolation Forest (any library allowed)

Run:  python question_A/level1_isolation_forest.py

Reports precision / recall / F1 per anomaly type and the number of false
alarms during walking. Seed S = 2504 everywhere.
"""
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.ensemble import IsolationForest
from sklearn.metrics import precision_recall_fscore_support

import common as C
from features import build_features

FINAL_CONTAMINATION = 0.05


def sk_prf(y, yp):
    p, r, f, _ = precision_recall_fscore_support(y, yp, average="binary", zero_division=0)
    return p, r, f


d = C.load()
X = build_features(d["hr"], d["acc"])
Xv = X.to_numpy()


def run(contamination):
    # Unsupervised: labels are NOT used for fitting.
    model = IsolationForest(n_estimators=200, contamination=contamination, random_state=C.S)
    model.fit(Xv)
    pred = (model.predict(Xv) == -1).astype(int)
    return model, pred


# ---- sweep (for transparency: it uses labels only to REPORT, not to fit) ----
print("Contamination sweep (labels used only for scoring):")
print(f"{'contam':>7}{'flagged':>9}{'walkFA_s':>10}{'spikeR':>8}{'dropR':>8}{'driftR':>8}{'F1 all':>8}")
sweep = []
for c in [0.03, 0.05, 0.08, 0.10, 0.15]:
    _, p = run(c)
    wfa, _ = C.walking_false_alarms(p, d["walk"])
    rec = {t: C.type_recall(d["events"], p, t)[0] for t in C.TYPES}
    f1 = sk_prf(d["label"], p)[2]
    sweep.append((c, int(p.sum()), wfa, rec["spike"], rec["dropout"], rec["drift"], f1))
    print(f"{c:>7.2f}{p.sum():>9d}{wfa:>10d}{rec['spike']:>8.2f}{rec['dropout']:>8.2f}{rec['drift']:>8.2f}{f1:>8.3f}")
pd.DataFrame(sweep, columns=["contamination", "flagged", "walking_FA_seconds", "recall_spike",
                             "recall_dropout", "recall_drift", "F1_overall"]).to_csv(
    f"{C.RESULTS}/level1_contamination_sweep.csv", index=False)

# ---- final model ----
model, pred = run(FINAL_CONTAMINATION)
score = -model.score_samples(Xv)  # higher = more abnormal
print(f"\nFINAL: contamination={FINAL_CONTAMINATION}, n_estimators=200, random_state={C.S}")

rows = C.per_type_table(d["atype"], d["label"], pred, sk_prf)
print("\nPer-type metrics (a type is scored against normal rows only):")
C.print_table(rows)
pd.DataFrame(rows, columns=["type", "precision", "recall", "f1", "TP", "FP", "FN"]).to_csv(
    f"{C.RESULTS}/level1_metrics.csv", index=False)

wfa_s, wfa_b = C.walking_false_alarms(pred, d["walk"])
print(f"\nFalse alarms during walking: {wfa_s} seconds in {wfa_b} bursts "
      f"(walking = {int(d['walk'].sum())} s)")

print("\nEvent-level view (an event counts as found if at least one second is flagged):")
for t in C.TYPES:
    sec, evt = C.type_recall(d["events"], pred, t)
    n_ev = sum(1 for e in d["events"] if e[0] == t)
    print(f"  {t:<8} events found {round(evt * n_ev)}/{n_ev}   second-level recall {sec:.2f}")

pd.DataFrame({"idx": np.arange(len(pred)), "score": score, "flag": pred}).to_csv(
    f"{C.RESULTS}/level1_predictions.csv", index=False)

# ---- plot ----
t = np.arange(len(pred)) / 60
fig, ax = plt.subplots(2, 1, figsize=(16, 7), sharex=True, gridspec_kw={"height_ratios": [3, 1]})
ax[0].plot(t, d["hr"], lw=0.5, color="steelblue")
colors = {"spike": "red", "dropout": "black", "drift": "orange"}
for k, s, l in d["events"]:
    ax[0].axvspan(s / 60, (s + l) / 60, color=colors[k], alpha=0.25)
w = d["walk"].astype(int)
edges = np.flatnonzero(np.diff(np.r_[0, w, 0]))
for a, b in zip(edges[::2], edges[1::2]):
    ax[0].axvspan(a / 60, b / 60, color="green", alpha=0.10)
idx = np.flatnonzero(pred)
ax[0].scatter(t[idx], d["hr"][idx], s=6, color="magenta", zorder=3, label="Isolation Forest flag")
ax[0].set_ylabel("HR (bpm)")
ax[0].set_title("Level 1: Isolation Forest flags (shaded: red spike, black drop-out, orange drift, green walking)")
ax[0].legend(loc="upper right")
ax[1].plot(t, score, lw=0.5, color="gray")
ax[1].axhline(np.sort(score)[-int(FINAL_CONTAMINATION * len(score))], color="magenta", ls="--", lw=0.8)
ax[1].set_ylabel("anomaly score")
ax[1].set_xlabel("time (min)")
plt.tight_layout()
plt.savefig(f"{C.RESULTS}/level1_flags.png", dpi=120)
print(f"\nSaved results to {C.RESULTS}")
