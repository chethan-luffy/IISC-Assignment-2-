"""
question_D/dashboard.py   (Level 1: dashboard that reads from the SQL database)

Run:  streamlit run question_D/dashboard.py
Needs streamlit >= 1.37 (auto-refresh uses st.fragment(run_every=...)).

It only READS the database (read-only connection). The producer writes readings, the alert
engine writes alerts, and this page plots the signal and marks the anomalies.
"""
import csv
import os
import sqlite3

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from db import DEFAULT_DB, connect

HERE = os.path.dirname(os.path.abspath(__file__))
EVENTS_CSV = os.path.join(HERE, "..", "setup", "anomaly_events.csv")
COLORS = {"spike": "#dc2626", "dropout": "#111827", "drift": "#f59e0b"}

st.set_page_config(page_title="Wearable anomaly monitor", layout="wide")
st.title("Wearable monitor: live heart rate and alerts")

with st.sidebar:
    st.header("Settings")
    db_path = st.text_input("Database file", DEFAULT_DB)
    user_id = st.number_input("User id", min_value=1, value=1, step=1)
    window_min = st.select_slider("Time window (minutes)", options=[1, 2, 5, 10, 30, 120], value=5)
    refresh_s = st.select_slider("Refresh every (seconds)", options=[1, 2, 3, 5, 10], value=2)
    show_truth = st.checkbox("Show ground-truth anomalies (shaded)", value=True)
    st.caption("Start the producer and the alert engine in other terminals; this page refreshes by itself.")


@st.cache_data
def load_truth():
    """Ground-truth events by recording time (only used for the shaded overlay)."""
    base = pd.read_csv(os.path.join(HERE, "..", "setup", "readings.csv"), usecols=["timestamp"])["timestamp"]
    out = []
    with open(EVENTS_CSV) as fh:
        for r in csv.DictReader(fh):
            s, l = int(r["start_idx"]), int(r["length_s"])
            out.append((r["anomaly_type"], base[s], base[min(s + l, len(base) - 1)]))
    return out


def read_data(path, uid, seconds):
    if not os.path.exists(path):
        return None, None
    try:
        con = connect(path, readonly=True)
        readings = pd.read_sql_query(
            "SELECT ts, hr, acc FROM readings WHERE user_id = ? ORDER BY ts DESC LIMIT ?", con, params=(uid, seconds))
        readings = readings.iloc[::-1].reset_index(drop=True)
        alerts = pd.read_sql_query(
            "SELECT alert_type, event_start_ts, detected_ts, hr, z FROM alerts WHERE user_id = ? ORDER BY detected_ts", con,
            params=(uid,))
        con.close()
        return readings, alerts
    except (sqlite3.Error, pd.errors.DatabaseError) as e:
        st.error(f"Could not read the database: {e}")
        return None, None


def render():
    readings, alerts = read_data(db_path, int(user_id), window_min * 60)
    if readings is None or readings.empty:
        st.info("No data yet. Start the producer:  python question_D/producer.py --reset")
        return
    readings["ts"] = pd.to_datetime(readings["ts"])
    t_min, t_max = readings["ts"].iloc[0], readings["ts"].iloc[-1]
    alerts["detected_ts"] = pd.to_datetime(alerts["detected_ts"])
    alerts["event_start_ts"] = pd.to_datetime(alerts["event_start_ts"])
    visible = alerts[(alerts["detected_ts"] >= t_min) & (alerts["detected_ts"] <= t_max)]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Latest recording time", t_max.strftime("%H:%M:%S"))
    c2.metric("Latest heart rate", f"{readings['hr'].iloc[-1]:.0f} bpm")
    c3.metric("Alerts in window", len(visible))
    c4.metric("Alerts total", len(alerts))

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.75, 0.25], vertical_spacing=0.04)
    fig.add_trace(go.Scatter(x=readings["ts"], y=readings["hr"], mode="lines", name="Heart rate",
                             line=dict(width=1.3, color="#2563eb")), row=1, col=1)
    fig.add_trace(go.Scatter(x=readings["ts"], y=readings["acc"], mode="lines", name="Movement",
                             line=dict(width=1, color="#6b7280")), row=2, col=1)

    for kind in ("spike", "dropout"):
        sub = visible[visible["alert_type"] == kind]
        if sub.empty:
            continue
        hr_at = readings.set_index("ts")["hr"].reindex(sub["detected_ts"]).to_numpy()
        fig.add_trace(go.Scatter(
            x=sub["detected_ts"], y=hr_at, mode="markers", name=f"ALERT: {kind}",
            marker=dict(size=13, symbol="diamond", color=COLORS[kind], line=dict(width=1, color="white")),
            text=[f"{kind}, event began {s:%H:%M:%S}" for s in sub["event_start_ts"]], hoverinfo="text+x"), row=1, col=1)

    if show_truth:
        for kind, s, e in load_truth():
            s, e = pd.to_datetime(s), pd.to_datetime(e)
            if e >= t_min and s <= t_max:
                fig.add_vrect(x0=s, x1=e, fillcolor=COLORS[kind], opacity=0.15, line_width=0, row=1, col=1)

    fig.update_yaxes(title_text="bpm", row=1, col=1)
    fig.update_yaxes(title_text="acc", row=2, col=1)
    fig.update_layout(height=560, margin=dict(l=10, r=10, t=10, b=10), legend=dict(orientation="h", y=1.07))
    st.plotly_chart(fig)
    st.caption("Diamonds = alerts raised by my engine. Shaded bands = true anomalies from the data generator "
               "(red spike, black drop-out, orange silent drift). Walking is normal and not marked.")

    st.subheader("Recent alerts")
    if alerts.empty:
        st.write("No alerts yet.")
    else:
        show = alerts.tail(10).iloc[::-1].copy()
        show["delay_s"] = (show["detected_ts"] - show["event_start_ts"]).dt.total_seconds()
        st.dataframe(show[["alert_type", "event_start_ts", "detected_ts", "hr", "z", "delay_s"]], hide_index=True)


# auto-refresh: only this fragment re-runs every `refresh_s` seconds
st.fragment(run_every=refresh_s)(render)()
