"""
database.py
-----------
SQLite persistence layer.

Tables
------
  rates       – raw time-series observations (one row per ticker/series per date)
  alerts      – fired alerts log
  run_log     – timestamps of each tracker run
"""

import sqlite3
from contextlib import contextmanager
from datetime import datetime

import pandas as pd

import config


@contextmanager
def _conn():
    con = sqlite3.connect(config.DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init_db() -> None:
    """Create tables if they don't exist yet."""
    with _conn() as con:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS rates (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                source      TEXT    NOT NULL,   -- 'fred' | 'market'
                series_id   TEXT    NOT NULL,   -- e.g. 'TRUCKD11' or 'BDRY'
                label       TEXT    NOT NULL,
                mode        TEXT    NOT NULL,   -- trucking / maritime / rail / air_freight
                date        TEXT    NOT NULL,   -- ISO-8601 YYYY-MM-DD
                value       REAL    NOT NULL,
                inserted_at TEXT    NOT NULL,
                UNIQUE(series_id, date)
            );

            CREATE TABLE IF NOT EXISTS alerts (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                series_id   TEXT    NOT NULL,
                label       TEXT    NOT NULL,
                alert_type  TEXT    NOT NULL,   -- 'spike' | 'drop'
                change_pct  REAL    NOT NULL,
                date        TEXT    NOT NULL,
                fired_at    TEXT    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS run_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                ran_at      TEXT    NOT NULL,
                rows_upserted INTEGER NOT NULL
            );
            """
        )


def upsert_rates(rows: list[dict]) -> int:
    """
    Insert or ignore rate rows.

    Parameters
    ----------
    rows : list[dict]
        Keys: source, series_id, label, mode, date, value

    Returns
    -------
    int  number of new rows inserted
    """
    now = datetime.utcnow().isoformat()
    inserted = 0
    with _conn() as con:
        for row in rows:
            cur = con.execute(
                """
                INSERT OR IGNORE INTO rates
                    (source, series_id, label, mode, date, value, inserted_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["source"],
                    row["series_id"],
                    row["label"],
                    row["mode"],
                    row["date"],
                    row["value"],
                    now,
                ),
            )
            inserted += cur.rowcount
    return inserted


def log_run(rows_upserted: int) -> None:
    with _conn() as con:
        con.execute(
            "INSERT INTO run_log (ran_at, rows_upserted) VALUES (?, ?)",
            (datetime.utcnow().isoformat(), rows_upserted),
        )


def log_alert(series_id: str, label: str, alert_type: str, change_pct: float, date: str) -> None:
    now = datetime.utcnow().isoformat()
    with _conn() as con:
        con.execute(
            """
            INSERT INTO alerts (series_id, label, alert_type, change_pct, date, fired_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (series_id, label, alert_type, change_pct, date, now),
        )


def load_rates(series_id: str | None = None, days: int = 365) -> pd.DataFrame:
    """
    Load rate history as a DataFrame.

    Parameters
    ----------
    series_id : str or None
        Filter to a specific series. None → all series.
    days : int
        How many calendar days back to fetch.
    """
    query = f"""
        SELECT series_id, label, mode, date, value
        FROM rates
        WHERE date >= date('now', '-{days} days')
        {"AND series_id = ?" if series_id else ""}
        ORDER BY series_id, date
    """
    params = (series_id,) if series_id else ()
    with _conn() as con:
        df = pd.read_sql_query(query, con, params=params)
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
    return df


def load_alerts(limit: int = 50) -> pd.DataFrame:
    with _conn() as con:
        return pd.read_sql_query(
            f"SELECT * FROM alerts ORDER BY fired_at DESC LIMIT {limit}", con
        )
