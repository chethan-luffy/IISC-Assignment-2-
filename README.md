AI-Driven Anomaly Detection and
Monitoring System: Project Report
Chethan | USN 1DA25SCS04 | Seed S = 2504 | M.Tech (CSE) technical assignment, 6
October 2026
1. Purpose
The assignment asks for a system that finds abnormal patterns in wearable sensor data
(heart rate and movement, one reading per second) and explains or serves the results.
The hard part is deliberate: walking raises heart rate by 20 to 30 bpm and must NOT be
treated as an anomaly, while three real anomaly types must be caught: spikes, sensor
drop-outs and silent drifts.
I completed the common setup and three of the four questions: A (Detect), C (Design)
and D (Dashboard). Question B was dropped to keep each answer complete. Each
question has three levels: Build (any library), Code it yourself (named parts from scratch)
and Reason with your results (predict first, test, explain with my own numbers).
Why it matters: in health monitoring, a false alarm trains people to ignore the device and a
missed event can be dangerous. Every result below is therefore reported as precision
AND recall, per anomaly type, with false alarms during walking counted separately.
2. Project at a glance
Folder Contents
setup/ generate_data.py, readings.csv (7,200 rows),
signal_plot.png, anomaly_events.csv and
walking_periods.csv (ground truth)
question_A/ Isolation Forest (L1), NumPy-only rolling z-score
and own metrics (L2), prediction and window
experiment (L3), results/
question_C/ schema.sql, architecture.png, three SQL queries,
capacity calculation and benchmark,
LEVEL3_ANALYSIS.md
question_D/ Live dashboard, producer, alert engine, delay
measurement (planned, see section 6)
AI-Driven Anomaly Detection and Monitoring System: Project Report
Page 1 of 11
Data flow: generate_data.py makes readings.csv. Question A turns it into features and
detectors. Question C stores it in SQL and attaches alerts from the Question A detector.
Question D replays it live and reuses the same detector logic for alerts.
3. Common setup: my personal dataset
The seed S is the last four digits of the USN (2504) and is used in the data generator
(numpy default_rng) and in every model (random_state=2504). The resting heart rate
level is 60 + (2504 mod 20) = 64 bpm, so my numbers differ from other candidates.
Events are placed by rejection sampling so none overlap walking or each other, with at
least 60 s between them. In total 2,000 of the 7,200 seconds are anomalous (28 percent),
mostly because drifts last 300 s each. A drift ends with an abrupt return to baseline,
which matters later (section 4.3).
4. Question A: Detectthe abnormal readings
4.1 Key difficulty and approach
Raw heart rate cannot be used: walking looks like a huge anomaly. My first feature set
flagged 148 walking seconds out of only 360 alerts. The fix was to give the models
movement-aware features, so walking becomes the expected situation rather than an
outlier.
4.2 Level 1:Isolation Forest
Isolation Forest isolates points with random splits; points that are isolated in few splits
(short path) get a high anomaly score. It is unsupervised, so labels are never used for
fitting. Features (features.py):
Component How it is generated
Heart rate resting 64 + slow drift (two sine waves) + breathing
wave (period 5 s) + Gaussian noise
Movement (acc) about 0.05 at rest; about 1.0 while walking
Walking 3 periods (303 s, 319 s, 445 s); HR rises 20 to 30
bpm with a 20 s ramp; labelled normal
Anomalies 20 events: 8 spikes (+42 to +60 bpm for 3 to 10 s), 6
drop-outs (zero or stuck value for 10 to 30 s), 6
silent drifts (+15 bpm over 300 s)
AI-Driven Anomaly Detection and Monitoring System: Project Report
Page 2 of 11
d1: 1-second change in HR (catches spikes and zero drop-outs)
flat_run: how many identical readings in a row (catches a stuck sensor)
resid: HR minus the HR explained by smoothed movement (linear fit), which removes
the walking rise
resid_m60: 60 s rolling mean of resid (a slow drift shows up here)
Settings: 200 trees, contamination 0.05, random_state 2504. Results (a type is scored
against normal rows only):
Walking false alarms: 10 seconds in 8 bursts, out of 1,067 walking seconds. All 8 spikes and
6 drop-outs were found as events, and 5 of 6 drifts were touched, but almost every drift
second was missed.
Honest caveat: contamination was chosen from a small sweep (0.03 to 0.15) that used the
labels for scoring, so the Level 1 numbers are slightly optimistic. At 0.10 walking false
alarms rise to 57 and at 0.15 to 84.
4.3 Level 2: rolling z-score in NumPy only
zscore_detector.py is a one-pass streaming loop. It keeps the last W (60) normal resting
readings in a circular buffer with a running sum and running sum of squares, so mean and
std update in constant time. z = (hr - mean) / std, and a reading is flagged after two
consecutive readings with |z| above 3. Three rules make it work on this data:
1. Moving gate: if acc exceeded 0.5 in the last 3 s the person is walking, so nothing is
flagged and the baseline is not updated.
2. Anomalous readings are not added to the baseline, so a spike cannot inflate the std. If a
breach lasts longer than 15 s (longer than any spike) it is treated as a new level and the
baseline resets.
3. Flat rule: 4 identical readings in a row means a stuck sensor. A z-score cannot see a flat
line sitting at a normal value.
my_metrics.py computes precision, recall and F1 from the definitions (TP, FP, FN) with no
scikit-learn. level2_rolling_zscore.py then proves they match scikit-learn to 1e-12 for the
overall result and each type.
Type Precision Recall F1
Spike 0.348 1.000 0.516
Drop-out 0.506 0.883 0.644
Silent drift 0.330 0.032 0.059
AI-Driven Anomaly Detection and Monitoring System: Project Report
Page 3 of 11
Results at W = 60: spike P 0.379 R 0.873; drop-out P 0.587 R 0.934; drift P 0.032 R 0.002;
walking false alarms 0. Spikes and drop-outs were detected within about 1 to 1.5 s on
average. The 90 remaining false alarms are exactly 6 drifts x 15 s: when a drift ends, HR
snaps back about 15 bpm, the detector flags it, and it takes 15 s to relearn the baseline.
4.4 Level 3: reasoning with my results
Prediction (written before the test): doubling the window from 60 s to 120 s will not
improve silent-drift recall; it stays below 5 percent and may drop slightly. Reasoning: a
drift is a ramp of 0.05 bpm/s. A trailing window of length W has a mean that lags by about
mW/2 and a std that includes the ramp itself, about mW/sqrt(12). For a noise-free ramp the
z-score therefore cannot exceed sqrt(3), about 1.73, which is below the threshold of 3. The
detector adapts to the drift, the boiling-frog weakness of any rolling-baseline method.
The prediction held for 60 to 120 s (a change of -0.11 percentage points). Beyond that,
recall rises to 4 to 7 percent, which is still low, and I have only a hypothesis (a longer
window gives a larger lag) rather than a proven explanation. Single noise readings do cross
z = 3 inside drifts (maximum z between 3.0 and 5.1), but the two-in-a-row rule filters most
of them.
Missed anomalies: the z-score missed a drift because its baseline climbs with the ramp
(plot level3_missed_zscore.png). Isolation Forest missed a drift because resid_m60
stayed inside the normal range and the score never reached the threshold (plot
level3_missed_iforest.png).
Possible improvement (not implemented): a trend detector such as CUSUM, or a slope
test over a long window gated by low movement, since drift is defined by a slow trend
rather than a level jump.
5. Question C: Design the full system
5.1 Level 1: architecture and schema
Architecture (architecture.png): devices buffer 10 s of readings and send a batch to an
ingestion API (about 100 requests per second for 1,000 users). A message queue
partitioned by user_id feeds two consumers: a DB writer that does batched inserts, and
detection workers that keep per-user state and read the queue instead of the database.
Detection raises alerts to an alert service (dedupe, push/SMS/e-mail) and the alerts table.
A dashboard and API read readings and alerts from the SQL database.
Window 30 s 60 s 120 s 240 s 480 s
Drift recall 0.0% 0.17% 0.06% 4.0% 7.2%
AI-Driven Anomaly Detection and Monitoring System: Project Report
Page 4 of 11
schema.sql has users, readings and alerts. readings uses PRIMARY KEY (user_id, ts): it
rejects duplicate re-sent readings and clusters each user's data by time so 'user X, last
hour' is a range scan. WITHOUT ROWID stores the table as that index, like InnoDB. alerts
stores one row per event (not per second) with indexes on (user_id, ts_start) and ts_start.
5.2 Level 2:three users and three queries
The same recording is loaded as three users with offsets 0, +45 min and -26 hours (21,600
readings). The Question A detector raised 66 alerts, 22 per user (7 drop-out, 9 spike, 6
sudden_drop). The six sudden_drop alerts are the false alarms after drifts. Hand-written
queries (queries.sql):
The 24-hour condition sits in the LEFT JOIN's ON clause. In WHERE it would turn the join
into an inner join and silently drop users with zero alerts. I cross-checked the sliding-hour
query against plain Python.
5.3 Level 3: capacity and where it breaks
Bytes per row: 14 bytes of data (4+4+2+4) plus 18 bytes of row overhead, times 1.15 for
page fill. A cross-check with the 51.2 bytes per row measured in SQLite gives about 133
GB.
Measured evidence (my sandbox; rerun on my laptop): one commit per reading gave
about 1,400 rows/s, against 100,000 needed (70x short), while batches of 1,000 gave about
430,000 rows/s. The detector handles about 209,000 readings/s per core, so about half a
Query Result
Alerts per user in the last 24 h user 1: 22, user 2: 22, user 3: 0 (its data is
from yesterday)
Users with more than 5 alerts in any one
hour (sliding window)
all three users, maximum 14 in one hour
Average HR per user per hour 7 rows; a second column excludes zero
readings from drop-outs
1,000 users 100,000 users
Rows per day 1,000 x 86,400 = 86.4 million 8.64 billion
Writes per second 1,000 100,000
Storage per month 2.592 billion rows x 36.8 B = about 95 GB about 9.5 TB
AI-Driven Anomaly Detection and Monitoring System: Project Report
Page 5 of 11
core covers 100,000 users. So the write path (a request and a commit per reading) breaks
first, then storage and query size.
Changes: devices send 10 s batches, a queue partitioned by user_id, batched inserts,
time-series storage partitioned by day, raw data kept about 30 days then rolled up to 1-
minute averages (60x fewer rows), and detection workers sharded by user_id.
6. Question D: live dashboard with alerts (status: planned, not yet
built)
Plan, to be updated after building: a Streamlit or Flask dashboard reading from SQLite and
plotting HR with anomalies marked; producer.py replaying readings.csv at one row per
second; alert_engine.py reusing the Question A logic as a streaming loop, with an alert
within 5 s of a spike or drop-out starting and a 60 s cooldown so one event never alerts
twice; and level3_measure_delay.py measuring start-to-alert delay for at least 10 events,
reporting the average and worst delay and the main source of delay (likely the
confirmation window or the dashboard refresh interval). Expected from Question A:
spikes and drop-outs alert in about 1 to 1.5 s.
AI-Driven Anomaly Detection and Monitoring System: Project Report
Page 6 of 11
7. Key decisions and trade-offs
8. Limitations
Silent drift is essentially undetected by both methods (recall 3 percent and 0.2
percent). I explain why, but I did not build a detector that solves it.
Isolation Forest's contamination was chosen using labels for scoring, so Level 1
numbers are optimistic.
The z-score raises about 15 false-alarm seconds after every drift ends.
The data is synthetic: real physiology is messier. The three users in Question C share
one signal and differ only by clock offset.
Benchmark numbers depend on the machine and vary between runs.
The Level 3 prediction text was first drafted with AI help and must be rewritten and
committed by me before running the experiment; AI use must be declared in
PERSONAL_INTELLIGENCE.md.
Decision Rejected option Evidence
Movement-adjusted features
for Isolation Forest
Raw HR features Raw-style features flagged 148
walking seconds; final set 10
Moving gate plus baseline that
skips anomalies
Plain rolling z-score
on raw HR
Walking would be flagged; spikes
would inflate the std
Flat-line rule z-score alone Stuck-at-normal-value drop-outs
have z near 0
Two consecutive breaches Single breach A single 3-sigma noise reading
would raise false alarms (about
0.3 percent of seconds)
Primary key (user_id, ts) Auto-increment id
plus index
Saves an index and gives free deduplication and time clustering
One alert per event One alert per
flagged second
22 alerts per user instead of
hundreds of rows
Batched inserts One commit per
reading
About 300x faster in my
benchmark
AI-Driven Anomaly Detection and Monitoring System: Project Report
Page 7 of 11
9.Interview preparation
The live walkthrough asks me to explain my code and change it without AI. Anything I
cannot explain will not count, so I should be able to answer these from memory.
General
Q: Explain the project in one minute. A: A personal 2-hour wearable recording with 20
labelled anomalies. I detect them with Isolation Forest and a from-scratch rolling z-score
without flagging walking, design the storage and alerting system for 1,000 users, and
measure where it breaks at 100,000.
Q: How did you use the seed? A: S = 2504 seeds the generator (resting HR 64, event
positions, walking periods) and every model (random_state). Results are reproducible and
differ from other candidates.
Q: WhyA, C and D and not B? A: A is the core of the topic, C reuses A's detector and D's
database, and D reuses A's detection logic. A complete answer to fewer questions beats
partial answers to four.
Data generation
Q: How do you make sure walking is normal and anomalies do not overlap it? A: Walking
periods are placed first, anomalies are placed by rejection sampling with a 60 s guard
around every reserved block, and only anomaly seconds get label 1.
Q: Why is walking the hard part? A: HR rises 20 to 30 bpm, which is as large as a real
spike. A detector looking only at HR level cannot tell them apart, so the model must use
movement.
Question A, Level 1
Q: How does Isolation Forest work? A: It builds random trees by choosing random
features and split values. Anomalies are few and different, so they are isolated in fewer
splits (short average path), which gives a higher anomaly score. Contamination sets the
share of points flagged.
Q: Why these features and not raw HR? A: resid removes the walking rise, d1 catches
jumps, flat_run catches a stuck sensor, resid_m60 exposes slow drift. Raw-style features
flagged walking heavily.
Q: How did you choose contamination and is that a problem? A: From a sweep scored
with labels, so it is mild leakage. I report the sweep openly: more contamination raises
recall but also walking false alarms.
AI-Driven Anomaly Detection and Monitoring System: Project Report
Page 8 of 11
Q: How did you compute per-type precision? A: For each type I keep that type's rows
plus all normal rows, drop the other types' rows, and compute TP, FP and FN on that
subset.
Q: Why is drift recall so low? A: A drift moves only 0.05 bpm per second. Inside a 60 s
window it barely leaves the normal range, so a rare-event model sees nothing unusual.
Drifts are also 25 percent of all seconds, so they are not rare.
Question A, Level 2
Q: Walk me through your detector loop. A: For each second: if moving, skip. Check the
flat rule. If the buffer has at least 30 values, compute mean and std from the running sums
and the z-score. Count consecutive breaches and flag after two. Only non-breach, nonflat readings are pushed into the buffer.
Q: Why a circular buffer with running sums? A: Each update is constant time: add the
new value and subtract the oldest. Memory is O(W) and the whole run is O(n). This also
matches a streaming use in Question D.
Q: Why exclude anomalies from the baseline? A: A 10 s spike of +50 would inflate a 60 s
std to about 18 and hide the next event.
Q: Why the flat rule? A: A stuck sensor repeating the last value has z near 0. Real readings
with noise are never exactly identical four times in a row.
Q: Why two consecutive breaches? A: One reading beyond 3 sigma happens by chance in
about 0.3 percent of seconds. Requiring two costs about 1 s of delay and removes most
noise false alarms.
Q: Why do you get 90 false alarms after drifts? A: HR snaps back 15 bpm when a drift
ends. That is a large negative z, so the detector flags it for 15 s until the baseline reset. Fix:
treat a large negative step at the end of a long upward trend as recovery, or shorten the
reset.
Q: How did you prove your metrics are correct? A: I compared precision, recall and F1
with scikit-learn on the same predictions for the overall case and each type. All matched
to 1e-12.
Question A, Level 3
Q: What did you predict and what happened? A: Doubling the window would not improve
drift recall (below 5 percent, maybe slightly lower). Actual: 0.17 percent at 60 s and 0.06
percent at 120 s.
AI-Driven Anomaly Detection and Monitoring System: Project Report
Page 9 of 11
Q: Why can a trailing z-score never exceed sqrt(3) on a ramp? A: The mean lags by mW/2
and the std of the window is about mW/sqrt(12). Their ratio is sqrt(12)/2 = sqrt(3) = 1.73,
independent of the window length.
Q: Recall rises at 240 and 480 s. Does that break your reasoning? A: It limits it. My claim
held for 60 to 120 s. At longer windows the lag is larger and recall reaches 4 to 7 percent,
still low; I only have a hypothesis for the cause and would test it with more windows or a
different noise level.
Q: How would you actually detect silent drift? A: Use a trend-based method: CUSUM or a
regression slope over a long window, applied only when movement is low, or compare with
the person's own baseline for the same time of day.
Question C
Q: Why primary key (user_id, ts)? A: It prevents duplicate readings if a device re-sends a
batch, and clusters each user's rows by time so range queries are fast. A separate autoincrement id would need another index.
Q: Why is the 24-hour filter in the ON clause? A: In WHERE it would remove users with
zero alerts and turn the LEFT JOIN into an inner join. In ON, users with no alerts still show
a 0.
Q: Sliding hour or clock hour in Query 2? How would you change it? A: I used a sliding 60-
minute window by self-joining alerts. For clock hours, group by user and strftime('%Y-
%m-%d %H', ts_start) and keep HAVING COUNT(*) > 5.
Q: Why two averages in Query 3? A: Drop-outs read 0 and pull the plain average down.
The valid-only average ignores hr = 0.
Q: Show how you computed storage per month. A: 1,000 users x 86,400 s = 86.4 million
rows per day; x 30 = 2.592 billion; x 36.8 bytes (14 data + 18 overhead, x 1.15) = about 95 GB.
Q: What breaks first at 100,000 users? A: The write path: 100,000 writes per second with
one commit per reading. I measured about 1,400 rows/s that way versus about 430,000
rows/s with batches. Storage (9.5 TB per month) is next. Detection is not the bottleneck
(about half a core).
Q: Why a message queue? A: It absorbs bursts, decouples ingestion from storage and
detection, and allows replay if a consumer fails.
Q: How do you handle duplicate or late readings? A: The primary key rejects duplicates
(insert-or-ignore); late readings are stored with their own timestamp, and the queue
offset allows replay.
Q: What about privacy of health data? A: Authenticate devices, encrypt in transit and at
rest, minimize identifiers, and control access to dashboards and exports.
AI-Driven Anomaly Detection and Monitoring System: Project Report
Page 10 of 11
Question D (answer after building)
Q: How does your engine alert within 5 seconds? A: It reuses the streaming z-score and
flat rule on each new row, with a short confirmation window, so a spike alerts after 2
readings and a drop-out after 4 at most.
Q: How do you avoid repeat alerts within 60 seconds? A: Store the last alert time per
user and type, and suppress anything inside the cooldown.
Q: What is the main source of delay and how would you cut it? A: To be filled in from my
own measured delays (likely the confirmation window or the refresh interval).
Live change tasks I should be able to do
Change the z threshold to 2.5 or the window to 30 s, and predict the effect on false
alarms and recall before running.
Set consecutive to 1 and explain the change in delay and false alarms.
Change Query 1 to the last 12 hours, or Query 2 to clock hours.
Add an index or a new alert type to the schema and explain why.
Change the merge gap that groups flagged seconds into one alert.
Questions about my AI use
Q: Which parts did AI write and where was it weak? A: Be specific and honest. Declare
each tool and its use in PERSONAL_INTELLIGENCE.md, plus one real place where the AI
was wrong and how I caught it. In this project one example is the early Isolation Forest
feature set that flagged walking heavily, found by checking per-type recall and walking
false alarms. Use it only if it matches what I actually saw and did.
Q: Why should we believe you understand this? A: Because I can run each script, explain
every rule in the detector, redo the capacity arithmetic by hand, and change the code live.
AI-Driven Anomaly Detection and Monitoring System: Project Report
Page 11 of 11
