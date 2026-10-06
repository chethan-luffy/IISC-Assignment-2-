"""
Question D, Level 2: check my alert logic against the two requirements on the real recording.
Run:  python question_D/level2_verify.py
"""
import statistics
from evaluate import load_recording, run_offline, match, duplicates_within

ts, hr, acc, events = load_recording()
alerts, eng = run_offline(ts, hr, acc)            # default engine: confirm=2, flat_len=4, cooldown 60 s
rows, extra = match(events, alerts, ts)

print(f"Recording: {len(hr):,} readings, {sum(1 for e in events if e[0] in ('spike', 'dropout'))} spike/drop-out events\n")
print(f"{'type':<9}{'start':>7}{'length':>8}{'alert delay (s)':>17}")
for r in rows:
    d = "MISSED" if r["delay_s"] is None else f"{r['delay_s']:.0f}"
    print(f"{r['type']:<9}{r['start_idx']:>7}{r['length_s']:>8}{d:>17}")

found = [r["delay_s"] for r in rows if r["delay_s"] is not None]
print("\nRequirement 1: alert within 5 s of the event starting")
print(f"  events alerted: {len(found)}/{len(rows)}   average delay {statistics.mean(found):.2f} s   worst {max(found):.0f} s"
      f"   -> {'PASS' if len(found) == len(rows) and max(found) <= 5 else 'FAIL'}")

dups = duplicates_within(alerts, 60)
per_event = {}
for r in rows:
    if r["alert"]:
        per_event[r["start_idx"]] = sum(1 for i, a in alerts if r["start_idx"] <= i < r["start_idx"] + r["length_s"] and a.alert_type == r["alert"].alert_type)
print("\nRequirement 2: no repeat alert for the same event within 60 s")
print(f"  same-type alerts closer than 60 s: {dups}   most alerts inside one event: {max(per_event.values())}"
      f"   candidates blocked by the cooldown: {eng.suppressed}   -> {'PASS' if dups == 0 else 'FAIL'}")

print(f"\nOther alerts (not matched to a spike/drop-out event): {len(extra)}")
kinds = {(e[0], e[1], e[2]) for e in events}
for i, a in extra:
    inside = next((f"{k} event at {s}" for k, s, l in events if s <= i < s + l), "no labelled event")
    print(f"  t={i:>5}  {a.alert_type:<8} -> {inside}")
