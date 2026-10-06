# Question D, Level 3: prediction (written BEFORE measuring any delay)

> DRAFT: rewrite this in your own words, then `git commit` it BEFORE you run
> `level3_measure_delay.py`. The commit timestamp is your proof.

**Question:** From the moment an anomaly starts, how long until my system raises the alert,
and where does that time go?

## Prediction

1. **Every spike and drop-out will alert within 5 s.** Average delay about **1.4 s**, worst case
   **2 s** (at most 3 s).
   - Spike: 1 s (the alert needs 2 consecutive readings beyond 3 sigma; the first one is the start).
   - Drop-out that reads zero: 1 s (same two-reading rule).
   - Drop-out that holds the last value: 2 s (the flat rule needs 4 identical readings, and the
     last normal reading is already the first of them).
2. **The pipeline itself is small:** engine polling every 0.2 s plus the database write should add
   about **0.1 to 0.3 s** between the triggering reading arriving and the alert row existing.
3. **Main source of delay: the confirmation rule** (waiting for 2 readings, or 4 identical ones),
   not the software pipeline. The sensor only gives 1 reading per second, so every confirmation
   reading costs a full second.
4. **One change that would cut it:** a fast path that alerts on a single reading when the evidence is
   overwhelming (reading is 0, or |z| above 10). A spike is +42 bpm or more, which is about
   z = 30, so spike and zero drop-out delay should fall from 1 s to about 0 s. The hold-last
   drop-out would still need repeated identical readings, so the worst case stays at 2 s.

## What would prove me wrong

- If the average is above 2 s or any event exceeds 5 s, my confirmation reasoning is wrong.
- If pipeline latency is larger than about 0.5 s, the pipeline (not the confirmation rule)
  is the main source of delay.
