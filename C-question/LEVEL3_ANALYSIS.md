# Question C, Level 3: capacity and where the design breaks

> DRAFT: I (the AI) wrote the first version from your measured numbers. Rewrite the
> reasoning in your own words and be ready to redo any calculation live.
> Reproduce the numbers with `python question_C/capacity_calc.py` and
> `python question_C/benchmark_inserts.py`.

## 1. Calculation for 1,000 users (step by step)

| Step | Calculation | Result |
|---|---|---|
| Rows per day | 1,000 users x 86,400 s | **86,400,000** |
| Writes per second | 1,000 users x 1 reading/s | **1,000 writes/s** |
| Rows per month | 86,400,000 x 30 | 2,592,000,000 |
| Bytes per row | user_id 4 + ts 4 + hr 2 + acc 4 = 14 payload, + 18 row overhead = 32, x 1.15 for page fill | ~36.8 B |
| Storage per month | 2,592,000,000 x 36.8 B | **~95 GB** |

Cross-checks: the payload alone is 36 GB. My SQLite table measured 51.2 bytes per row
(text timestamp), which gives ~133 GB. So the answer is "roughly 100 GB per month".
Alerts add about 264,000 rows/day (22 alerts per 2 h per user, measured), around 21 MB/day, which is negligible.

## 2. Same arithmetic at 100,000 users

Everything scales linearly (x100): **8.64 billion rows/day, 100,000 writes/s, ~9.5 TB/month**
(about 29 TB/month with 3 replicas).

## 3. Where the design breaks first at 100,000 users

I measured three things on my machine:

| Measurement | Result | Needed at 100,000 users |
|---|---|---|
| One commit per reading | ~1,400 rows/s | 100,000/s: **70x short** (only 1.4x headroom even at 1,000 users) |
| Batches of 1,000 rows | ~430,000 rows/s (one SQLite writer) | 100,000/s: fine in the lab |
| Rolling z-score detector | ~209,000 readings/s per CPU core | ~0.5 core: not the problem |

**First break: the write path** (one request and one commit per reading). At 1,000 users it works with
almost no headroom; at 100,000 users it is 70x too slow, and 100,000 HTTP requests per second
would also overload the ingestion API.

**Second break: storage and query size.** 9.5 TB per month in one table makes backups,
indexes and dashboard queries slow, even after batching removes the write problem.

The detector is not the bottleneck: it uses about half a core, and its state (60 readings per user,
~48 MB for 100,000 users) fits in memory.

## 4. What I would change, and why

1. **Devices send a batch every 10 s** instead of one request per second. Requests drop from 100,000/s to 10,000/s.
2. **Message queue partitioned by user_id** in front of everything. It absorbs bursts and lets detection and storage consume independently.
3. **Batched inserts** (about 1,000 rows per commit). My benchmark showed ~300x more rows/s than one commit per reading.
4. **Time-series storage partitioned by day** (for example TimescaleDB or ClickHouse). Old days can be dropped or compressed cheaply, and dashboards only touch recent partitions.
5. **Retention and roll-ups:** keep raw readings for about 30 days, then keep 1-minute averages. That is 60x fewer rows.
6. **Detection workers sharded by user_id** reading from the queue, not by querying the database every second.
