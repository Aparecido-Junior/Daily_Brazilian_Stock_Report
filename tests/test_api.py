"""Tests for Stage 4 (API) — exercised with FastAPI's TestClient.

`db.latest_prices` is monkeypatched so these tests verify the *endpoints*
(status codes, response shape) without needing a live Postgres connection.
"""
from __future__ import annotations

import pandas as pd
from fastapi.testclient import TestClient

from stockpipe.analytics import queries as analytics
from stockpipe.api import main as api_main
from stockpipe.storage import db

client = TestClient(api_main.app)


def _fake_frame(ticker: str) -> pd.DataFrame:
    return pd.DataFrame([{
        "ticker": ticker, "name": "Petrobras PN", "sector": "Energy", "role": "stock",
        "trade_date": "2026-01-02", "open": 10.0, "high": 10.8, "low": 9.9,
        "close": 10.4, "adj_close": 10.4, "volume": 1000,
    }])


def test_symbols_returns_the_configured_universe():
    resp = client.get("/symbols")
    assert resp.status_code == 200
    tickers = [s["ticker"] for s in resp.json()]
    assert "PETR4.SA" in tickers
    assert "^BVSP" in tickers  # benchmark included


def test_prices_returns_rows_for_known_ticker(monkeypatch):
    monkeypatch.setattr(db, "latest_prices", lambda ticker=None, limit=100, engine=None: _fake_frame(ticker))

    resp = client.get("/prices/PETR4.SA")

    assert resp.status_code == 200
    body = resp.json()
    assert body[0]["ticker"] == "PETR4.SA"
    assert body[0]["close"] == 10.4


def test_prices_404s_for_ticker_with_no_data(monkeypatch):
    monkeypatch.setattr(db, "latest_prices", lambda ticker=None, limit=100, engine=None: pd.DataFrame())

    resp = client.get("/prices/NOPE.SA")

    assert resp.status_code == 404


def test_analytics_prices_returns_moving_averages(monkeypatch):
    fake = pd.DataFrame([{
        "ticker": "PETR4.SA", "name": "Petrobras PN", "sector": "Energy",
        "trade_date": "2026-01-02", "close": 10.4, "daily_return": 0.01,
        "ma_20": 10.2, "ma_50": 10.1, "ma_200": 9.9, "volatility_20": 0.015,
    }])
    monkeypatch.setattr(analytics, "price_analytics", lambda ticker=None, limit=400, engine=None: fake)

    resp = client.get("/analytics/prices/PETR4.SA")

    assert resp.status_code == 200
    assert resp.json()[0]["ma_20"] == 10.2


def test_analytics_prices_404s_with_no_data(monkeypatch):
    monkeypatch.setattr(analytics, "price_analytics", lambda ticker=None, limit=400, engine=None: pd.DataFrame())

    resp = client.get("/analytics/prices/NOPE.SA")

    assert resp.status_code == 404


def test_analytics_leaderboard_returns_ranked_rows(monkeypatch):
    fake = pd.DataFrame([
        {"ticker": "WINNER.SA", "name": "Winner Co", "sector": "Test", "trade_date": "2026-01-02",
         "stock_return_since_start": 0.2, "benchmark_return_since_start": 0.05, "relative_performance": 0.15},
    ])
    monkeypatch.setattr(analytics, "leaderboard", lambda benchmark="^BVSP", engine=None: fake)

    resp = client.get("/analytics/leaderboard")

    assert resp.status_code == 200
    assert resp.json()[0]["ticker"] == "WINNER.SA"


def test_analytics_cumulative_returns_long_format(monkeypatch):
    fake = pd.DataFrame([
        {"ticker": "PETR4.SA", "trade_date": "2026-01-02", "cum_return": 0.05},
        {"ticker": "^BVSP", "trade_date": "2026-01-02", "cum_return": 0.02},
    ])
    monkeypatch.setattr(analytics, "all_cumulative_returns", lambda limit_per_ticker=400, engine=None: fake)

    resp = client.get("/analytics/cumulative-returns")

    assert resp.status_code == 200
    assert len(resp.json()) == 2
