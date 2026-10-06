# AI-Driven Anomaly Detection and Monitoring System

M.Tech (CSE) technical assignment: detecting and explaining abnormal patterns in wearable sensor data.

| | |
|---|---|
| **Candidate** | `Chethan Prasad L` |
| **USN** | `1DA25SCS04` |
| **Seed S** | **2504** (last four digits of the USN, used everywhere) |
| **Questions answered** | **A** (Detect), **C** (Design), **D** (Live dashboard), each with Levels 1 to 3 |
| **Demo video** | ` https://drive.google.com/drive/folders/1vOo0cp-5V4jL-YCoTPday38jbvPbHqk5` |
| **Personal intelligence note** | [PERSONAL_INTELLIGENCE.md](PERSONAL_INTELLIGENCE.md) (decision log and AI usage declaration) |

---

## 1. What this project does

A wearable records **heart rate (HR)** and **movement (acc)** once per second. The system must flag three kinds of abnormal readings but **must not flag walking**, which raises HR by 20 to 30 bpm and is normal.

| Anomaly | Description |
|---|---|
| **Spike** | HR jumps by more than 40 bpm for 3 to 10 s with no movement |
| **Drop-out** | The sensor reads zero or a frozen value for 10 to 30 s |
| **Silent drift** | HR climbs 15 bpm over 5 minutes with no movement |

The work is split into a common dataset generator and three questions:

```
setup/generate_data.py  ->  readings.csv  (7,200 rows, 20 labelled anomalies)
        |
        +-- Question A: detect anomalies (Isolation Forest, rolling z-score from scratch)
        +-- Question C: design the system for 1,000 users (architecture, SQL, capacity)
        +-- Question D: live pipeline (producer, alert engine, dashboard) with measured delay
```

## 2. Results at a glance

| Question | Key results (seed 2504) |
|---|---|
| **A, Level 1** Isolation Forest | Spike recall 1.00, drop-out recall 0.88, silent drift recall 0.03; only 10 false-alarm seconds in 1,067 walking seconds |
| **A, Level 2** rolling z-score (NumPy only) | Spike recall 0.87, drop-out recall 0.93, **0 walking false alarms**; own precision/recall/F1 match scikit-learn to 1e-12 |
| **A, Level 3** window experiment | Drift recall 0.17 % at 60 s and 0.06 % at 120 s: a rolling baseline adapts to a slow drift (prediction held) |
| **C** system design | 1,000 users = 86.4 million rows/day, 1,000 writes/s, about 95 GB/month; at 100,000 users the write path (one commit per reading) breaks first |
| **D** live alerts | 14 of 14 spike/drop-out events alerted; average 1.34 s, worst 2.17 s from event start; main source is the confirmation rule (about 91 %) |

## 3. Repository structure

```
.
├── README.md                     this file
├── PERSONAL_INTELLIGENCE.md      decision log + AI usage declaration
├── requirements.txt
├── .gitignore
│
├── setup/                        common dataset (required by every question)
│   ├── generate_data.py          creates the personal dataset from seed S
│   ├── readings.csv              timestamp, hr, acc, label, anomaly_type (7,200 rows)
│   ├── signal_plot.png           full signal with anomalies marked
│   ├── anomaly_events.csv        ground-truth list of the 20 anomalies
│   └── walking_periods.csv       ground-truth walking periods (normal)
│
├── question_A/                   Detect the abnormal readings
│   ├── common.py, features.py
│   ├── level1_isolation_forest.py
│   ├── my_metrics.py, zscore_detector.py, level2_rolling_zscore.py
│   ├── PREDICTION.md, level3_reasoning.py
│   └── results/                  tables and plots
│
├── question_C/                   Design the full system
│   ├── architecture.png, draw_architecture.py
│   ├── schema.sql, queries.sql, level2_load_and_query.py
│   ├── capacity_calc.py, benchmark_inserts.py, LEVEL3_ANALYSIS.md
│   └── results/
│
└── question_D/                   Live dashboard with alerts
    ├── schema.sql, db.py
    ├── producer.py, alert_engine.py, dashboard.py
    ├── test_alert_engine.py, evaluate.py, level2_verify.py
    ├── PREDICTION.md, level3_measure_delay.py
    └── results/
```

## 4. Setup

**Requirements:** Python 3.9 or newer.

```bash
git clone <this-repository-url>
cd <repository-folder>

python -m venv .venv
source .venv/bin/activate            # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**Always run commands from the repository root.** The scripts find the data through `setup/` by their own location, and Question C and D reuse code from sibling folders.

### Regenerate the dataset (optional)

`setup/readings.csv` is already included. Running the generator again gives identical output because the seed is fixed.

```bash
python setup/generate_data.py
```

It writes `readings.csv`, `signal_plot.png`, `anomaly_events.csv` and `walking_periods.csv`.

## 5. Question A: Detect the abnormal readings

Goal: find spikes, drop-outs and silent drifts without flagging walking.

**Level 1 (Build).** Isolation Forest on movement-aware window features (1-second HR change, run of identical readings, HR minus HR explained by movement, and its 60 s rolling mean). Reports precision, recall and F1 per anomaly type and the false alarms during walking.

**Level 2 (Code it yourself).** A rolling z-score detector in **NumPy only** (circular buffer with running sums; walking gate; flat-sensor rule; two consecutive breaches), plus my own precision/recall/F1 function that is checked against scikit-learn.

**Level 3 (Reason).** Prediction written first: doubling the window (60 s to 120 s) will not improve silent-drift recall. Then the experiment, a window sweep, and plots of one anomaly each method missed.

```bash
python question_A/level1_isolation_forest.py
python question_A/level2_rolling_zscore.py

# Level 3: commit your prediction BEFORE running the experiment
git add question_A/PREDICTION.md
git commit -m "Question A Level 3 prediction (before running)"
git push
python question_A/level3_reasoning.py
```

Outputs are saved in `question_A/results/`. See `question_A/README.md` for details.

## 6. Question C: Design the full system

Goal: design the system for 1,000 users sending one reading per second.

**Level 1.** `architecture.png` (device, ingestion, queue, DB writer, database, detection, alerts, dashboard) and `schema.sql` (users, readings, alerts).

**Level 2.** Loads `readings.csv` into SQLite as three users (clock offsets 0, +45 min, -26 h), creates alerts with the Question A detector, and runs three hand-written queries: alerts per user in the last 24 hours, users with more than five alerts in any one hour, and average heart rate per user per hour.

**Level 3.** Step-by-step capacity arithmetic, a measured insert benchmark, and where the design breaks at 100,000 users.

```bash
python question_C/draw_architecture.py
python question_C/level2_load_and_query.py     # builds question_C/wearables.db, prints the query outputs
python question_C/capacity_calc.py
python question_C/benchmark_inserts.py
```

Query outputs are saved in `question_C/results/level2_query_outputs.txt`. The reasoning is in `question_C/LEVEL3_ANALYSIS.md`. Question C imports the detector from `question_A/zscore_detector.py`.

## 7. Question D: Live dashboard with alerts

Goal: a live pipeline where an alert fires within 5 seconds of a spike or drop-out starting, the same event never alerts twice within 60 seconds, and a dashboard shows the signal and the alerts.

```
readings.csv -> producer.py -> SQLite (readings) -> alert_engine.py -> SQLite (alerts) -> dashboard.py
```

**Level 1.** `dashboard.py`: Streamlit dashboard that reads from SQL, plots HR and movement, marks alerts and optionally shades the true anomalies.

**Level 2.** `producer.py` replays the CSV at one row per second. `alert_engine.py` is my own streaming alert logic (5 s requirement, 60 s cooldown, walking ignored). `test_alert_engine.py` and `level2_verify.py` prove both requirements.

**Level 3.** `level3_measure_delay.py` measures the delay for all 14 spike and drop-out events and splits it into detection delay and pipeline latency.

### Run the live demo (three terminals, from the repository root)

```bash
# Terminal 1: producer (creates the database; --speed 20 replays 20x faster for a quick look)
python question_D/producer.py --reset

# Terminal 2: alert engine
python question_D/alert_engine.py

# Terminal 3: dashboard (opens in the browser and refreshes by itself)
streamlit run question_D/dashboard.py
```

Start the producer first, and do not use `--reset` while the engine is running.

### Checks and Level 3 measurement

```bash
python question_D/test_alert_engine.py        # 7 unit tests
python question_D/level2_verify.py            # both requirements on the real recording

# Level 3: commit your prediction BEFORE running the measurement
git add question_D/PREDICTION.md
git commit -m "Question D Level 3 prediction (before running)"
git push
python question_D/level3_measure_delay.py               # 10x replay speed, about 2 minutes
python question_D/level3_measure_delay.py --speed 1     # real time, about 20 minutes
```

Outputs are saved in `question_D/results/` (`level3_delay_table.csv`, `level3_delay.png`). See `question_D/README.md` for details.

## 8. Reproducibility

- Every random choice uses the seed **S = 2504** (`numpy.random.default_rng(2504)` in the generator, `random_state=2504` in models), so data and results repeat exactly.
- The only values that vary between runs and machines are wall-clock timings (insert throughput and pipeline latency).

## 9. Troubleshooting

| Problem | Fix |
|---|---|
| `ModuleNotFoundError` or file not found | Run from the repository root; check that `setup/`, `question_A/`, `question_C/` and `question_D/` are side by side |
| `streamlit: command not found` or `st.fragment` error | `pip install -U "streamlit>=1.37"` |
| `disk I/O error` or `database is locked` | Keep the project on a normal local disk (not a synced or network folder); stop other programs using `live.db` |
| Dashboard says "No data yet" | Start the producer first; check the database path in the sidebar |
| Port already in use | `streamlit run question_D/dashboard.py --server.port 8502` |
| `python` not found on macOS or Linux | Use `python3` |

## 10. Known limitations

- **Silent drift is essentially undetected** by both methods (recall 3 % for Isolation Forest, 0.2 % for the z-score). I explain why in Question A Level 3 but did not build a detector that solves it. A trend method such as CUSUM would be the next step.
- Isolation Forest's contamination (0.05) was chosen from a sweep scored with the labels, so its Level 1 numbers are slightly optimistic.
- The z-score raises false alarms for about 15 s after each drift ends (HR snaps back).
- The data is synthetic, and the three users in Question C share one signal with different clock offsets.
- Question B was not attempted.

## 11. AI usage and credits

AI tools were used as described in [PERSONAL_INTELLIGENCE.md](PERSONAL_INTELLIGENCE.md), including one place where the AI was wrong and how it was found and fixed.

**Libraries used:** numpy, pandas, matplotlib, scikit-learn (`IsolationForest`, metrics), streamlit, plotly, and the Python standard library (`sqlite3`, `csv`, `threading`, `datetime`).

## 12. Submission

Submitted to `mnaveennk@iisc.ac.in` before 5:00 PM IST on 6 October 2026 with this repository link and the demo video link.
