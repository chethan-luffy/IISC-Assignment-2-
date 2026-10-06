"""
question_A/common.py
Shared helpers for Question A. NumPy only (so Level 2 can import it legally).

S = 2504 (last four digits of USN 1DA25SCS04) is used as the seed everywhere.
"""
import os
import numpy as np

S = 2504
HERE = os.path.dirname(os.path.abspath(__file__))
SETUP = os.path.join(HERE, "..", "setup")
RESULTS = os.path.join(HERE, "results")
os.makedirs(RESULTS, exist_ok=True)
TYPES = ["spike", "dropout", "drift"]


def _read(name):
    return np.genfromtxt(os.path.join(SETUP, name), delimiter=",", names=True,
                         dtype=None, encoding="utf-8")


def load():
    """Load readings, ground-truth events and the walking mask (NumPy only)."""
    d = _read("readings.csv")
    ev = _read("anomaly_events.csv")
    wk = _read("walking_periods.csv")
    n = len(d)
    walk = np.zeros(n, dtype=bool)
    for s, l in zip(wk["start_idx"], wk["length_s"]):
        walk[s:s + l] = True
    events = [(str(t), int(s), int(l)) for t, s, l in zip(ev["anomaly_type"], ev["start_idx"], ev["length_s"])]
    return {
        "hr": d["hr"].astype(float),
        "acc": d["acc"].astype(float),
        "label": d["label"].astype(int),
        "atype": d["anomaly_type"].astype(str),
        "events": events,
        "walk": walk,
    }


def type_subset(atype, t):
    """Rows used to score one anomaly type: that type + all normal rows.
    Rows belonging to the *other* anomaly types are left out."""
    return (atype == t) | (atype == "none")


def count_bursts(mask):
    """Number of contiguous runs of True."""
    m = mask.astype(int)
    return int(((m[1:] == 1) & (m[:-1] == 0)).sum() + (m[0] == 1))


def per_type_table(atype, label, pred, prf):
    """Rows: overall + each type. prf(y_true, y_pred) -> (precision, recall, f1)."""
    rows = []
    p, r, f = prf(label, pred.astype(int))
    rows.append(("overall", p, r, f, int(((pred == 1) & (label == 1)).sum()),
                 int(((pred == 1) & (label == 0)).sum()), int(((pred == 0) & (label == 1)).sum())))
    for t in TYPES:
        m = type_subset(atype, t)
        y = (atype[m] == t).astype(int)
        yp = pred[m].astype(int)
        p, r, f = prf(y, yp)
        rows.append((t, p, r, f, int(((yp == 1) & (y == 1)).sum()),
                     int(((yp == 1) & (y == 0)).sum()), int(((yp == 0) & (y == 1)).sum())))
    return rows


def print_table(rows):
    print(f"{'type':<9}{'precision':>10}{'recall':>9}{'F1':>8}{'TP':>7}{'FP':>7}{'FN':>7}")
    for t, p, r, f, tp, fp, fn in rows:
        print(f"{t:<9}{p:>10.3f}{r:>9.3f}{f:>8.3f}{tp:>7d}{fp:>7d}{fn:>7d}")


def event_table(events, pred):
    """Per event: seconds flagged, second-level recall, detected?, delay (s) to first flag."""
    out = []
    for t, s, l in events:
        seg = pred[s:s + l].astype(bool)
        hit = bool(seg.any())
        out.append({
            "type": t, "start": s, "length": l,
            "flagged_s": int(seg.sum()), "recall": float(seg.mean()),
            "detected": hit, "delay_s": int(np.argmax(seg)) if hit else None,
        })
    return out


def walking_false_alarms(pred, walk):
    fa = pred.astype(bool) & walk
    return int(fa.sum()), count_bursts(fa)


def type_recall(events, pred, t):
    """Second-level and event-level recall for one anomaly type."""
    ev = [e for e in event_table(events, pred) if e["type"] == t]
    sec = sum(e["flagged_s"] for e in ev) / sum(e["length"] for e in ev)
    evt = sum(e["detected"] for e in ev) / len(ev)
    return sec, evt
