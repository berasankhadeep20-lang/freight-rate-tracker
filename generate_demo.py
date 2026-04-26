"""
generate_demo.py
----------------
Seeds the DB with synthetic-but-realistic freight data so the
dashboard renders immediately on GitHub Pages before CI runs.

Run once locally:  python generate_demo.py
"""

import random
import math
from datetime import datetime, timedelta

import database
import config

config.DASHBOARD_OUTPUT = "docs/index.html"

random.seed(42)

def _walk(start: float, days: int, vol: float = 0.012, drift: float = 0.0002) -> list[float]:
    """Geometric random walk — realistic price-like series."""
    vals = [start]
    for _ in range(days - 1):
        shock = random.gauss(drift, vol)
        # Add a little seasonality
        t = len(vals)
        seasonal = 0.003 * math.sin(2 * math.pi * t / 252)
        vals.append(vals[-1] * math.exp(shock + seasonal))
    return vals

SYNTHETIC_SERIES = {
    "BDRY": {
        "label": "Baltic Dry Index ETF",
        "mode": "maritime",
        "start": 9.50,
        "vol": 0.022,
    },
    "BOAT": {
        "label": "Global Shipping ETF",
        "mode": "maritime",
        "start": 24.10,
        "vol": 0.014,
    },
    "ZIM": {
        "label": "ZIM Integrated Shipping",
        "mode": "maritime",
        "start": 18.30,
        "vol": 0.028,
    },
    "SBLK": {
        "label": "Star Bulk Carriers",
        "mode": "maritime",
        "start": 14.75,
        "vol": 0.018,
    },
    "FWRD": {
        "label": "Forward Air Corp",
        "mode": "air_freight",
        "start": 22.00,
        "vol": 0.015,
    },
    "XPO": {
        "label": "XPO Logistics",
        "mode": "trucking",
        "start": 112.40,
        "vol": 0.013,
    },
    "TRUCKD11": {
        "label": "ATA Truck Tonnage Index",
        "mode": "trucking",
        "start": 116.2,
        "vol": 0.006,
        "freq": "monthly",
    },
    "RAILFRTCARLOADSSA": {
        "label": "Rail Freight Carloads (SA)",
        "mode": "rail",
        "start": 472.0,
        "vol": 0.007,
        "freq": "weekly",
    },
}

def generate():
    database.init_db()
    rows = []
    today = datetime.today()
    days = 365

    for sid, meta in SYNTHETIC_SERIES.items():
        freq = meta.get("freq", "daily")

        if freq == "daily":
            dates = [today - timedelta(days=i) for i in range(days, 0, -1)]
        elif freq == "weekly":
            dates = [today - timedelta(weeks=i) for i in range(days // 7, 0, -1)]
        else:  # monthly
            dates = [today - timedelta(days=30 * i) for i in range(12, 0, -1)]

        n = len(dates)
        values = _walk(meta["start"], n, vol=meta["vol"])

        for d, v in zip(dates, values):
            rows.append({
                "source": "demo",
                "series_id": sid,
                "label": meta["label"],
                "mode": meta["mode"],
                "date": d.strftime("%Y-%m-%d"),
                "value": round(v, 4),
            })

    inserted = database.upsert_rates(rows)
    print(f"✅ Seeded {inserted} demo rows")

    import dashboard
    dashboard.build_dashboard(output_path="docs/index.html")
    print("✅ Demo dashboard written → docs/index.html")

if __name__ == "__main__":
    generate()
