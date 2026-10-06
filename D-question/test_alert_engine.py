"""
question_D/test_alert_engine.py   unit tests for the two Level 2 requirements.
Run:  python question_D/test_alert_engine.py     (or: pytest question_D)
"""
from datetime import datetime, timedelta
import numpy as np
from alert_engine import StreamAlertEngine

T0 = datetime(2026, 10, 6, 9, 0, 0)


def make_signal(n=400, seed=2504):
    rng = np.random.default_rng(seed)
    hr = 70 + 1.2 * np.sin(2 * np.pi * np.arange(n) / 5) + rng.normal(0, 1.0, n)
    acc = 0.05 + np.abs(rng.normal(0, 0.03, n))
    return hr, acc


def run(hr, acc, **kw):
    eng = StreamAlertEngine(**kw)
    out = []
    for i in range(len(hr)):
        a = eng.update(T0 + timedelta(seconds=i), float(hr[i]), float(acc[i]))
        if a:
            out.append((i, a))
    return out, eng


def test_spike_alerts_within_5s():
    hr, acc = make_signal()
    hr[100:106] += 50                                    # 6 s spike starting at t=100
    alerts, _ = run(hr, acc)
    assert len(alerts) == 1 and alerts[0][1].alert_type == "spike"
    assert alerts[0][0] - 100 <= 5, "alert later than 5 s"


def test_zero_dropout_alerts_within_5s():
    hr, acc = make_signal()
    hr[100:120] = 0.0
    alerts, _ = run(hr, acc)
    assert len(alerts) == 1 and alerts[0][1].alert_type == "dropout"
    assert alerts[0][0] - 100 <= 5


def test_stuck_sensor_alerts_within_5s():
    hr, acc = make_signal()
    hr[100:120] = hr[99]                                 # holds the last value
    alerts, _ = run(hr, acc)
    assert len(alerts) == 1 and alerts[0][1].alert_type == "dropout"
    assert alerts[0][0] - 100 <= 5


def test_same_event_no_repeat_within_60s():
    hr, acc = make_signal()
    hr[100:104] += 50                                    # first spike
    hr[130:134] += 50                                    # same kind of event only 30 s later
    alerts, eng = run(hr, acc)
    assert len(alerts) == 1, "second spike inside 60 s must not alert again"
    assert eng.suppressed >= 1


def test_alert_again_after_60s():
    hr, acc = make_signal()
    hr[100:104] += 50
    hr[200:204] += 50                                    # 100 s later: a new event
    alerts, _ = run(hr, acc)
    assert [a.alert_type for _, a in alerts] == ["spike", "spike"]


def test_walking_is_not_an_alert():
    hr, acc = make_signal()
    hr[150:300] += np.linspace(0, 25, 150).clip(max=25)  # heart rate climbs while walking
    acc[150:300] = 1.0
    alerts, _ = run(hr, acc)
    assert alerts == []


def test_fast_path_alerts_on_first_reading():
    hr, acc = make_signal()
    hr[100:106] += 50
    alerts, _ = run(hr, acc, fast_z=10)
    assert alerts[0][0] == 100                           # 0 s delay


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"PASS  {t.__name__}")
    print(f"\nAll {len(tests)} tests passed.")
