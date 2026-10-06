"""
question_D/evaluate.py   run the alert engine over the whole recording and compare with ground truth.
Used by level2_verify.py and level3_measure_delay.py. Seed S = 2504 (data and engine are deterministic).
"""
import csv
import os
from datetime import datetime, timedelta

from alert_engine import StreamAlertEngine
from db import FMT

HERE = os.path.dirname(os.path.abspath(__file__))
SETUP = os.path.join(HERE, "..", "setup")
EXPECTED = {"spike": "spike", "dropout": "dropout"}     # ground-truth type -> alert type


def load_recording():
    ts, hr, acc = [], [], []
    with open(os.path.join(SETUP, "readings.csv")) as fh:
        for r in csv.DictReader(fh):
            ts.append(datetime.strptime(r["timestamp"], FMT))
            hr.append(float(r["hr"]))
            acc.append(float(r["acc"]))
    events = []
    with open(os.path.join(SETUP, "anomaly_events.csv")) as fh:
        for r in csv.DictReader(fh):
            events.append((r["anomaly_type"], int(r["start_idx"]), int(r["length_s"])))
    return ts, hr, acc, sorted(events, key=lambda e: e[1])


def run_offline(ts, hr, acc, **engine_kwargs):
    eng = StreamAlertEngine(**engine_kwargs)
    alerts = []
    for i in range(len(hr)):
        a = eng.update(ts[i], hr[i], acc[i])
        if a:
            alerts.append((i, a))
    return alerts, eng


def match(events, alerts, ts):
    """For every spike / drop-out event find its alert (type matches, raised during the event)."""
    rows, used = [], set()
    for kind, start, length in events:
        if kind not in EXPECTED:
            continue
        hit = None
        for k, (i, a) in enumerate(alerts):
            if a.alert_type == EXPECTED[kind] and start <= i < start + length and k not in used:
                hit = (k, i, a)
                break
        if hit:
            used.add(hit[0])
            rows.append({"type": kind, "start_idx": start, "length_s": length,
                         "delay_s": (hit[2].detected_ts - ts[start]).total_seconds(), "alert": hit[2]})
        else:
            rows.append({"type": kind, "start_idx": start, "length_s": length, "delay_s": None, "alert": None})
    extra = [(i, a) for k, (i, a) in enumerate(alerts) if k not in used]
    return rows, extra


def duplicates_within(alerts, seconds=60):
    """Pairs of same-type alerts closer than `seconds` (must be zero)."""
    bad = 0
    last = {}
    for _, a in alerts:
        t = last.get(a.alert_type)
        if t is not None and (a.detected_ts - t).total_seconds() < seconds:
            bad += 1
        last[a.alert_type] = a.detected_ts
    return bad
