"""
question_A/zscore_detector.py   (Level 2: NumPy only. No pandas rolling, no scikit-learn)

Rolling z-score detector, written as a one-pass streaming loop so the same
logic can be reused for the live alert engine in Question D.

Idea
  Keep the last `window` "normal resting" heart-rate readings in a circular
  buffer with running sum and running sum of squares:
        mean = sum / n          std = sqrt(sum_sq / n - mean^2)
  z = (hr - mean) / std. A reading is a breach when |z| > z_thresh, and it is
  flagged when `consecutive` breaches happen in a row (one noisy reading
  should not raise an alarm).

Three rules make walking "normal":
  1. Moving gate: if any acc in the last `acc_hold` seconds is above
     `acc_thresh`, the person is walking. No flag, and the baseline is NOT
     updated (walking heart rate must not pollute the resting baseline).
  2. Anomalous readings are not added to the baseline (a spike must not
     inflate the std). If a breach lasts longer than `max_breach` seconds
     (longer than any spike) it is a new level, so the baseline is reset.
  3. Flat rule: `flat_len` identical readings in a row means a stuck sensor
     (real readings are never exactly identical): flag it. A z-score alone
     cannot see a flat line that sits at a normal value.
"""
import numpy as np


def rolling_zscore_detector(hr, acc, window=60, z_thresh=3.0, consecutive=2,
                            min_samples=30, flat_len=4, acc_thresh=0.5,
                            acc_hold=3, max_breach=15, std_floor=0.5):
    hr = np.asarray(hr, dtype=float)
    acc = np.asarray(acc, dtype=float)
    n = len(hr)

    flags = np.zeros(n, dtype=bool)
    base_mean = np.full(n, np.nan)
    base_std = np.full(n, np.nan)

    buf = np.zeros(window)   # circular buffer of accepted readings
    count = 0                # readings currently in the buffer
    head = 0                 # next write position
    s1 = 0.0                 # running sum
    s2 = 0.0                 # running sum of squares
    streak = 0               # consecutive breaches
    breach_run = 0           # length of the current breach (for the reset rule)

    def push(x):
        nonlocal count, head, s1, s2
        if count == window:              # buffer full: drop the oldest value
            old = buf[head]
            s1 -= old
            s2 -= old * old
        else:
            count += 1
        buf[head] = x
        s1 += x
        s2 += x * x
        head = (head + 1) % window

    for i in range(n):
        # rule 1: walking gate
        if acc[max(0, i - acc_hold + 1): i + 1].max() > acc_thresh:
            streak = 0
            breach_run = 0
            continue

        # rule 3: flat line
        flat = i >= flat_len - 1 and np.ptp(hr[i - flat_len + 1: i + 1]) < 1e-9

        # z-score against the baseline built from earlier readings
        ready = count >= min_samples
        breach = False
        if ready:
            mean = s1 / count
            std = max(np.sqrt(max(s2 / count - mean * mean, 0.0)), std_floor)
            base_mean[i], base_std[i] = mean, std
            breach = abs((hr[i] - mean) / std) > z_thresh

        if breach:
            streak += 1
            breach_run += 1
        else:
            streak = 0
            breach_run = 0

        flags[i] = flat or (breach and streak >= consecutive)

        # rule 2: only normal readings update the baseline
        if not flat and not breach:
            push(hr[i])
        elif breach and breach_run > max_breach:
            count, head, s1, s2 = 0, 0, 0.0, 0.0   # new level: relearn the baseline
            push(hr[i])
            streak = 0
            breach_run = 0

    return flags, base_mean, base_std
