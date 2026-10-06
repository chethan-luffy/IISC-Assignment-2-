"""
question_C/draw_architecture.py
Draws architecture.png: 1,000 users, one reading per second.
Run: python question_C/draw_architecture.py
"""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

HERE = os.path.dirname(os.path.abspath(__file__))

fig, ax = plt.subplots(figsize=(15, 8))
ax.set_xlim(0, 15)
ax.set_ylim(0, 8)
ax.axis("off")


def box(x, y, w, h, title, sub="", color="#dbeafe"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.05,rounding_size=0.15",
                                fc=color, ec="#1e3a8a", lw=1.5))
    ax.text(x + w / 2, y + h - 0.32, title, ha="center", va="center", fontsize=10.5, weight="bold")
    if sub:
        ax.text(x + w / 2, y + h / 2 - 0.2, sub, ha="center", va="center", fontsize=8.5, color="#222")


def arrow(x1, y1, x2, y2, label="", dy=0.18):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle="->", lw=1.6, color="#111"))
    if label:
        ax.text((x1 + x2) / 2, (y1 + y2) / 2 + dy, label, ha="center", fontsize=8, color="#7c2d12")


# 1. devices
box(0.2, 3.0, 2.2, 2.0, "1. Wearable devices", "1,000 users\n1 reading/s each\nHR + accelerometer\nbuffer 10 s, send batch", "#fef3c7")
# 2. ingestion
box(3.3, 3.0, 2.2, 2.0, "2. Ingestion API", "authenticate device\nvalidate readings\n~100 requests/s\n(1,000 users / 10 s)", "#dcfce7")
# 3. queue
box(6.4, 3.0, 2.2, 2.0, "3. Message queue", "partitioned by user_id\nbuffers bursts,\nreplay on failure", "#ede9fe")
# 4a. db writer + 5. database
box(9.6, 5.5, 2.4, 1.8, "4a. DB writer", "batched INSERTs\n(~1,000 rows per batch)", "#dcfce7")
box(12.4, 4.4, 2.4, 2.9, "5. Database (SQL)", "users\nreadings  PK (user_id, ts)\nalerts\npartitioned by day", "#fee2e2")
# 4b. detection
box(9.6, 2.9, 2.4, 2.0, "4b. Detection workers", "per-user stream state\nrolling z-score + flat rule\nreads the queue, not the DB", "#dbeafe")
# 6. alerts
box(9.6, 0.4, 2.4, 1.8, "6. Alert service", "dedupe (60 s cooldown)\npush / SMS / e-mail", "#fce7f3")
# 7. dashboard
box(12.4, 0.4, 2.4, 2.4, "7. Dashboard + API", "reads readings & alerts\nplots signal, marks\nanomalies, auto-refresh", "#fee2e2")

arrow(2.4, 4.0, 3.3, 4.0, "HTTPS")
arrow(5.5, 4.0, 6.4, 4.0, "1,000 rows/s")
arrow(8.6, 4.6, 9.6, 6.2, "")
arrow(8.6, 3.6, 9.6, 3.9, "")
arrow(12.0, 6.4, 12.4, 6.4, "")
arrow(12.0, 4.2, 12.4, 4.9, "alerts")
arrow(10.8, 2.9, 10.8, 2.2, "")
ax.text(10.7, 2.55, "alert event", ha="right", fontsize=8, color="#7c2d12")
arrow(13.6, 4.4, 13.6, 2.8, "")
ax.text(13.7, 3.6, "SQL reads", ha="left", fontsize=8, color="#7c2d12")
arrow(12.0, 1.3, 12.4, 1.3, "")

ax.text(7.5, 7.6, "Architecture: 1,000 users x 1 reading/second = 1,000 writes/s, 86.4 million rows/day",
        ha="center", fontsize=13, weight="bold")
ax.text(7.5, 0.1, "Data path: device -> ingestion -> queue -> (DB writer -> database) and (detection -> alerts -> dashboard)",
        ha="center", fontsize=9, style="italic")
plt.tight_layout()
plt.savefig(os.path.join(HERE, "architecture.png"), dpi=130)
print("saved architecture.png")
