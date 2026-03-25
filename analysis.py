"""
Digital Marketing Campaign Analytics
=====================================
Author: You
Dataset: 10,000 rows of simulated web traffic & campaign data
Tools: Pandas, Plotly
"""

import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import warnings
warnings.filterwarnings('ignore')

# ─────────────────────────────────────────
# 1. LOAD & CLEAN
# ─────────────────────────────────────────
df = pd.read_csv('/mnt/user-data/outputs/marketing_data.csv', parse_dates=['date'])

print("=" * 55)
print("STEP 1: DATA OVERVIEW")
print("=" * 55)
print(f"Shape        : {df.shape[0]:,} rows × {df.shape[1]} columns")
print(f"Date range   : {df['date'].min().date()} → {df['date'].max().date()}")
print(f"Null values  : {df.isnull().sum().sum()}")
print(f"Channels     : {sorted(df['channel'].unique())}")

# Basic cleaning
df = df.drop_duplicates()
df['month'] = df['date'].dt.to_period('M').astype(str)
df['week']  = df['date'].dt.to_period('W').astype(str)
df['roas']  = (df['revenue'] / df['spend'].replace(0, np.nan)).round(2)  # Return on Ad Spend

# ─────────────────────────────────────────
# 2. CHANNEL-LEVEL INSIGHTS
# ─────────────────────────────────────────
print("\n" + "=" * 55)
print("STEP 2: CHANNEL PERFORMANCE SUMMARY")
print("=" * 55)

channel_summary = df.groupby('channel').agg(
    total_sessions  = ('sessions',    'sum'),
    total_conversions=('conversions', 'sum'),
    avg_bounce_rate = ('bounce_rate', 'mean'),
    total_spend     = ('spend',       'sum'),
    total_revenue   = ('revenue',     'sum'),
).reset_index()

channel_summary['conv_rate_%'] = (
    channel_summary['total_conversions'] / channel_summary['total_sessions'] * 100
).round(2)
channel_summary['roas'] = (
    channel_summary['total_revenue'] / channel_summary['total_spend'].replace(0, np.nan)
).round(2)
channel_summary['avg_bounce_rate'] = (channel_summary['avg_bounce_rate'] * 100).round(1)

channel_summary = channel_summary.sort_values('total_sessions', ascending=False)
print(channel_summary[[
    'channel','total_sessions','conv_rate_%','avg_bounce_rate','roas'
]].to_string(index=False))

# ─────────────────────────────────────────
# 3. KEY INSIGHTS
# ─────────────────────────────────────────
top_traffic  = channel_summary.loc[channel_summary['total_sessions'].idxmax(), 'channel']
top_conv     = channel_summary.loc[channel_summary['conv_rate_%'].idxmax(), 'channel']
top_bounce   = channel_summary.loc[channel_summary['avg_bounce_rate'].idxmax(), 'channel']
top_roas     = channel_summary.dropna(subset=['roas']).loc[
                   channel_summary.dropna(subset=['roas'])['roas'].idxmax(), 'channel']

print("\n" + "=" * 55)
print("STEP 3: KEY INSIGHTS")
print("=" * 55)
print(f"🚦 Highest traffic     → {top_traffic}")
print(f"✅ Best conversion rate → {top_conv}")
print(f"📉 Highest bounce rate  → {top_bounce}")
print(f"💰 Best ROAS            → {top_roas}")

# ─────────────────────────────────────────
# 4. MONTHLY TREND
# ─────────────────────────────────────────
monthly = df.groupby('month').agg(
    sessions    = ('sessions',    'sum'),
    conversions = ('conversions', 'sum'),
).reset_index()
monthly['conv_rate'] = (monthly['conversions'] / monthly['sessions'] * 100).round(2)

# ─────────────────────────────────────────
# 5. BUILD DASHBOARD (Plotly)
# ─────────────────────────────────────────
COLORS = {
    'Google Ads':     '#4285F4',
    'Organic Search': '#34A853',
    'Instagram':      '#E1306C',
    'Email':          '#FF6D00',
    'Facebook':       '#1877F2',
    'Direct':         '#6D4C41',
    'YouTube':        '#FF0000',
}
BG    = '#0F1117'
CARD  = '#1A1D27'
TEXT  = '#E8EAF0'
GRID  = '#2A2D3A'
ACCENT= '#00D4FF'

fig = make_subplots(
    rows=3, cols=2,
    subplot_titles=(
        'Monthly Sessions Over Time',
        'Conversion Rate by Channel (%)',
        'Bounce Rate by Channel (%)',
        'Sessions vs Conversions (bubble = revenue)',
        'Monthly Conversion Rate Trend',
        'ROAS by Paid Channel',
    ),
    vertical_spacing=0.13,
    horizontal_spacing=0.10,
)

# ── Plot 1: Monthly sessions line ──
fig.add_trace(go.Scatter(
    x=monthly['month'], y=monthly['sessions'],
    mode='lines+markers',
    line=dict(color=ACCENT, width=2.5),
    marker=dict(size=6, color=ACCENT),
    fill='tozeroy', fillcolor='rgba(0,212,255,0.08)',
    name='Sessions',
), row=1, col=1)

# ── Plot 2: Conv rate bar (sorted) ──
cv = channel_summary.sort_values('conv_rate_%')
bar_colors = [COLORS.get(c, '#888') for c in cv['channel']]
fig.add_trace(go.Bar(
    x=cv['conv_rate_%'], y=cv['channel'],
    orientation='h',
    marker_color=bar_colors,
    text=[f"{v}%" for v in cv['conv_rate_%']],
    textposition='outside',
    name='Conv Rate',
), row=1, col=2)

# ── Plot 3: Bounce rate bar ──
br = channel_summary.sort_values('avg_bounce_rate')
fig.add_trace(go.Bar(
    x=br['avg_bounce_rate'], y=br['channel'],
    orientation='h',
    marker_color=[COLORS.get(c,'#888') for c in br['channel']],
    text=[f"{v}%" for v in br['avg_bounce_rate']],
    textposition='outside',
    name='Bounce Rate',
), row=2, col=1)

# ── Plot 4: Bubble chart ──
for _, row_data in channel_summary.iterrows():
    fig.add_trace(go.Scatter(
        x=[row_data['total_sessions']],
        y=[row_data['total_conversions']],
        mode='markers+text',
        marker=dict(
            size=np.sqrt(row_data['total_revenue'] / 500),
            color=COLORS.get(row_data['channel'], '#888'),
            opacity=0.85,
            line=dict(color='white', width=1),
        ),
        text=[row_data['channel']],
        textposition='top center',
        textfont=dict(size=9, color=TEXT),
        name=row_data['channel'],
        showlegend=False,
    ), row=2, col=2)

# ── Plot 5: Monthly conv rate ──
fig.add_trace(go.Scatter(
    x=monthly['month'], y=monthly['conv_rate'],
    mode='lines+markers',
    line=dict(color='#FFD700', width=2.5, dash='dot'),
    marker=dict(size=6, color='#FFD700'),
    name='Conv Rate %',
), row=3, col=1)

# ── Plot 6: ROAS bar ──
paid = channel_summary.dropna(subset=['roas']).sort_values('roas')
fig.add_trace(go.Bar(
    x=paid['roas'], y=paid['channel'],
    orientation='h',
    marker_color=[COLORS.get(c,'#888') for c in paid['channel']],
    text=[f"{v}x" for v in paid['roas']],
    textposition='outside',
    name='ROAS',
), row=3, col=2)

# ── Global layout ──
fig.update_layout(
    title=dict(
        text='Digital Marketing Analytics Dashboard · 2024',
        font=dict(size=22, color=TEXT, family='Georgia'),
        x=0.5,
    ),
    paper_bgcolor=BG,
    plot_bgcolor=CARD,
    font=dict(color=TEXT, size=11),
    showlegend=False,
    height=1000,
    margin=dict(l=60, r=60, t=80, b=40),
)

# Axis styling
for row in range(1, 4):
    for col in range(1, 3):
        fig.update_xaxes(
            gridcolor=GRID, linecolor=GRID,
            tickfont=dict(color=TEXT, size=9),
            row=row, col=col,
        )
        fig.update_yaxes(
            gridcolor=GRID, linecolor=GRID,
            tickfont=dict(color=TEXT, size=9),
            row=row, col=col,
        )

for ann in fig.layout.annotations:
    ann.font.color = ACCENT
    ann.font.size  = 12

fig.write_html('/mnt/user-data/outputs/dashboard.html')
print("\n✅ Dashboard saved → dashboard.html")

# ─────────────────────────────────────────
# 6. FINAL INSIGHTS REPORT
# ─────────────────────────────────────────
print("\n" + "=" * 55)
print("FINAL INSIGHTS (use these in your portfolio/interview)")
print("=" * 55)
top3 = channel_summary.nlargest(3, 'total_sessions')
for _, r in top3.iterrows():
    print(f"  • {r['channel']:18s} | {r['total_sessions']:,} sessions | "
          f"{r['conv_rate_%']}% conv | {r['avg_bounce_rate']}% bounce")
print(f"\n  Best conversion channel : {top_conv}")
print(f"  Best ROAS channel       : {top_roas}")
print(f"  Highest bounce channel  : {top_bounce}")
print("\n  Recruiter-ready bullets:")
print(f"  → '{top_traffic} drove highest traffic but had a lower conv rate than {top_conv}'")
print(f"  → '{top_conv} campaigns achieved the highest conversion rate across all channels'")
print(f"  → '{top_bounce} showed highest bounce rate, signaling landing page optimisation opportunity'")
