# Weekly Channel Performance Analyzer

**Business question:** Which acquisition channels are gaining or losing momentum
week-over-week, and where should spend or attention shift next?

**Data source:** [`bigquery-public-data.thelook_ecommerce`](https://console.cloud.google.com/marketplace/product/bigquery-public-data/thelook-ecommerce) — a public BigQuery dataset simulating an online retailer's orders, users, and acquisition channels.

**Method:** A BigQuery SQL query aggregates completed orders by ISO week and
acquisition channel (`users.traffic_source`). A Python script pulls the
result into pandas, computes week-over-week % change in revenue and orders
per channel, renders a trend chart, and writes a plain-English summary with
a recommendation — the artifact format I'd hand a client each week.

**Key finding (sample run):** total revenue across channels moved **+2.5%**
week-over-week; Facebook was the strongest mover (+11.8%), Organic the
weakest (-6.8%). See [`sample_output/summary.md`](sample_output/summary.md)
for the full breakdown.

**A real data-quality issue I caught along the way:** the live dataset is
periodically refreshed with batch-loaded synthetic orders dated near the
current date, which creates an artificial spike in the most recent 1–2
weeks — not real business activity. A naive week-over-week comparison
against the literal latest week showed every channel "collapsing" by
60–70% in lockstep, which was the tell that something was wrong with the
comparison, not the business. The script now compares the two most recent
*stable* weeks instead (`--trim-recent`, default 2), rather than trusting
the live edge of the dataset.

---

## Why this project

Dashboards (Looker Studio, GA4 reports) are great for exploration, but a lot
of real consulting work is the recurring, slightly tedious step after that:
turning last week's numbers into a short written read a client or team can
act on. This script automates that step end-to-end — query → analysis →
chart → written summary — rather than stopping at a chart.

## Project structure
├── src/
│ ├── weekly_channel_performance.sql # the BigQuery query
│ ├── analyze_channel_performance.py # main script: fetch → analyze → chart → summary
│ └── generate_demo_data.py # (re)generates the bundled demo dataset + sample output
├── sample_data/
│ └── demo_weekly_channel_performance.csv # synthetic input used by --demo mode
├── sample_output/
│ ├── weekly_channel_performance.csv
│ ├── channel_revenue_trend.png
│ └── summary.md
├── requirements.txt
└── README.md


## Running it

**Demo mode** — no GCP account or credentials needed, uses bundled sample data:

```bash
pip install -r requirements.txt
python src/analyze_channel_performance.py --demo
```

If you don't pass `--weeks`, the script prompts you interactively for how
many trailing weeks to analyze (press Enter for the default of 12).

**Live mode** — against the real public dataset, requires a GCP project with
billing enabled (BigQuery's public-dataset queries still bill the querying
project, though the first 1TB/month of query processing is free) and
`google-cloud-bigquery` installed and authenticated
(`gcloud auth application-default login`):

```bash
python src/analyze_channel_performance.py --project YOUR_GCP_PROJECT_ID --weeks 12
```

Either mode writes `weekly_channel_performance.csv`, `channel_revenue_trend.png`,
and `summary.md` to the output directory (`./output/` by default, or
`--output-dir`).

**Regenerating the demo dataset** (optional — only needed to change the
synthetic data or scenario):

```bash
python src/generate_demo_data.py
```

This also re-runs the full analysis on the new demo data and refreshes
`sample_output/`.

## Sample output

![Weekly revenue by channel](sample_output/channel_revenue_trend.png)

Full written summary: [`sample_output/summary.md`](sample_output/summary.md)

## Possible extensions

- Swap the written summary from a template to an LLM call for more natural
  narrative generation
- Add a funnel view using the dataset's `events` table (session → cart → purchase)
- Push `summary.md` straight into a Slack webhook or email as a scheduled job
- Parameterize the channel grouping to match real ad-platform UTM conventions

---
*Part of a small portfolio of web analytics / marketing data projects.*