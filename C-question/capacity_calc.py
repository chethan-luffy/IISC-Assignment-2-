"""
question_C/capacity_calc.py   (Level 3: the arithmetic, step by step)

Run:  python question_C/capacity_calc.py
Inputs that come from MY OWN runs are marked (measured); the rest are stated assumptions.
"""

SECONDS_PER_DAY = 24 * 60 * 60          # 86,400
DAYS_PER_MONTH = 30

# --- bytes per row (design: MySQL InnoDB-style clustered table) ----------------------
user_id, ts, hr, acc = 4, 4, 2, 4       # INT, TIMESTAMP, SMALLINT, FLOAT
payload = user_id + ts + hr + acc       # 14 bytes of real data
overhead = 6 + 7 + 5                    # transaction id + roll pointer + record header
row_bytes = payload + overhead          # 32 bytes
page_factor = 1.15                      # pages are not 100 % full + page headers (assumption)
effective = row_bytes * page_factor     # ~36.8 bytes
measured_sqlite = 51.2                  # bytes per reading row measured in Level 2 (SQLite, TEXT timestamp)

alerts_per_user_2h = 22                 # measured in Level 2
alert_row_bytes = 80                    # assumption (2 timestamps + type + ids)


def report(users):
    print(f"\n================  {users:,} users  ================")
    rows_per_day = users * SECONDS_PER_DAY
    writes_per_s = users * 1
    rows_per_month = rows_per_day * DAYS_PER_MONTH
    gb = rows_per_month * effective / 1e9
    gb_sqlite = rows_per_month * measured_sqlite / 1e9
    print(f"1. rows per day       = {users:,} users x {SECONDS_PER_DAY:,} s = {rows_per_day:,}")
    print(f"2. writes per second  = {users:,} users x 1 reading/s = {writes_per_s:,}")
    print(f"3. rows per month     = {rows_per_day:,} x {DAYS_PER_MONTH} = {rows_per_month:,}")
    print(f"4. bytes per row      = payload {payload} + overhead {overhead} = {row_bytes}; x {page_factor} page factor = {effective:.1f}")
    print(f"5. storage per month  = {rows_per_month:,} x {effective:.1f} B = {gb:,.0f} GB  (= {gb / 1000:.2f} TB)")
    print(f"   cross-check with the measured SQLite row size ({measured_sqlite} B): {gb_sqlite:,.0f} GB ({gb_sqlite / 1000:.2f} TB)")
    print(f"   lower bound, payload only ({payload} B): {rows_per_month * payload / 1e9:,.0f} GB")
    alerts_day = users * alerts_per_user_2h * 12
    print(f"6. alerts per day     = {users:,} x {alerts_per_user_2h} per 2 h x 12 = {alerts_day:,}  "
          f"(~{alerts_day * alert_row_bytes / 1e6:,.0f} MB/day: negligible next to readings)")
    print(f"7. with 3 replicas the cluster stores {3 * gb / 1000:.2f} TB per month")


report(1_000)
report(100_000)
