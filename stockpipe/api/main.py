"""STAGE 4 — SERVING (API).

Every stage before this one only makes sense to *you*, running scripts on a
terminal. This stage is what makes the pipeline useful to anything else: a
notebook, a dashboard, a phone app, a teammate. The rule that makes this a
real "serving layer" rather than just another script:

    Nothing outside this file talks to the database directly.

A notebook doing `SELECT * FROM prices` and a notebook doing
`requests.get(".../prices/PETR4.SA")` look similar, but they aren't: the
second one can't accidentally corrupt data, doesn't need a database password,
and keeps working even if we later swap Postgres for something else — only
this file would need to change.

Run it:  uvicorn stockpipe.api.main:app --reload
Then:    http://127.0.0.1:8000/docs   (FastAPI's free interactive API docs)
"""
from __future__ import annotations

from datetime import date

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from stockpipe import config
from stockpipe.analytics import queries as analytics
from stockpipe.sources import registry
from stockpipe.storage import db

app = FastAPI(
    title="Daily Brazilian Stock Report API",
    description="Serving layer over the B3 price warehouse (Stage 4).",
    version="0.1.0",
)


class PriceRow(BaseModel):
    ticker: str
    name: str
    sector: str
    role: str
    trade_date: date
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    adj_close: float | None = None
    volume: int | None = None


@app.get("/health")
def health() -> dict:
    """Liveness check — and confirms the database is actually reachable."""
    try:
        engine = db.get_engine()
        with engine.connect():
            pass
        return {"status": "ok", "database": "reachable"}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"database unreachable: {exc}") from exc


@app.get("/symbols")
def symbols() -> list[dict]:
    """The tracked universe — Stage 1's catalogue, resolved."""
    return registry.resolve_symbols()


@app.get("/prices/{ticker}", response_model=list[PriceRow])
def prices(ticker: str, limit: int = Query(default=100, le=1000)) -> list[dict]:
    """Recent price history for one ticker, most recent first."""
    frame = db.latest_prices(ticker=ticker, limit=limit)
    if frame.empty:
        raise HTTPException(status_code=404, detail=f"no data for ticker {ticker!r}")
    return frame.to_dict(orient="records")


@app.get("/report/latest")
def latest_report() -> dict:
    """One row per tracked ticker: its most recent close — a tiny 'Stage 6' preview."""
    universe = registry.resolve_symbols()
    out = []
    for sym in universe:
        frame = db.latest_prices(ticker=sym["ticker"], limit=1)
        if frame.empty:
            continue
        row = frame.iloc[0]
        out.append({
            "ticker": sym["ticker"],
            "name": sym["name"],
            "sector": sym["sector"],
            "trade_date": row["trade_date"],
            "close": float(row["close"]) if row["close"] is not None else None,
        })
    return {"as_of": config.settings()["project"]["timezone"], "rows": out}


# --- Stage 5 (Analytics) endpoints -----------------------------------------
# Same rule as everything else in this file: these compute from the
# warehouse on request rather than reading from any new stored table.


@app.get("/analytics/prices/{ticker}")
def analytics_prices(ticker: str, limit: int = Query(default=400, le=2000)) -> list[dict]:
    """Daily return, 20/50/200-day moving averages, and rolling volatility."""
    df = analytics.price_analytics(ticker=ticker, limit=limit)
    if df.empty:
        raise HTTPException(status_code=404, detail=f"no data for ticker {ticker!r}")
    return df.to_dict(orient="records")


@app.get("/analytics/cumulative-returns")
def analytics_cumulative_returns(limit_per_ticker: int = Query(default=400, le=2000)) -> list[dict]:
    """Cumulative return since first date on record, for every tracked symbol.

    Long format (ticker, trade_date, cum_return) — pivot to wide in the
    client to plot every ticker's line on one overlay chart.
    """
    return analytics.all_cumulative_returns(limit_per_ticker=limit_per_ticker).to_dict(orient="records")


@app.get("/analytics/daily-returns")
def analytics_daily_returns(limit_per_ticker: int = Query(default=400, le=2000)) -> list[dict]:
    """Daily return for every tracked symbol, long format — feeds a correlation matrix."""
    return analytics.all_daily_returns(limit_per_ticker=limit_per_ticker).to_dict(orient="records")


@app.get("/analytics/relative-performance/{ticker}")
def analytics_relative_performance(ticker: str, benchmark: str = "^BVSP",
                                    limit: int = Query(default=400, le=2000)) -> list[dict]:
    """A stock's cumulative return minus the benchmark's, day by day."""
    df = analytics.relative_performance(ticker, benchmark=benchmark, limit=limit)
    if df.empty:
        raise HTTPException(status_code=404, detail=f"no data for ticker {ticker!r}")
    return df.to_dict(orient="records")


@app.get("/analytics/leaderboard")
def analytics_leaderboard(benchmark: str = "^BVSP") -> list[dict]:
    """Every tracked stock's latest performance vs. the benchmark, ranked best to worst."""
    return analytics.leaderboard(benchmark=benchmark).to_dict(orient="records")
