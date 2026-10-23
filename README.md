# Marketing Analytics Dashboard

An end-to-end marketing analytics project in SQL and Python. It uses **real Google Analytics 4 (GA4) data** to analyze channels, the purchase funnel and landing pages, plus a simulated campaign dataset for paid-media metrics (bounce rate, ROAS) that the GA4 sample doesn't contain.

**Tools:** BigQuery SQL · Python (Pandas, Plotly) · GA4 · ETL

![GA4 dashboard](images/ga4_dashboard.png)

---

## Part 1: GA4 funnel and channel analysis (real data)

Source: Google's public GA4 sample ecommerce dataset (Google Merchandise Store, Nov 2020 to Jan 2021), 360K+ sessions.

- **Channels:** Referral converts best (1.66% of sessions, $1.31 revenue per session); Paid Search converts worst (0.98%, $0.58 per session).
- **Funnel:** only ~20% of users who view a product add it to the cart, and 54% of users who begin checkout abandon. This holds on every device.
- **Device:** mobile converts slightly better than desktop (1.71% vs 1.62%), so the fix is the product page and checkout flow, not a mobile-specific one.
- **Seasonality:** revenue peaked on Cyber Monday (Nov 30, 2020, ~$12K).
- **Landing pages:** the Dino Game Tee page brings 18K sessions but converts at 0.02% with 45% engagement.

## Part 2: Paid campaign performance (simulated data)

10,000 rows of synthetic campaign data across 7 channels (`marketing_data.csv`). The GA4 sample has no ad spend, so ROAS and bounce analysis use this dataset.

- **Traffic vs conversion:** Google Ads drove the most traffic (360K sessions) but Email converted best (7.75% vs 4.50%).
- **Bounce:** Instagram has the highest bounce rate (65.2%), flagging a landing page or targeting issue.
- **ROAS:** Google Ads leads and Facebook trails (215x vs 67x). The spend values are synthetic and unrealistically low, so compare channels with each other and don't treat the absolute ROAS as a benchmark.

![Campaign dashboard](images/campaign_dashboard.png)

---

## How the pipeline works (ETL)

| Step | What happens |
|---|---|
| **Extract** | Four BigQuery SQL queries in `sql/` pull channel, funnel, daily and landing page data from the GA4 export (`UNNEST` of `event_params`). Results are saved as CSVs in `data/ga4/`. |
| **Transform** | `analysis.py` cleans and aggregates with Pandas: sessions keyed on `user_pseudo_id + ga_session_id`, conversion and engagement rates, funnel step rates, 7-day rolling averages, homepage hostnames combined, duplicates dropped. |
| **Load** | One command rebuilds the interactive Plotly dashboard (`dashboard.html`) and prints the key findings. |

## Files

| File | Description |
|---|---|
| `analysis.py` | The full pipeline: transform, findings and dashboard for both datasets |
| `sql/` | BigQuery queries for the GA4 extracts |
| `data/ga4/` | CSV exports of the query results |
| `marketing_data.csv` | 10,000-row simulated campaign dataset |
| `dashboard.html` | Interactive dashboard (open in a browser) |
| `images/` | Dashboard screenshots used in this README |

## Run it

```bash
pip install -r requirements.txt
python analysis.py
```

Then open `dashboard.html` in a browser (it loads Plotly from a CDN, so you need internet).

To refresh the GA4 data: run each query in `sql/` in the [BigQuery console](https://console.cloud.google.com/bigquery) (the free sandbox works, no billing needed) and save the results over the matching CSV in `data/ga4/`.

## Data notes

- GA4 channel is based on `traffic_source`, which in the export is first-touch acquisition.
- The funnel is an open funnel: distinct users who fired each ecommerce event during the period.
- Google obfuscates the sample dataset, so some source and medium values appear as `<Other>` or `(data deleted)`; they are shown as "Other / Redacted".
- Revenue in the GA4 sample drops to about $0 after Jan 25, 2021 while purchases continue, so revenue figures stop at that date (sessions and purchase counts use the full period).
- The homepage appears under three hostnames in the export; they are combined in the landing page analysis.
