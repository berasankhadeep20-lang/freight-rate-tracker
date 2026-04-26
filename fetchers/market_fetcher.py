"""
fetchers/market_fetcher.py
--------------------------
Pulls freight-proxy market data via yfinance (no API key needed).

Why market proxies?
-------------------
  Real freight rate databases (Freightos, DAT, Baltic Exchange) cost
  thousands per month.  Publicly traded ETFs and stocks that derive their
  value directly from freight rates are a *free* real-time proxy:

  Instrument   Tracks
  ──────────── ────────────────────────────────────────────────────────
  BDRY         Baltic Dry Index (BDI) — dry bulk shipping spot rates
  BOAT         Global container shipping basket
  ZIM          Container spot rate sentiment (reports quarterly)
  SBLK         Dry bulk carrier — BDI corr > 0.85 historically
  FWRD         Air freight / expedited LTL trucking
  XPO          LTL truck-rate environment

The returned rows share the same schema as FRED rows so the DB layer
never needs to know which source it's looking at.
"""

from datetime import datetime, timedelta

import yfinance as yf
import pandas as pd
from rich.console import Console

import config

console = Console()


def fetch_ticker(ticker: str, days: int = 365) -> list[dict]:
    """
    Download daily adjusted close prices for one ticker.

    Parameters
    ----------
    ticker : str   e.g. 'BDRY'
    days   : int   look-back window in calendar days

    Returns
    -------
    list[dict]  normalised rows ready for DB upsert
    """
    meta = config.MARKET_TICKERS.get(ticker, {})
    end = datetime.today()
    start = end - timedelta(days=days)

    try:
        df: pd.DataFrame = yf.download(
            ticker,
            start=start.strftime("%Y-%m-%d"),
            end=end.strftime("%Y-%m-%d"),
            auto_adjust=True,
            progress=False,
            # suppress the multi-level column header yfinance adds
        )
    except Exception as exc:
        console.print(f"[red]✗ yfinance failed for {ticker}: {exc}[/red]")
        return []

    if df.empty:
        console.print(f"[yellow]⚠  No data returned for {ticker}[/yellow]")
        return []

    # yfinance ≥ 0.2.x returns MultiIndex columns — flatten them
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [col[0] for col in df.columns]

    close_col = "Close"
    if close_col not in df.columns:
        console.print(f"[yellow]⚠  'Close' column missing for {ticker}[/yellow]")
        return []

    rows = []
    for date_idx, row in df.iterrows():
        close_val = row[close_col]
        if pd.isna(close_val):
            continue
        rows.append(
            {
                "source": "market",
                "series_id": ticker,
                "label": meta.get("label", ticker),
                "mode": meta.get("mode", "unknown"),
                "date": date_idx.strftime("%Y-%m-%d"),
                "value": round(float(close_val), 4),
            }
        )

    console.print(
        f"[green]✓ Market[/green] {ticker:6s} → "
        f"[cyan]{len(rows)}[/cyan] trading days"
    )
    return rows


def fetch_all_market(days: int = 365) -> list[dict]:
    """Fetch every configured market ticker and return combined rows."""
    all_rows: list[dict] = []
    for ticker in config.MARKET_TICKERS:
        all_rows.extend(fetch_ticker(ticker, days=days))
    return all_rows
