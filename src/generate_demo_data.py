#!/usr/bin/env python3
"""
Generates sample_data/demo_weekly_channel_performance.csv — synthetic but
realistic weekly channel performance data, shaped like what the real
weekly_channel_performance.sql query returns from thelook_ecommerce.

Also runs the full analysis pipeline on this demo data and writes the
resulting chart + summary to sample_output/, so the repo ships with a
ready-made example of what the project produces — no GCP setup required
for someone to see real output.
"""

from pathlib import Path

import numpy as np
import pandas as pd

from analyze_channel_performance import plot_trend, compute_wow_change, write_summary

np.random.seed(7)  # fixed seed = same "random" output every run

CHANNELS = {
    # channel: (starting weekly revenue, starting weekly orders, weekly trend, noise level)
    "Search":   (16500, 220,  0.005, 0.07),
    "Organic":  (18000, 260,  0.01,  0.06),
    "Email":    (9000,  140,  0.015, 0.05),
    "Facebook": (14000, 190, -0.02,  0.09),
    "Display":  (6000,  95,  -0.03,  0.10),
}


def get_num_weeks():
    while True:
        raw = input("How many weeks of demo history would you like to generate? [default: 12] ").strip()
        if raw == "":
            return 12
        if raw.isdigit() and int(raw) > 0:
            return int(raw)
        print("Please enter a positive whole number (e.g. 12), or press Enter for the default.")


N_WEEKS = get_num_weeks()
start = pd.Timestamp("2026-07-13")  # a Monday
weeks = [start + pd.Timedelta(weeks=i) for i in range(N_WEEKS)]

rows = []
for channel, (rev, orders, trend, noise) in CHANNELS.items():
    for week in weeks:
        rev *= (1 + trend + np.random.normal(0, noise))
        orders *= (1 + trend * 0.6 + np.random.normal(0, noise * 0.7))
        rev, orders = max(rev, 500), max(orders, 10)

        rows.append({
            "week_start": week,
            "channel": channel,
            "orders": int(round(orders)),
            "customers": int(orders * np.random.uniform(0.72, 0.9)),
            "revenue": round(rev, 2),
            "avg_order_value": round(rev / orders, 2),
        })

df = pd.DataFrame(rows).sort_values(["week_start", "channel"]).reset_index(drop=True)

sample_data_dir = Path("sample_data")
sample_data_dir.mkdir(exist_ok=True)
demo_csv_path = sample_data_dir / "demo_weekly_channel_performance.csv"
df.to_csv(demo_csv_path, index=False)
print(f"Wrote {len(df)} rows to {demo_csv_path}")

sample_output_dir = Path("sample_output")
sample_output_dir.mkdir(exist_ok=True)

plot_trend(df, sample_output_dir / "channel_revenue_trend.png")
wow = compute_wow_change(df, trim_recent_weeks=0)  # clean synthetic data, nothing to trim
write_summary(wow, sample_output_dir / "summary.md")
df.to_csv(sample_output_dir / "weekly_channel_performance.csv", index=False)

print(f"Also wrote chart, data, and summary to {sample_output_dir}/")