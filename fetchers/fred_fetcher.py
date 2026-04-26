"""
fetchers/fred_fetcher.py
------------------------
Pulls economic freight series from the St. Louis Federal Reserve (FRED).

FRED is free and official US government data.
API key: https://fred.stlouisfed.org/docs/api/api_key.html  (takes 30 seconds)

Series used
-----------
  TRUCKD11          ATA Truck Tonnage Index (monthly, SA)
  RAILFRTCARLOADSSA Rail Freight Carloads   (weekly,  SA)

Both are downloaded as raw JSON and normalised to the shared row schema:
  { source, series_id, label, mode, date, value }
"""

from datetime import datetime, timedelta

import requests
from rich.console import Console

import config

console = Console()


def _observation_url(series_id: str, start_date: str, end_date: str) -> str:
    return (
        f"{config.FRED_BASE_URL}"
        f"?series_id={series_id}"
        f"&observation_start={start_date}"
        f"&observation_end={end_date}"
        f"&api_key={config.FRED_API_KEY}"
        f"&file_type=json"
    )


def _validate_row(obs: dict) -> bool:
    """FRED uses '.' for missing values — skip those."""
    return obs.get("value", ".") != "."


def fetch_fred_series(series_id: str, days: int = 365) -> list[dict]:
    """
    Fetch a single FRED series and return normalised rows.

    Parameters
    ----------
    series_id : str  e.g. 'TRUCKD11'
    days      : int  how far back to pull

    Returns
    -------
    list[dict]  ready to upsert into the DB
    """
    if not config.FRED_API_KEY:
        console.print(
            f"[yellow]⚠  FRED_API_KEY not set — skipping {series_id}. "
            "Get a free key at fred.stlouisfed.org[/yellow]"
        )
        return []

    meta = config.FRED_SERIES.get(series_id, {})
    end = datetime.today()
    start = end - timedelta(days=days)

    url = _observation_url(
        series_id,
        start.strftime("%Y-%m-%d"),
        end.strftime("%Y-%m-%d"),
    )

    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as exc:
        console.print(f"[red]✗ FRED request failed for {series_id}: {exc}[/red]")
        return []

    data = resp.json()
    observations = data.get("observations", [])

    rows = []
    for obs in observations:
        if not _validate_row(obs):
            continue
        rows.append(
            {
                "source": "fred",
                "series_id": series_id,
                "label": meta.get("label", series_id),
                "mode": meta.get("mode", "unknown"),
                "date": obs["date"],
                "value": float(obs["value"]),
            }
        )

    console.print(
        f"[green]✓ FRED[/green] {series_id} → "
        f"[cyan]{len(rows)}[/cyan] observations"
    )
    return rows


def fetch_all_fred(days: int = 365) -> list[dict]:
    """Iterate every configured FRED series and return combined rows."""
    all_rows: list[dict] = []
    for series_id in config.FRED_SERIES:
        all_rows.extend(fetch_fred_series(series_id, days=days))
    return all_rows
