# Question C: Design the full system

Seed **S = 2504**. Needs the repo layout `setup/` + `question_A/` + `question_C/` side by side
(Level 2 imports the detector from `question_A/zscore_detector.py`).

## Run

```bash
pip install numpy pandas matplotlib
python question_C/draw_architecture.py        # Level 1: architecture.png
python question_C/level2_load_and_query.py    # Level 2: builds wearables.db, runs queries.sql
python question_C/capacity_calc.py            # Level 3: step-by-step arithmetic
python question_C/benchmark_inserts.py        # Level 3: measured write throughput
```

## Files

| File | Level | Notes |
|---|---|---|
| `architecture.png`, `draw_architecture.py` | 1 | device, ingestion, queue, DB writer, database, detection, alerts, dashboard |
| `schema.sql` | 1 | users, readings, alerts + indexes (runs in SQLite) |
| `queries.sql` | 2 | three hand-written queries |
| `level2_load_and_query.py` | 2 | loads 3 users (offsets 0, +45 min, -26 h), raises alerts, runs the queries |
| `results/level2_query_outputs.txt` | 2 | the query outputs |
| `capacity_calc.py`, `benchmark_inserts.py` | 3 | calculations and measured evidence |
| `LEVEL3_ANALYSIS.md` | 3 | reasoning: where it breaks at 100,000 users |

`wearables.db` is generated and ignored by git; rebuild it with the Level 2 script.

## Libraries used

numpy, pandas, matplotlib, sqlite3 (standard library).
