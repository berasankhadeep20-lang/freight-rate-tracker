# 🚛 freight-rate-tracker

> Real-time freight rate fluctuation tracker using public market proxies and FRED economic data. Auto-deploys a live Plotly dashboard to GitHub Pages every 6 hours via GitHub Actions.

**Live Dashboard →** `https://<your-username>.github.io/freight-rate-tracker/`

---

## What it tracks

| Series | Mode | Source | Why |
|---|---|---|---|
| BDRY | Maritime | yfinance | Baltic Dry Index ETF — spot dry bulk shipping |
| BOAT | Maritime | yfinance | Global container shipping basket |
| ZIM | Maritime | yfinance | Container spot rate sentiment |
| SBLK | Maritime | yfinance | Dry bulk carrier — BDI corr > 0.85 |
| FWRD | Air Freight | yfinance | Expedited LTL / air cargo proxy |
| XPO | Trucking | yfinance | LTL truck-rate environment |
| TRUCKD11 | Trucking | FRED | ATA Truck Tonnage Index (monthly, SA) |
| RAILFRTCARLOADSSA | Rail | FRED | US Rail Freight Carloads (weekly, SA) |

---

## Dashboard features

- **Normalised index chart** — all series on the same 0–100 scale for cross-modal comparison
- **Week-over-week bar chart** — green/red bars per series showing recent momentum
- **Correlation heatmap** — Pearson correlation matrix across all series (spot cross-modal contagion)
- **Alert log** — table of all fired spike/drop events
- **Auto-refresh** — GitHub Actions re-fetches every 6 hours and redeploys

---

## Quick start (local)

```bash
# 1. Clone
git clone https://github.com/<you>/freight-rate-tracker
cd freight-rate-tracker

# 2. Install deps
pip install -r requirements.txt

# 3. Configure
cp .env.example .env
# Edit .env and add your FRED_API_KEY (free at fred.stlouisfed.org)

# 4. Fetch real data + generate dashboard
python main.py fetch
open dashboard.html

# 5. Run on a schedule (blocks — fetches every 6 hours)
python main.py schedule
```

### All CLI commands

```
python main.py fetch      # Fetch data, run analysis, print table, build dashboard
python main.py dash       # Rebuild dashboard from existing DB (no fetch)
python main.py alerts     # Print recent alerts
python main.py schedule   # Block + run fetch every 6 hours
python main.py reset      # Wipe DB
```

---

## Deploy to GitHub Pages (one-time setup)

### Step 1 — Create the repo

```bash
git init
git remote add origin https://github.com/<you>/freight-rate-tracker
git add .
git commit -m "feat: initial commit"
git push -u origin main
```

### Step 2 — Add the FRED API key as a secret

1. Go to your repo → **Settings** → **Secrets and variables** → **Actions**
2. Click **New repository secret**
3. Name: `FRED_API_KEY`
4. Value: your key from [fred.stlouisfed.org](https://fred.stlouisfed.org/docs/api/api_key.html)

> yfinance (market data) needs no key — it's always free.

### Step 3 — Enable GitHub Pages

1. Go to **Settings** → **Pages**
2. Source: **Deploy from a branch**
3. Branch: `gh-pages` / `/ (root)`
4. Save

### Step 4 — Trigger the first run

Go to **Actions** → **Freight Tracker — Fetch & Deploy** → **Run workflow**

Your live dashboard will be at:
```
https://<your-username>.github.io/freight-rate-tracker/
```

The workflow runs automatically at `0 */6 * * *` (every 6 hours, UTC).

---

## How it works

```
main.py
  ├── fetchers/
  │   ├── market_fetcher.py   yfinance → daily OHLCV for 6 tickers
  │   └── fred_fetcher.py     FRED API → economic series (monthly/weekly)
  ├── database.py             SQLite persistence (INSERT OR IGNORE dedup)
  ├── analyzer.py             WoW % change · MA · Z-score · correlation
  └── dashboard.py            Plotly → self-contained HTML
```

### Why SQLite?

Zero dependencies, zero cost, and `INSERT OR IGNORE` on `(series_id, date)` means you can re-run the fetcher anytime without duplicating data.

### Why market proxies instead of real freight indices?

Real freight rate databases cost **$2,000–$15,000/month** (Freightos, DAT, Baltic Exchange API). ETFs and stocks derived from those rates are free via yfinance and correlate **0.75–0.92** with the underlying index historically.

### Alert logic

1. Compute WoW % change per series (shift 5 for daily, shift 1 for monthly)
2. If `|WoW %| ≥ ALERT_THRESHOLD_PCT` (default 5%), log to `alerts` table
3. Alerts are visible in the dashboard and via `python main.py alerts`

### Z-score anomaly detection

A rolling 20-period window computes mean and std. `Z = (value − mean) / std`. `|Z| > 2` → statistically unusual move (outer 5% of the rolling distribution).

---

## File structure

```
freight-rate-tracker/
├── .github/
│   └── workflows/
│       └── deploy.yml          # CI: fetch + deploy every 6h
├── fetchers/
│   ├── __init__.py
│   ├── fred_fetcher.py         # FRED API client
│   └── market_fetcher.py       # yfinance client
├── docs/
│   └── index.html              # Generated dashboard (served by Pages)
├── analyzer.py                 # Stats: WoW, MA, Z-score, correlation
├── config.py                   # All settings + series definitions
├── dashboard.py                # Plotly HTML generator
├── database.py                 # SQLite layer
├── generate_demo.py            # Seed DB with synthetic data (demo)
├── main.py                     # CLI entry point
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

---

## Adding more series

**Add a market ticker** — edit `config.py`:

```python
MARKET_TICKERS["MATX"] = {
    "label": "Matson Navigation",
    "mode": "maritime",
    "description": "Pacific container shipping — transpacific rate proxy",
    "type": "stock",
}
```

**Add a FRED series** — edit `config.py`:

```python
FRED_SERIES["PCU484121484121"] = {
    "label": "Trucking PPI (TL)",
    "mode": "trucking",
    "unit": "Index",
    "description": "Producer Price Index for truckload freight",
    "frequency": "monthly",
}
```

---

## License

MIT
