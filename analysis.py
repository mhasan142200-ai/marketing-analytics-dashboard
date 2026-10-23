"""
Marketing Analytics Dashboard
=============================
One pipeline, two datasets:

  Part 1  GA4 (real data)    Google Merchandise Store events exported from BigQuery:
                             channel performance, purchase funnel by device,
                             daily trend, landing pages.
  Part 2  Simulated campaigns  10,000 rows of synthetic campaign data (marketing_data.csv).
                             The GA4 sample has no ad spend, so ROAS, bounce rate and
                             monthly trends come from this dataset.

Pipeline (ETL):
  Extract    BigQuery SQL in sql/ -> CSV exports in data/ga4/
  Transform  Pandas cleaning, aggregation and metric calculation
  Load       Interactive Plotly dashboard (dashboard.html) + key findings in the console

Run:   pip install -r requirements.txt
       python analysis.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

ROOT = Path(__file__).parent
GA4_DIR = ROOT / "data" / "ga4"
SIM_FILE = ROOT / "marketing_data.csv"
OUT_FILE = ROOT / "dashboard.html"

GA4_FILES = ["channel_performance", "funnel_by_device", "daily_trend", "landing_pages"]
FUNNEL = ["visited", "viewed_item", "added_to_cart", "began_checkout", "purchased"]
FUNNEL_LABELS = ["Visit to view item", "View item to add to cart",
                 "Add to cart to begin checkout", "Begin checkout to purchase"]

# Revenue in the obfuscated GA4 sample drops to ~$0 after this date while purchases continue,
# so revenue figures stop here (sessions and purchase counts use the full period).
REVENUE_CUTOFF = pd.Timestamp("2021-01-25")

BLUE, RED, GREEN, PURPLE, ORANGE, TEAL = "#4C78A8", "#E45756", "#54A24B", "#B279A2", "#F58518", "#72B7B2"


# --------------------------------------------------------------------------------------
# PART 1: GA4 (real data)
# --------------------------------------------------------------------------------------
def load_ga4():
    missing = [f for f in GA4_FILES if not (GA4_DIR / f"{f}.csv").exists()]
    if missing:
        sys.exit(f"Missing CSVs in {GA4_DIR}: {', '.join(m + '.csv' for m in missing)}")
    d = {f: pd.read_csv(GA4_DIR / f"{f}.csv") for f in GA4_FILES}
    d["daily_trend"]["date"] = pd.to_datetime(d["daily_trend"]["date"])
    return d


def transform_ga4(d):
    ch = d["channel_performance"].copy()
    ch["engagement_rate"] = ch["engaged_sessions"] / ch["sessions"]
    ch["conversion_rate"] = ch["purchase_sessions"] / ch["sessions"]
    ch["revenue_per_session"] = ch["revenue_usd"] / ch["sessions"]
    ch["session_share"] = ch["sessions"] / ch["sessions"].sum()
    ch["revenue_share"] = ch["revenue_usd"] / ch["revenue_usd"].sum()

    fn = d["funnel_by_device"].copy()
    for a, b in zip(FUNNEL, FUNNEL[1:]):
        fn[f"{a}->{b}"] = fn[b] / fn[a]
    fn["overall_conversion"] = fn["purchased"] / fn["visited"]

    tr = d["daily_trend"].copy()
    tr["sessions_7d"] = tr["sessions"].rolling(7, min_periods=1).mean()
    tr["revenue_valid"] = tr["date"] <= REVENUE_CUTOFF
    tr["revenue_7d"] = tr["revenue_usd"].where(tr["revenue_valid"]).rolling(7, min_periods=1).mean()
    tr.loc[~tr["revenue_valid"], "revenue_7d"] = np.nan

    # The homepage is reported under several hostnames; combine them by path.
    lp = d["landing_pages"].copy()
    lp["page"] = (lp["landing_page"].str.replace(r"^https?://[^/]+", "", regex=True)
                  .str.lower().str.rstrip("/").replace("", "/"))
    lp["engaged"] = lp["engagement_rate"] * lp["sessions"]
    lp["purchases"] = lp["conversion_rate"] * lp["sessions"]
    lp = lp.groupby("page", as_index=False)[["sessions", "engaged", "purchases"]].sum()
    lp["engagement_rate"] = lp["engaged"] / lp["sessions"]
    lp["conversion_rate"] = lp["purchases"] / lp["sessions"]
    lp = lp.sort_values("sessions", ascending=False).reset_index(drop=True)
    return {"channels": ch, "funnel": fn, "trend": tr, "pages": lp}


def ga4_findings(t):
    ch, fn, tr, lp = t["channels"], t["funnel"], t["trend"], t["pages"]
    out = []

    named = ch[~ch["channel"].isin(["Other", "Other / Redacted"])]
    best, worst = named.loc[named["conversion_rate"].idxmax()], named.loc[named["conversion_rate"].idxmin()]
    out.append(f"<b>Channels:</b> {best['channel']} converts best ({best['conversion_rate']:.2%} of sessions, "
               f"${best['revenue_per_session']:.2f}/session); {worst['channel']} converts worst "
               f"({worst['conversion_rate']:.2%}, ${worst['revenue_per_session']:.2f}/session).")

    total = fn[FUNNEL].sum()
    rates = [total[b] / total[a] for a, b in zip(FUNNEL, FUNNEL[1:])]
    out.append(f"<b>Funnel:</b> only {rates[1]:.0%} of users who view a product add it to the cart, and "
               f"{rates[3]:.0%} of those who begin checkout complete the purchase "
               f"({1 - rates[3]:.0%} abandon). Overall, {total['purchased'] / total['visited']:.2%} of visitors buy.")

    f = fn.set_index("device")
    if {"desktop", "mobile"} <= set(f.index):
        out.append(f"<b>Device:</b> mobile converts at {f.loc['mobile', 'overall_conversion']:.2%} vs "
                   f"{f.loc['desktop', 'overall_conversion']:.2%} on desktop, so the leaks are in the product page "
                   f"and checkout flow on every device, not a mobile-specific problem.")

    ok = tr[tr["revenue_valid"]]
    peak = ok.loc[ok["revenue_usd"].idxmax()]
    out.append(f"<b>Seasonality:</b> revenue peaked on {peak['date']:%b %d, %Y} (${peak['revenue_usd']:,.0f}, Cyber Monday). "
               f"Through {REVENUE_CUTOFF:%b %d} the store earned ${ok['revenue_usd'].sum():,.0f} from "
               f"{ok['purchases'].sum():,} purchases.")

    big = lp[lp["sessions"] >= 5000]
    top, low = big.loc[big["conversion_rate"].idxmax()], big.loc[big["conversion_rate"].idxmin()]
    out.append(f"<b>Landing pages (5,000+ sessions):</b> {top['page']} converts best ({top['conversion_rate']:.2%}). "
               f"{low['page']} brings {low['sessions']:,.0f} sessions but converts at {low['conversion_rate']:.2%} "
               f"with {low['engagement_rate']:.0%} engagement, the clearest page to fix.")
    return out


def ga4_figure(t):
    ch, fn, tr, lp = t["channels"], t["funnel"], t["trend"], t["pages"]
    fig = make_subplots(
        rows=4, cols=2,
        specs=[[{"colspan": 2, "secondary_y": True}, None], [{}, {}], [{"colspan": 2}, None], [{"colspan": 2}, None]],
        subplot_titles=("Daily sessions and revenue (7-day average)", "Conversion rate by channel",
                        "Revenue per session by channel",
                        "Funnel step conversion by device (share of users continuing to the next step)",
                        "Conversion rate of the 10 biggest landing pages"),
        vertical_spacing=0.07, horizontal_spacing=0.14,
    )
    fig.add_trace(go.Scatter(x=tr["date"], y=tr["sessions_7d"], name="Sessions",
                             line=dict(color=BLUE, width=2.5)), row=1, col=1, secondary_y=False)
    fig.add_trace(go.Scatter(x=tr["date"], y=tr["revenue_7d"], name="Revenue (USD)",
                             line=dict(color=RED, width=2.5)), row=1, col=1, secondary_y=True)
    fig.update_yaxes(title_text="Sessions", rangemode="tozero", row=1, col=1, secondary_y=False)
    fig.update_yaxes(title_text="Revenue (USD)", tickprefix="$", showgrid=False, rangemode="tozero",
                     dtick=2000, row=1, col=1, secondary_y=True)
    fig.add_vrect(x0=REVENUE_CUTOFF, x1=tr["date"].max(), fillcolor="#999", opacity=0.12, line_width=0,
                  annotation_text="revenue not reported", annotation_position="top left", row=1, col=1)

    c = ch.sort_values("conversion_rate")
    fig.add_trace(go.Bar(x=c["conversion_rate"], y=c["channel"], orientation="h", showlegend=False,
                         marker_color=GREEN, text=[f"{v:.2%}" for v in c["conversion_rate"]],
                         textposition="outside", cliponaxis=False), 2, 1)
    r = ch.sort_values("revenue_per_session")
    fig.add_trace(go.Bar(x=r["revenue_per_session"], y=r["channel"], orientation="h", showlegend=False,
                         marker_color=PURPLE, text=[f"${v:.2f}" for v in r["revenue_per_session"]],
                         textposition="outside", cliponaxis=False), 2, 2)
    fig.update_xaxes(tickformat=".1%", range=[0, c["conversion_rate"].max() * 1.25], row=2, col=1)
    fig.update_xaxes(tickprefix="$", range=[0, r["revenue_per_session"].max() * 1.25], row=2, col=2)

    step_cols = [f"{a}->{b}" for a, b in zip(FUNNEL, FUNNEL[1:])]
    colors = {"desktop": BLUE, "mobile": ORANGE, "tablet": TEAL}
    for _, row in fn.iterrows():
        fig.add_trace(go.Bar(x=FUNNEL_LABELS, y=[row[s] for s in step_cols], name=str(row["device"]).title(),
                             marker_color=colors.get(row["device"]),
                             text=[f"{row[s]:.0%}" for s in step_cols], textposition="outside"), 3, 1)
    fig.update_yaxes(tickformat=".0%", range=[0, 1], row=3, col=1)

    top = lp.head(10).iloc[::-1]
    fig.add_trace(go.Bar(x=top["conversion_rate"], y=top["page"].str.slice(0, 60), orientation="h",
                         showlegend=False, marker_color=BLUE,
                         text=[f"{c:.2%}  ({n / 1000:.0f}k sessions)" for c, n in zip(top["conversion_rate"], top["sessions"])],
                         textposition="outside", cliponaxis=False), 4, 1)
    fig.update_xaxes(tickformat=".1%", range=[0, top["conversion_rate"].max() * 1.3], row=4, col=1)

    fig.update_layout(height=1700, template="plotly_white", barmode="group",
                      legend=dict(orientation="h", y=1.03, x=0.5, xanchor="center"),
                      margin=dict(t=60, l=60, r=40))
    return fig


# --------------------------------------------------------------------------------------
# PART 2: simulated campaign data
# --------------------------------------------------------------------------------------
def load_sim():
    if not SIM_FILE.exists():
        sys.exit(f"Missing {SIM_FILE.name}")
    return pd.read_csv(SIM_FILE, parse_dates=["date"])


def transform_sim(df):
    df = df.drop_duplicates().copy()
    df["month"] = df["date"].dt.to_period("M").astype(str)
    df["bounced"] = df["bounce_rate"] * df["sessions"]          # weight bounce rate by sessions

    ch = df.groupby("channel").agg(
        sessions=("sessions", "sum"), conversions=("conversions", "sum"), bounced=("bounced", "sum"),
        spend=("spend", "sum"), revenue=("revenue", "sum")).reset_index()
    ch["conversion_rate"] = ch["conversions"] / ch["sessions"]
    ch["bounce_rate"] = ch["bounced"] / ch["sessions"]
    ch["roas"] = ch["revenue"] / ch["spend"].replace(0, np.nan)   # only defined for paid channels
    ch = ch.sort_values("sessions", ascending=False).reset_index(drop=True)

    monthly = df.groupby("month").agg(sessions=("sessions", "sum"), conversions=("conversions", "sum")).reset_index()
    monthly["conversion_rate"] = monthly["conversions"] / monthly["sessions"]
    return {"rows": df, "channels": ch, "monthly": monthly}


def sim_findings(s):
    ch = s["channels"]
    top_traffic = ch.loc[ch["sessions"].idxmax()]
    top_conv = ch.loc[ch["conversion_rate"].idxmax()]
    top_bounce = ch.loc[ch["bounce_rate"].idxmax()]
    paid = ch.dropna(subset=["roas"])
    top_roas, low_roas = paid.loc[paid["roas"].idxmax()], paid.loc[paid["roas"].idxmin()]
    return [
        f"<b>Traffic vs conversion:</b> {top_traffic['channel']} drove the most traffic ({top_traffic['sessions']:,.0f} sessions) "
        f"but converted at {top_traffic['conversion_rate']:.2%}, well below {top_conv['channel']} ({top_conv['conversion_rate']:.2%}).",
        f"<b>Bounce:</b> {top_bounce['channel']} has the highest bounce rate ({top_bounce['bounce_rate']:.1%}), "
        f"pointing to a landing page or targeting problem for that traffic.",
        f"<b>Paid efficiency:</b> {top_roas['channel']} returns the most per ad dollar and {low_roas['channel']} the least "
        f"(ROAS {top_roas['roas']:.0f}x vs {low_roas['roas']:.0f}x).",
    ]


def sim_figure(s):
    ch, monthly = s["channels"], s["monthly"]
    fig = make_subplots(rows=2, cols=2, vertical_spacing=0.16, horizontal_spacing=0.14,
                        subplot_titles=("Monthly sessions", "Conversion rate by channel",
                                        "Bounce rate by channel", "ROAS by paid channel (illustrative)"))
    fig.add_trace(go.Scatter(x=monthly["month"], y=monthly["sessions"], mode="lines+markers",
                             line=dict(color=BLUE, width=2.5), showlegend=False), 1, 1)

    c = ch.sort_values("conversion_rate")
    fig.add_trace(go.Bar(x=c["conversion_rate"], y=c["channel"], orientation="h", marker_color=GREEN, showlegend=False,
                         text=[f"{v:.2%}" for v in c["conversion_rate"]], textposition="outside", cliponaxis=False), 1, 2)
    b = ch.sort_values("bounce_rate")
    fig.add_trace(go.Bar(x=b["bounce_rate"], y=b["channel"], orientation="h", marker_color=RED, showlegend=False,
                         text=[f"{v:.1%}" for v in b["bounce_rate"]], textposition="outside", cliponaxis=False), 2, 1)
    p = ch.dropna(subset=["roas"]).sort_values("roas")
    fig.add_trace(go.Bar(x=p["roas"], y=p["channel"], orientation="h", marker_color=ORANGE, showlegend=False,
                         text=[f"{v:.0f}x" for v in p["roas"]], textposition="outside", cliponaxis=False), 2, 2)

    fig.update_xaxes(tickformat=".0%", range=[0, c["conversion_rate"].max() * 1.2], row=1, col=2)
    fig.update_xaxes(tickformat=".0%", range=[0, b["bounce_rate"].max() * 1.2], row=2, col=1)
    fig.update_xaxes(range=[0, p["roas"].max() * 1.2], row=2, col=2)
    fig.update_layout(height=800, template="plotly_white", margin=dict(t=60, l=60, r=40))
    return fig


# --------------------------------------------------------------------------------------
# LOAD: write the combined dashboard
# --------------------------------------------------------------------------------------
PAGE = """<!doctype html><html><head><meta charset="utf-8"><title>Marketing Analytics Dashboard</title>
<style>body{{font-family:system-ui,sans-serif;max-width:1200px;margin:24px auto;padding:0 16px;color:#222}}
h1{{font-size:26px}}h2{{margin-top:40px;border-bottom:2px solid #eee;padding-bottom:6px}}
ul{{background:#f6f7f9;padding:16px 32px;border-radius:8px;line-height:1.6}}.note{{color:#666;font-size:14px}}</style>
</head><body>
<h1>Marketing Analytics Dashboard</h1>
<h2>Part 1: GA4 funnel and channel analysis (real data: Google Merchandise Store, Nov 2020 to Jan 2021)</h2>
<ul>{ga4_notes}</ul>{ga4_fig}
<h2>Part 2: Paid campaign performance (simulated data: 10,000 campaign rows, 2024)</h2>
<ul>{sim_notes}</ul>
<p class="note">The GA4 sample has no ad spend, so ROAS comes from this simulated dataset. Its spend values are
synthetic and unrealistically low, so compare ROAS across channels rather than reading the absolute numbers.</p>
{sim_fig}
</body></html>"""


def write_dashboard(ga4_notes, ga4_fig, sim_notes, sim_fig):
    html = PAGE.format(
        ga4_notes="".join(f"<li>{n}</li>" for n in ga4_notes),
        sim_notes="".join(f"<li>{n}</li>" for n in sim_notes),
        ga4_fig=ga4_fig.to_html(include_plotlyjs="cdn", full_html=False),
        sim_fig=sim_fig.to_html(include_plotlyjs=False, full_html=False),
    )
    OUT_FILE.write_text(html, encoding="utf-8")


def main():
    ga4 = transform_ga4(load_ga4())                      # Extract (CSV exports) + Transform
    sim = transform_sim(load_sim())

    ga4_notes, sim_notes = ga4_findings(ga4), sim_findings(sim)
    strip = lambda s: s.replace("<b>", "").replace("</b>", "")
    print("PART 1: GA4 (real data)")
    print("\n".join(f"  - {strip(n)}" for n in ga4_notes))
    print("\nPART 2: Simulated campaigns")
    print("\n".join(f"  - {strip(n)}" for n in sim_notes))

    write_dashboard(ga4_notes, ga4_figure(ga4), sim_notes, sim_figure(sim))   # Load
    print(f"\nDashboard saved to {OUT_FILE.name}")


if __name__ == "__main__":
    main()
