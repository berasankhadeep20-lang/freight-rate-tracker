"""
analyzer.py
-----------
Statistical analysis layer.

What it does
────────────
1. Week-over-week (WoW) change detection per series
2. Spike / drop alerting when |WoW %| exceeds threshold (default 5 %)
3. Rolling 4-week moving average + Z-score for anomaly scoring
4. Correlation matrix across all active series (cross-modal insight)
5. Trend summary table printed to the terminal via Rich

All analysis runs purely on DataFrames — no model weights, no external calls.
"""

import numpy as np
import pandas as pd
from rich.console import Console
from rich.table import Table

import config
import database

console = Console()


# ── helpers ──────────────────────────────────────────────────────────────────

def _wow_change(series: pd.Series) -> pd.Series:
    """
    Week-over-week percentage change.
    For daily data  → shift(5)  (5 trading days ≈ 1 week)
    For monthly data → shift(1)
    We infer frequency from the median date gap.
    """
    if len(series) < 2:
        return pd.Series(dtype=float)

    dates = series.index
    median_gap = (dates[1:] - dates[:-1]).median().days

    shift_n = 5 if median_gap <= 5 else 1          # daily vs monthly
    pct = series.pct_change(periods=shift_n) * 100
    return pct


def _rolling_zscore(series: pd.Series, window: int = 20) -> pd.Series:
    """
    Z-score relative to a rolling window.
    |Z| > 2 → statistically unusual move.
    """
    roll_mean = series.rolling(window, min_periods=3).mean()
    roll_std  = series.rolling(window, min_periods=3).std()
    return (series - roll_mean) / (roll_std + 1e-9)


# ── main analysis functions ───────────────────────────────────────────────────

def analyze_series(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add derived columns to a rates DataFrame.

    Input columns : series_id, label, mode, date, value
    Added columns : wow_pct, ma4w, zscore
    """
    if df.empty:
        return df

    results = []
    for sid, grp in df.groupby("series_id"):
        grp = grp.sort_values("date").set_index("date")
        grp["wow_pct"] = _wow_change(grp["value"])
        grp["ma4w"]    = grp["value"].rolling(window=20, min_periods=3).mean()
        grp["zscore"]  = _rolling_zscore(grp["value"])
        grp = grp.reset_index()
        results.append(grp)

    return pd.concat(results, ignore_index=True) if results else df


def detect_alerts(df: pd.DataFrame, threshold_pct: float = None) -> list[dict]:
    """
    Scan latest WoW move for each series and return alerts.

    Parameters
    ----------
    df            : output of analyze_series()
    threshold_pct : fire an alert if |wow_pct| >= this value

    Returns
    -------
    list[dict]   alert records (also written to DB)
    """
    if threshold_pct is None:
        threshold_pct = config.ALERT_THRESHOLD_PCT

    fired: list[dict] = []
    if df.empty or "wow_pct" not in df.columns:
        return fired

    for sid, grp in df.groupby("series_id"):
        grp = grp.sort_values("date")
        last_row = grp.dropna(subset=["wow_pct"]).iloc[-1] if not grp.dropna(subset=["wow_pct"]).empty else None
        if last_row is None:
            continue

        pct = last_row["wow_pct"]
        if abs(pct) >= threshold_pct:
            alert_type = "spike" if pct > 0 else "drop"
            alert = {
                "series_id":  sid,
                "label":      last_row["label"],
                "alert_type": alert_type,
                "change_pct": round(pct, 2),
                "date":       str(last_row["date"].date()),
            }
            fired.append(alert)
            database.log_alert(**alert)

    return fired


def correlation_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """
    Pivot all series to a date × series matrix and compute Pearson correlation.
    Useful for spotting cross-modal freight contagion (e.g. BDI spike → trucking lag).
    """
    if df.empty:
        return pd.DataFrame()

    pivot = df.pivot_table(index="date", columns="series_id", values="value")
    return pivot.pct_change().corr().round(3)


def summary_table(df: pd.DataFrame) -> None:
    """Print a Rich terminal table with the latest reading per series."""
    if df.empty:
        console.print("[yellow]No data to display.[/yellow]")
        return

    latest = (
        df.sort_values("date")
        .groupby("series_id")
        .last()
        .reset_index()
    )

    table = Table(title="📦 Freight Rate Summary (latest readings)", border_style="dim")
    table.add_column("Series",     style="bold cyan",   no_wrap=True)
    table.add_column("Mode",       style="magenta")
    table.add_column("Date",       style="white")
    table.add_column("Value",      justify="right", style="bold white")
    table.add_column("WoW %",      justify="right")
    table.add_column("Z-Score",    justify="right")

    for _, row in latest.iterrows():
        wow  = row.get("wow_pct", float("nan"))
        zscore = row.get("zscore", float("nan"))

        wow_str = (
            f"[green]+{wow:.1f}%[/green]" if wow > 0
            else f"[red]{wow:.1f}%[/red]" if wow < 0
            else "—"
        ) if not pd.isna(wow) else "—"

        z_str = f"{zscore:.2f}" if not pd.isna(zscore) else "—"

        table.add_row(
            row["label"],
            row["mode"],
            str(row["date"].date()),
            f"{row['value']:.4f}",
            wow_str,
            z_str,
        )

    console.print(table)
