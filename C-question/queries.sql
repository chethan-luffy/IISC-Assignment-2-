-- question_C/queries.sql  (hand-written, SQLite)
-- Run with:  python question_C/level2_load_and_query.py
--
-- The data is a recording, so "now" is defined as the newest reading in the database.
-- In production you would replace it with the real current time.


-- Q1. Alerts per user in the last 24 hours -----------------------------------------
-- LEFT JOIN from users, so a user with zero recent alerts still shows up with 0.
-- The 24-hour condition lives in the JOIN (not in WHERE), otherwise the LEFT JOIN
-- would silently turn into an inner join and drop the users with 0 alerts.
SELECT u.user_id,
       u.name,
       COUNT(a.alert_id) AS alerts_last_24h
FROM users AS u
LEFT JOIN alerts AS a
       ON a.user_id  = u.user_id
      AND a.ts_start >= datetime((SELECT MAX(ts) FROM readings), '-24 hours')
GROUP BY u.user_id, u.name
ORDER BY u.user_id;


-- Q2. Users with more than five alerts in any one hour -----------------------------
-- "Any one hour" = any sliding 60-minute window, not just clock hours:
-- for every alert a1, count the same user's alerts that start within the next hour.
-- A user qualifies if the largest such count is above 5.
SELECT user_id,
       MAX(alerts_in_hour) AS max_alerts_in_any_hour
FROM (
    SELECT a1.user_id,
           a1.alert_id,
           COUNT(*) AS alerts_in_hour
    FROM alerts AS a1
    JOIN alerts AS a2
      ON a2.user_id  = a1.user_id
     AND a2.ts_start >= a1.ts_start
     AND a2.ts_start <  datetime(a1.ts_start, '+1 hour')
    GROUP BY a1.user_id, a1.alert_id
)
GROUP BY user_id
HAVING MAX(alerts_in_hour) > 5
ORDER BY user_id;


-- Q3. Average heart rate per user per hour -----------------------------------------
-- Clock-hour buckets. Two averages: all readings, and valid readings only (hr > 0).
-- Drop-outs read 0, which drags the plain average down, so the second column is the
-- clinically meaningful one.
SELECT user_id,
       strftime('%Y-%m-%d %H:00', ts)                  AS hour_start,
       COUNT(*)                                         AS readings,
       ROUND(AVG(hr), 2)                                AS avg_hr_all,
       ROUND(AVG(CASE WHEN hr > 0 THEN hr END), 2)      AS avg_hr_valid
FROM readings
GROUP BY user_id, strftime('%Y-%m-%d %H:00', ts)
ORDER BY user_id, hour_start;
