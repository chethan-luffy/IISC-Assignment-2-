# Question A, Level 3: prediction (written BEFORE running the experiment)

> DRAFT: rewrite this in your own words, then `git commit` it BEFORE you run
> `level3_reasoning.py`. The commit timestamp is your proof.

**Question:** What happens to the recall for *silent drift* if I double the
window size of the rolling z-score detector (60 s -> 120 s)?

## Prediction

Recall for silent drift will stay very low (below 5 %) at both window sizes.
Doubling the window will **not** help. If it changes at all, it will go
**slightly down** (by less than 3 percentage points).

## Reasoning (from the method's own logic)

- The detector compares each reading with the mean and standard deviation of
  the previous W resting readings: z = (x - mean) / std.
- A silent drift is a slow ramp: 15 bpm over 300 s, so slope m = 0.05 bpm/s.
- The trailing mean lags the ramp by about m*W/2. For W = 60 that is only
  about 1.5 bpm, and for W = 120 about 3 bpm.
- The window also *contains* the ramp, so the std grows too:
  std = sqrt(sigma^2 + (m*W)^2 / 12). Mathematically, for a noise-free ramp
  z can never exceed sqrt(3) = 1.73 however long the window is, which is
  below my threshold of 3.
- So only a lucky noise excursion could trigger an alert. A longer window
  needs a *bigger* excursion (std is larger), so recall should not improve.
- The drift is hidden because the detector adapts to it: it is the "boiling
  frog" weakness of any rolling-baseline method.

## What would prove me wrong

If drift recall at W = 120 is clearly higher than at W = 60 (more than 5
percentage points), my reasoning about the std inflation is wrong.
