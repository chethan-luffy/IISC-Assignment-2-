"""
setup/generate_data.py
Generates a personal 2-hour wearable recording (1 reading/second, 7,200 rows).

Seed S = last four digits of USN 1DA25SCS04 -> 2504
Run:  python setup/generate_data.py
Outputs (in the same folder as this script):
    readings.csv          timestamp, hr, acc, label, anomaly_type
    signal_plot.png       full signal with anomalies marked
    walking_periods.csv   ground truth for walking (normal) periods
    anomaly_events.csv    ground truth list of the 20 anomaly events
"""
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

S = 2504
N = 7200
OUT = os.path.dirname(os.path.abspath(__file__))
rng = np.random.default_rng(S)

t = np.arange(N)
timestamps = pd.date_range("2026-10-06 09:00:00", periods=N, freq="s")

# ---------------------------------------------------------------- heart rate
rest = 60 + (S % 20)
phase = rng.uniform(0, 2 * np.pi, 2)
drift = 2.5 * np.sin(2 * np.pi * t / 5400 + phase[0]) + 1.0 * np.sin(2 * np.pi * t / 1700 + phase[1])
breathing = 1.2 * np.sin(2 * np.pi * t / 5.0)          # ~12 breaths/min
noise = rng.normal(0, 1.0, N)
hr = rest + drift + breathing + noise

# ------------------------------------------------------------------ movement
acc = 0.05 + np.abs(rng.normal(0, 0.03, N))             # mostly low

occupied = np.zeros(N, dtype=bool)   # seconds already used (walking / anomalies / guard gaps)
GUARD = 60


def reserve(start, length):
    occupied[max(0, start - GUARD): min(N, start + length + GUARD)] = True


def free(start, length):
    return start >= GUARD and start + length + GUARD < N and not occupied[start - GUARD: start + length + GUARD].any()


def place(length):
    for _ in range(10000):
        start = int(rng.integers(GUARD, N - length - GUARD))
        if free(start, length):
            reserve(start, length)
            return start
    raise RuntimeError("could not place event; change seed handling")


# three walking periods, 5-10 minutes each
walks = []
for _ in range(3):
    length = int(rng.integers(300, 601))
    start = place(length)
    walks.append((start, length))
    seg = slice(start, start + length)
    step = np.sin(2 * np.pi * np.arange(length) / 2.0)   # step rhythm
    acc[seg] = 1.0 + 0.25 * step + rng.normal(0, 0.1, length)
    rise = rng.uniform(20, 30)
    ramp = np.minimum(1, np.minimum(np.arange(length), length - np.arange(length)) / 20.0)
    hr[seg] += rise * ramp

# ---------------------------------------------------------------- anomalies
label = np.zeros(N, dtype=int)
atype = np.array(["none"] * N, dtype=object)
events = []

plan = ["spike"] * 8 + ["dropout"] * 6 + ["drift"] * 6      # 20 anomalies
order = rng.permutation(len(plan))
plan = [plan[i] for i in order]

# place long events first so they find room, then restore chronological order
plan.sort(key=lambda k: {"drift": 0, "dropout": 1, "spike": 2}[k])
for kind in plan:
    if kind == "spike":
        length = int(rng.integers(3, 11))
    elif kind == "dropout":
        length = int(rng.integers(10, 31))
    else:
        length = 300
    start = place(length)
    seg = slice(start, start + length)
    if kind == "spike":
        hr[seg] += rng.uniform(42, 60)                  # > 40 bpm jump
    elif kind == "dropout":
        if rng.random() < 0.5:
            hr[seg] = 0.0                                # reads zero
        else:
            hr[seg] = hr[start - 1]                      # flat at last value
    else:
        hr[seg] += np.linspace(0, 15, length)            # +15 bpm over 5 min
    label[seg] = 1
    atype[seg] = kind
    events.append((kind, start, length))

hr = np.clip(hr, 0, None)

df = pd.DataFrame({
    "timestamp": timestamps,
    "hr": np.round(hr, 2),
    "acc": np.round(acc, 3),
    "label": label,
    "anomaly_type": atype,
})
df.to_csv(os.path.join(OUT, "readings.csv"), index=False)

ev = pd.DataFrame(sorted(events, key=lambda e: e[1]), columns=["anomaly_type", "start_idx", "length_s"])
ev["start_time"] = timestamps[ev["start_idx"].values].astype(str)
ev.to_csv(os.path.join(OUT, "anomaly_events.csv"), index=False)

wk = pd.DataFrame(sorted(walks), columns=["start_idx", "length_s"])
wk["start_time"] = timestamps[wk["start_idx"].values].astype(str)
wk.to_csv(os.path.join(OUT, "walking_periods.csv"), index=False)

# --------------------------------------------------------------------- plot
colors = {"spike": "red", "dropout": "black", "drift": "orange"}
fig, (a1, a2) = plt.subplots(2, 1, figsize=(16, 7), sharex=True, gridspec_kw={"height_ratios": [3, 1]})
a1.plot(t / 60, hr, lw=0.6, color="steelblue")
a2.plot(t / 60, acc, lw=0.5, color="gray")
for s0, l in walks:
    for a in (a1, a2):
        a.axvspan(s0 / 60, (s0 + l) / 60, color="green", alpha=0.12)
for kind, s0, l in events:
    a1.axvspan(s0 / 60, (s0 + l) / 60, color=colors[kind], alpha=0.35)
handles = [plt.Line2D([0], [0], color=c, lw=6, alpha=0.5, label=k) for k, c in colors.items()]
handles.append(plt.Line2D([0], [0], color="green", lw=6, alpha=0.3, label="walking (normal)"))
a1.legend(handles=handles, loc="upper right")
a1.set_ylabel("Heart rate (bpm)")
a2.set_ylabel("Accel magnitude")
a2.set_xlabel("Time (minutes)")
a1.set_title(f"Wearable recording, seed S={S}: 20 labelled anomalies")
plt.tight_layout()
plt.savefig(os.path.join(OUT, "signal_plot.png"), dpi=130)

print(f"S={S}, resting HR level={rest}, rows={len(df)}")
print(ev["anomaly_type"].value_counts().to_dict(), "| anomalous seconds:", int(label.sum()))
print("walking periods (start_s, length_s):", sorted(walks))
