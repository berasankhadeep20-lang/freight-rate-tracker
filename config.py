import os
from dotenv import load_dotenv

load_dotenv()

# ─── FRED API ────────────────────────────────────────────────────────────────
# Free key → https://fred.stlouisfed.org/docs/api/api_key.html
FRED_API_KEY = os.getenv("FRED_API_KEY", "")
FRED_BASE_URL = "https://api.stlouisfed.org/fred/series/observations"

# FRED Series tracked
# Each series_id maps to a human label + mode (trucking / maritime / air / rail)
FRED_SERIES = {
    "TRUCKD11": {
        "label": "ATA Truck Tonnage Index",
        "mode": "trucking",
        "unit": "Index (2015=100)",
        "description": "Seasonally adjusted tonnage hauled by US for-hire truckers",
        "frequency": "monthly",
    },
    "RAILFRTCARLOADSSA": {
        "label": "Rail Freight Carloads (SA)",
        "mode": "rail",
        "unit": "Thousands of Carloads",
        "description": "US rail freight carloads, seasonally adjusted",
        "frequency": "weekly",
    },
}

# ─── MARKET PROXIES (via yfinance, no key needed) ─────────────────────────────
# These are publicly traded instruments whose price closely tracks freight indices
MARKET_TICKERS = {
    "BDRY": {
        "label": "Baltic Dry Index ETF",
        "mode": "maritime",
        "description": "Breakwave Dry Bulk Shipping ETF — tracks Baltic Dry Index (BDI)",
        "type": "etf",
    },
    "BOAT": {
        "label": "Global Shipping ETF",
        "mode": "maritime",
        "description": "SonicShares Global Shipping ETF — broad container shipping exposure",
        "type": "etf",
    },
    "ZIM": {
        "label": "ZIM Integrated Shipping",
        "mode": "maritime",
        "description": "ZIM container shipping stock — sensitive to spot rate swings",
        "type": "stock",
    },
    "SBLK": {
        "label": "Star Bulk Carriers",
        "mode": "maritime",
        "description": "Dry bulk carrier — tracks BDI closely",
        "type": "stock",
    },
    "FWRD": {
        "label": "Forward Air Corp",
        "mode": "air_freight",
        "description": "Air freight & expedited LTL — US air cargo rate proxy",
        "type": "stock",
    },
    "XPO": {
        "label": "XPO Logistics",
        "mode": "trucking",
        "description": "LTL trucking giant — US truck freight proxy",
        "type": "stock",
    },
}

# ─── ALERT THRESHOLDS ─────────────────────────────────────────────────────────
ALERT_THRESHOLD_PCT = float(os.getenv("ALERT_THRESHOLD_PCT", "5.0"))  # % weekly change

# ─── DATABASE ─────────────────────────────────────────────────────────────────
DB_PATH = os.getenv("DB_PATH", "freight_data.db")

# ─── FETCH WINDOW ─────────────────────────────────────────────────────────────
HISTORY_DAYS = int(os.getenv("HISTORY_DAYS", "365"))  # 1 year default

# ─── DASHBOARD OUTPUT ─────────────────────────────────────────────────────────
DASHBOARD_OUTPUT = os.getenv("DASHBOARD_OUTPUT", "dashboard.html")
