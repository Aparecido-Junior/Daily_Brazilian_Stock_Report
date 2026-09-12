"""Tests for Stage 4 (API) — exercised with FastAPI's TestClient.

`db.latest_prices` is monkeypatched so these tests verify the *endpoints*
(status codes, response shape) without needing a live Postgres connection.
"""
from __future__ import annotations

import pandas as pd
from fastapi.testclient import TestClient

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
