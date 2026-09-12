"""Tests for Stage 2 (Ingestion) that never touch the network.

`_fetch_one` is monkeypatched with canned data shaped exactly like what
`yfinance.Ticker(...).history()` returns, so we're testing our own tidying
logic, not Yahoo Finance's availability.
"""
from __future__ import annotations

import pandas as pd
import pytest

from stockpipe.ingestion import yahoo

FAKE_SYMBOLS = [
    {"ticker": "PETR4.SA", "name": "Petrobras PN", "sector": "Energy", "role": "stock"},
    {"ticker": "BROKEN.SA", "name": "Broken Co", "sector": "Energy", "role": "stock"},
]


def _fake_history(ticker: str, lookback_days: int) -> pd.DataFrame:
    if ticker == "BROKEN.SA":
        raise ValueError("simulated network failure")
    return pd.DataFrame({
        "date": pd.to_datetime(["2026-01-02", "2026-01-03"]),
        "open": [10.0, 10.5],
        "high": [10.8, 10.9],
        "low": [9.9, 10.2],
        "close": [10.4, 10.7],
        "adj_close": [10.4, 10.7],
        "volume": [1000, 1200],
    })


def test_fetch_prices_tidies_ok_symbols_and_isolates_failures(monkeypatch):
    monkeypatch.setattr(yahoo, "_fetch_one", _fake_history)

    result = yahoo.fetch_prices(symbols=FAKE_SYMBOLS, lookback_days=5)

    assert result.ok_symbols == ["PETR4.SA"]
    assert len(result.failed_symbols) == 1
    assert result.failed_symbols[0][0] == "BROKEN.SA"
    assert result.row_count == 2
    assert list(result.frame.columns) == yahoo.OUTPUT_COLUMNS
    assert set(result.frame["ticker"]) == {"PETR4.SA"}


def test_fetch_prices_all_fail_returns_empty_frame_not_error(monkeypatch):
    def always_fail(ticker, lookback_days):
        raise ValueError("down")

    monkeypatch.setattr(yahoo, "_fetch_one", always_fail)

    result = yahoo.fetch_prices(symbols=FAKE_SYMBOLS, lookback_days=5)

    assert result.frame.empty
    assert result.ok_symbols == []
    assert len(result.failed_symbols) == 2


def test_describe_does_not_raise_on_empty_result():
    empty = yahoo.IngestionResult(frame=pd.DataFrame(columns=yahoo.OUTPUT_COLUMNS), ok_symbols=[], failed_symbols=[])
    assert "STAGE 2" in yahoo.describe(empty)
