"""
question_A/features.py   (Level 1 only: pandas / scikit-learn are allowed here)

Per-second features for Isolation Forest. Walking must NOT look abnormal, so
heart rate is expressed relative to what movement explains.

d1        1-second change in HR                    -> spikes, drop-outs to zero
flat_run  how many readings in a row are identical -> flat (stuck) sensor
resid     HR minus HR explained by movement        -> removes the walking rise
resid_m60 60 s rolling mean of resid               -> slow upward drift
"""
import numpy as np
import pandas as pd


def build_features(hr, acc):
    hr = pd.Series(hr)
    acc_s = pd.Series(acc).rolling(5, min_periods=1).mean()

    f = pd.DataFrame(index=hr.index)
    f["d1"] = hr.diff().fillna(0.0)

    same = (hr.diff() == 0).to_numpy()
    run = np.zeros(len(hr))
    for i in range(1, len(hr)):
        run[i] = run[i - 1] + 1 if same[i] else 0
    f["flat_run"] = run

    # linear model: HR ~ smoothed movement. Residual = HR not explained by walking.
    slope, intercept = np.polyfit(acc_s, hr, 1)
    f["resid"] = hr - (slope * acc_s + intercept)
    f["resid_m60"] = f["resid"].rolling(60, min_periods=1).mean()
    return f
