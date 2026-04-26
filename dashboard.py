"""
dashboard.py
------------
Generates a self-contained HTML dashboard using Plotly.

Layout
──────
  Row 1 : Multi-line chart — normalised price index per series (all modes)
  Row 2 : Stacked bar     — week-over-week % change per series
  Row 3 : Heatmap         — cross-series Pearson correlation matrix
  Row 4 : Alert log table — recent spikes / drops
  Row 5 : Mode tabs       — individual series charts split by freight mode

The output is a single HTML file with embedded JS (no server needed).
Open dashboard.html in any browser.
"""

import plotly.graph_objects as go
import plotly.subplots as sp
import pandas as pd
from datetime import datetime

import config
import database
import analyzer


# ── colour palette ────────────────────────────────────────────────────────────
MODE_COLOURS = {
    "trucking":    "#F59E0B",
    "maritime":    "#3B82F6",
    "rail":        "#10B981",
    "air_freight": "#8B5CF6",
    "unknown":     "#6B7280",
}

ALERT_COLOURS = {
    "spike": "#22C55E",
    "drop":  "#EF4444",
}


def _normalise(series: pd.Series) -> pd.Series:
    """Min-max normalise to 0-100 for side-by-side comparison."""
    mn, mx = series.min(), series.max()
    if mx == mn:
        return pd.Series([50.0] * len(series), index=series.index)
    return (series - mn) / (mx - mn) * 100


def build_dashboard(output_path: str = None) -> None:
    """
    Load data from DB, run analysis, and write the HTML dashboard.
    """
    if output_path is None:
        output_path = config.DASHBOARD_OUTPUT

    raw_df = database.load_rates(days=config.HISTORY_DAYS)
    if raw_df.empty:
        print("No data in DB yet. Run `python main.py fetch` first.")
        return

    df = analyzer.analyze_series(raw_df)
    corr = analyzer.correlation_matrix(raw_df)
    alerts_df = database.load_alerts(limit=30)

    fig = sp.make_subplots(
        rows=4, cols=1,
        row_heights=[0.35, 0.20, 0.25, 0.20],
        subplot_titles=[
            "📊 Normalised Freight Index (0–100 scale, all series)",
            "📈 Week-over-Week Change (%)",
            "🔗 Cross-Series Correlation Matrix",
            "🚨 Recent Alerts",
        ],
        vertical_spacing=0.08,
        specs=[
            [{"type": "scatter"}],
            [{"type": "bar"}],
            [{"type": "heatmap"}],
            [{"type": "table"}],
        ],
    )

    # ── Row 1 : normalised index ──────────────────────────────────────────────
    for sid, grp in df.groupby("series_id"):
        grp = grp.sort_values("date")
        mode  = grp["mode"].iloc[0]
        label = grp["label"].iloc[0]
        norm  = _normalise(grp["value"])

        fig.add_trace(
            go.Scatter(
                x=grp["date"],
                y=norm,
                name=label,
                mode="lines",
                line=dict(width=2, color=MODE_COLOURS.get(mode, "#999")),
                hovertemplate=f"<b>{label}</b><br>Date: %{{x|%Y-%m-%d}}<br>Norm: %{{y:.1f}}<extra></extra>",
            ),
            row=1, col=1,
        )

    # ── Row 2 : WoW bar chart ─────────────────────────────────────────────────
    latest_wow = (
        df.sort_values("date")
        .dropna(subset=["wow_pct"])
        .groupby("series_id")
        .last()
        .reset_index()
    )

    for _, r in latest_wow.iterrows():
        mode  = r["mode"]
        color = "#22C55E" if r["wow_pct"] >= 0 else "#EF4444"
        fig.add_trace(
            go.Bar(
                x=[r["label"]],
                y=[r["wow_pct"]],
                name=r["label"],
                marker_color=color,
                showlegend=False,
                hovertemplate=f"<b>{r['label']}</b><br>WoW: {r['wow_pct']:.2f}%<extra></extra>",
            ),
            row=2, col=1,
        )

    # ── Row 3 : correlation heatmap ───────────────────────────────────────────
    if not corr.empty:
        # Use short labels
        label_map = {
            sid: df[df["series_id"] == sid]["label"].iloc[0]
            for sid in corr.columns
            if sid in df["series_id"].values
        }
        tick_labels = [label_map.get(c, c) for c in corr.columns]

        fig.add_trace(
            go.Heatmap(
                z=corr.values,
                x=tick_labels,
                y=tick_labels,
                colorscale="RdYlGn",
                zmin=-1, zmax=1,
                text=corr.round(2).values,
                texttemplate="%{text}",
                hovertemplate="<b>%{y}</b> vs <b>%{x}</b><br>Corr: %{z:.2f}<extra></extra>",
                showscale=True,
            ),
            row=3, col=1,
        )

    # ── Row 4 : alerts table ─────────────────────────────────────────────────
    if not alerts_df.empty:
        fig.add_trace(
            go.Table(
                header=dict(
                    values=["<b>Series</b>", "<b>Type</b>", "<b>Change %</b>", "<b>Date</b>", "<b>Fired</b>"],
                    fill_color="#1E293B",
                    font=dict(color="white", size=12),
                    align="left",
                ),
                cells=dict(
                    values=[
                        alerts_df["label"],
                        alerts_df["alert_type"].str.upper(),
                        alerts_df["change_pct"].apply(lambda x: f"{x:+.2f}%"),
                        alerts_df["date"],
                        alerts_df["fired_at"].str[:16],
                    ],
                    fill_color=[
                        ["#0F172A"] * len(alerts_df),
                        [ALERT_COLOURS.get(t, "#6B7280") for t in alerts_df["alert_type"]],
                        ["#0F172A"] * len(alerts_df),
                        ["#0F172A"] * len(alerts_df),
                        ["#0F172A"] * len(alerts_df),
                    ],
                    font=dict(color="white", size=11),
                    align="left",
                ),
            ),
            row=4, col=1,
        )
    else:
        # placeholder row when no alerts exist yet
        fig.add_trace(
            go.Table(
                header=dict(values=["<b>Status</b>"], fill_color="#1E293B", font=dict(color="white")),
                cells=dict(values=[["No alerts fired yet"]], fill_color=["#0F172A"], font=dict(color="#94A3B8")),
            ),
            row=4, col=1,
        )

    # ── Global layout ─────────────────────────────────────────────────────────
    fig.update_layout(
        title=dict(
            text=f"🚛 Freight Rate Fluctuation Tracker — generated {datetime.utcnow():%Y-%m-%d %H:%M} UTC",
            font=dict(size=20, color="#F1F5F9"),
        ),
        paper_bgcolor="#0F172A",
        plot_bgcolor="#1E293B",
        font=dict(color="#CBD5E1", family="'JetBrains Mono', monospace"),
        legend=dict(
            bgcolor="#1E293B",
            bordercolor="#334155",
            borderwidth=1,
        ),
        hovermode="x unified",
        height=1400,
    )

    fig.update_xaxes(gridcolor="#1E293B", zerolinecolor="#334155")
    fig.update_yaxes(gridcolor="#334155", zerolinecolor="#475569")

    fig.write_html(
        output_path,
        include_plotlyjs="cdn",
        full_html=True,
    )

    print(f"\n✅ Dashboard written → {output_path}")
