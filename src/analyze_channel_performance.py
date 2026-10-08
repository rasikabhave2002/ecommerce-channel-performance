#!/usr/bin/env python3
"""
Weekly channel performance analyzer
------------------------------------
Pulls weekly revenue/orders/customers by acquisition channel from
bigquery-public-data.thelook_ecommerce, computes week-over-week change,
renders a trend chart, and writes a plain-English summary. Also builds a
session-level funnel (sessions → cart → purchase) from the events table.

Usage:
    python analyze_channel_performance.py --project YOUR_GCP_PROJECT_ID --weeks 12
    python analyze_channel_performance.py --demo --weeks 8
    python analyze_channel_performance.py --demo      # prompts interactively for weeks
"""

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd

SQL_PATH = Path(__file__).parent / "weekly_channel_performance.sql"
FUNNEL_SQL_PATH = Path(__file__).parent / "session_funnel.sql"


def parse_args():
    parser = argparse.ArgumentParser(description="Weekly channel performance analyzer")
    parser.add_argument("--project", default="main-beanbag-393810", help="GCP project ID to bill queries to")
    parser.add_argument("--weeks", type=int, default=None, help="Trailing weeks to pull (if omitted, you'll be prompted)")
    parser.add_argument("--trim-recent", type=int, default=2, help="Most recent weeks to exclude from WoW comparison")
    parser.add_argument("--demo", action="store_true", help="Use bundled sample data instead of BigQuery")
    parser.add_argument("--output-dir", default="output", help="Where to write CSV/chart/summary")
    return parser.parse_args()


def get_weeks_back(args):
    if args.weeks is not None:
        return args.weeks

    while True:
        raw = input("How many trailing weeks of data would you like to analyze? [default: 12] ").strip()
        if raw == "":
            return 12
        if raw.isdigit() and int(raw) > 0:
            return int(raw)
        print("Please enter a positive whole number (e.g. 8), or press Enter for the default.")


# --- Weekly channel performance: data loading ---

def load_demo_data(weeks_back):
    demo_path = Path(__file__).parent.parent / "sample_data" / "demo_weekly_channel_performance.csv"
    df = pd.read_csv(demo_path, parse_dates=["week_start"])
    cutoff = df["week_start"].max() - pd.Timedelta(weeks=weeks_back)
    return df[df["week_start"] > cutoff].reset_index(drop=True)


def fetch_from_bigquery(project, weeks_back):
    from google.cloud import bigquery  # only needed for live mode

    client = bigquery.Client(project=project)
    query = SQL_PATH.read_text()
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("weeks_back", "INT64", weeks_back)]
    )
    return client.query(query, job_config=job_config).to_dataframe()


# --- Weekly channel performance: chart, WoW calc, summary ---

def plot_trend(df, out_path):
    pivot = df.pivot_table(index="week_start", columns="channel", values="revenue", aggfunc="sum")

    fig, ax = plt.subplots(figsize=(10, 5.5))
    for channel in pivot.columns:
        ax.plot(pivot.index, pivot[channel], marker="o", linewidth=2, label=channel)

    ax.set_title("Weekly Revenue by Acquisition Channel", fontsize=13, fontweight="bold")
    ax.set_xlabel("Week starting")
    ax.set_ylabel("Revenue ($)")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x:,.0f}"))
    ax.legend(loc="upper left", fontsize=9, frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", alpha=0.3)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def compute_wow_change(df, trim_recent_weeks=2):
    weeks = sorted(df["week_start"].unique())

    # Trim the most recent weeks: the live dataset is periodically refreshed
    # with batch-loaded synthetic data near the current date, which can
    # create artificial spikes/partial weeks unrelated to real channel
    # performance. We compare two stable, fully-settled weeks instead.
    # NOTE: guard with `trim_recent_weeks > 0` — weeks[:-0] in Python is NOT
    # "trim nothing", it's actually weeks[:0], an empty list. A classic
    # negative-zero slicing trap.
    if trim_recent_weeks > 0 and len(weeks) > trim_recent_weeks:
        weeks = weeks[:-trim_recent_weeks]

    if len(weeks) < 2:
        return pd.DataFrame()

    latest, prior = weeks[-1], weeks[-2]
    latest_df = df[df["week_start"] == latest].set_index("channel")
    prior_df = df[df["week_start"] == prior].set_index("channel")

    merged = latest_df[["revenue", "orders"]].join(
        prior_df[["revenue", "orders"]], lsuffix="_latest", rsuffix="_prior", how="outer"
    ).fillna(0)

    merged["revenue_wow_pct"] = (
        (merged["revenue_latest"] - merged["revenue_prior"]) / merged["revenue_prior"].replace(0, pd.NA) * 100
    ).round(1)
    merged["orders_wow_pct"] = (
        (merged["orders_latest"] - merged["orders_prior"]) / merged["orders_prior"].replace(0, pd.NA) * 100
    ).round(1)

    merged = merged.sort_values("revenue_latest", ascending=False)
    merged.attrs["latest_week"] = str(latest)
    merged.attrs["prior_week"] = str(prior)
    return merged


def write_summary(wow, out_path):
    if wow.empty:
        out_path.write_text("Not enough weeks of data to compute week-over-week change.\n")
        return

    latest_week = wow.attrs.get("latest_week", "latest week")
    prior_week = wow.attrs.get("prior_week", "prior week")

    total_latest = wow["revenue_latest"].sum()
    total_prior = wow["revenue_prior"].sum()
    total_wow = (total_latest - total_prior) / total_prior * 100 if total_prior else 0

    best = wow["revenue_wow_pct"].idxmax()
    worst = wow["revenue_wow_pct"].idxmin()

    lines = [
        "# Weekly Channel Performance Summary",
        "",
        f"**Period compared:** {prior_week} → {latest_week}",
        "",
        "## Headline",
        f"- Total revenue across all channels moved **{total_wow:+.1f}%** week-over-week "
        f"(${total_prior:,.0f} → ${total_latest:,.0f}).",
        f"- **{best}** had the strongest week-over-week revenue move: {wow.loc[best, 'revenue_wow_pct']:+.1f}%.",
        f"- **{worst}** had the weakest: {wow.loc[worst, 'revenue_wow_pct']:+.1f}%.",
        "",
        "## Channel breakdown",
        "",
        "| Channel | Revenue (latest) | WoW Revenue % | Orders (latest) | WoW Orders % |",
        "|---|---:|---:|---:|---:|",
    ]
    for channel, row in wow.iterrows():
        lines.append(
            f"| {channel} | ${row['revenue_latest']:,.0f} | {row['revenue_wow_pct']:+.1f}% | "
            f"{int(row['orders_latest'])} | {row['orders_wow_pct']:+.1f}% |"
        )

    lines += [
        "",
        "## Recommendation",
        f"Investigate **{worst}** before next week's spend decisions — a single-week dip can be "
        "noise, but if it persists into a second week it's worth checking landing page changes, "
        "creative fatigue, or a tracking/attribution issue. Consider reallocating a small amount "
        f"of test budget toward **{best}** while the trend holds, and re-check after one more week "
        "of data before making a larger shift.",
    ]
    out_path.write_text("\n".join(lines) + "\n")


# --- Session funnel: data loading, chart, summary ---

def fetch_funnel_from_bigquery(project, weeks_back):
    from google.cloud import bigquery

    client = bigquery.Client(project=project)
    query = FUNNEL_SQL_PATH.read_text()
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("weeks_back", "INT64", weeks_back)]
    )
    return client.query(query, job_config=job_config).to_dataframe()


def load_demo_funnel_data():
    demo_path = Path(__file__).parent.parent / "sample_data" / "demo_session_funnel.csv"
    return pd.read_csv(demo_path)


def plot_funnel(df, out_path):
    totals = [df["sessions"].sum(), df["added_to_cart"].sum(), df["purchased"].sum()]
    labels = ["Sessions", "Added to Cart", "Purchased"]

    fig, ax = plt.subplots(figsize=(8, 4.5))
    bars = ax.barh(labels, totals, color=["#4C72B0", "#DD8452", "#55A868"])
    ax.invert_yaxis()  # largest stage on top
    ax.set_xlabel("Sessions")
    ax.set_title("Session Funnel: Sessions → Cart → Purchase", fontsize=13, fontweight="bold")
    ax.spines[["top", "right"]].set_visible(False)
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:,.0f}"))

    for bar, total in zip(bars, totals):
        pct = total / totals[0] * 100
        ax.text(bar.get_width() + totals[0] * 0.01, bar.get_y() + bar.get_height() / 2,
                 f"{total:,.0f} ({pct:.0f}%)", va="center", fontsize=10)

    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def write_funnel_summary(df, out_path):
    if df.empty:
        out_path.write_text("No funnel data available.\n")
        return

    df = df.copy()
    df["cart_rate_pct"] = (df["added_to_cart"] / df["sessions"] * 100).round(1)
    df["purchase_rate_pct"] = (df["purchased"] / df["added_to_cart"].replace(0, pd.NA) * 100).round(1)
    df["overall_conversion_pct"] = (df["purchased"] / df["sessions"] * 100).round(1)

    total_sessions = df["sessions"].sum()
    total_cart = df["added_to_cart"].sum()
    total_purchased = df["purchased"].sum()

    lines = [
        "# Session Funnel Summary",
        "",
        "**Sessions → Cart → Purchase**, by channel. Note: this uses "
        "`events.traffic_source`, a separate field/taxonomy from "
        "`users.traffic_source` used in the weekly revenue report — the two "
        "should not be compared directly.",
        "",
        "## Overall",
        f"- {total_sessions:,} sessions → {total_cart:,} added to cart "
        f"({total_cart/total_sessions*100:.1f}%) → {total_purchased:,} purchased "
        f"({total_purchased/total_cart*100:.1f}% of cart-adders, "
        f"{total_purchased/total_sessions*100:.1f}% of all sessions).",
        "",
        "## By channel",
        "",
        "| Channel | Sessions | Added to Cart | Cart Rate | Purchased | Purchase Rate (of cart) | Overall Conversion |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for _, row in df.sort_values("sessions", ascending=False).iterrows():
        lines.append(
            f"| {row['channel']} | {row['sessions']:,} | {row['added_to_cart']:,} | "
            f"{row['cart_rate_pct']:.1f}% | {row['purchased']:,} | "
            f"{row['purchase_rate_pct']:.1f}% | {row['overall_conversion_pct']:.1f}% |"
        )
    out_path.write_text("\n".join(lines) + "\n")


def main():
    args = parse_args()
    weeks_back = get_weeks_back(args)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)

    if args.demo:
        print("Running in demo mode (bundled sample data, no BigQuery call)...")
        df = load_demo_data(weeks_back)
    else:
        print(f"Querying bigquery-public-data.thelook_ecommerce (project={args.project}, weeks={weeks_back})...")
        df = fetch_from_bigquery(args.project, weeks_back)

    df.to_csv(output_dir / "weekly_channel_performance.csv", index=False)
    print(f"Saved {len(df)} rows to {output_dir}/weekly_channel_performance.csv")

    plot_trend(df, output_dir / "channel_revenue_trend.png")
    print(f"Saved chart to {output_dir}/channel_revenue_trend.png")

    wow = compute_wow_change(df, trim_recent_weeks=args.trim_recent)
    write_summary(wow, output_dir / "summary.md")
    print(f"Saved summary to {output_dir}/summary.md")

    if args.demo:
        funnel_df = load_demo_funnel_data()
    else:
        funnel_df = fetch_funnel_from_bigquery(args.project, weeks_back)

    plot_funnel(funnel_df, output_dir / "session_funnel.png")
    print(f"Saved funnel chart to {output_dir}/session_funnel.png")

    write_funnel_summary(funnel_df, output_dir / "funnel_summary.md")
    print(f"Saved funnel summary to {output_dir}/funnel_summary.md")


if __name__ == "__main__":
    main()