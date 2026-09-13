"""Tests for Stage 5 (Analytics).

Most of these run against an in-memory SQLite database seeded with fixture
rows — no live Postgres needed, because the queries under test (returns,
moving averages, cumulative return, relative performance) only use SQL
features SQLite also supports (LAG, FIRST_VALUE, AVG, joins).

`price_analytics()` is the one exception: its rolling-volatility column
uses STDDEV(), which is native to Postgres but not SQLite, so that one is
exercised only against a real database (see needs_live_db in
test_storage.py for the same pattern).
"""
from __future__ import annotations

import os
from datetime import date, timedelta

import pandas as pd
import pytest
from sqlalchemy import create_engine

from stockpipe.analytics import queries
from stockpipe.storage.db import init_db, prices

needs_live_db = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="DATABASE_URL not set — skipping test that needs Postgres-only SQL (STDDEV)",
)


@pytest.fixture
def sqlite_engine():
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    yield engine
    engine.dispose()


def _seed(engine, ticker: str, closes: list[float], sector: str = "Test", name: str = "Test Co",
          role: str = "stock", id_start: int = 0):
    # Explicit ids: SQLite's autoincrement only kicks in for a column typed
    # exactly INTEGER PRIMARY KEY, not the BigInteger our (Postgres-target)
    # schema uses, so bulk-inserting fixture rows here needs ids supplied
    # by hand. Real Postgres never hits this — bigserial just works.
    start = date(2026, 1, 1)
    rows = [
        {
            "id": id_start + i,
            "ticker": ticker, "name": name, "sector": sector, "role": role,
            "trade_date": start + timedelta(days=i),
            "open": c, "high": c, "low": c, "close": c, "adj_close": c, "volume": 1000,
        }
        for i, c in enumerate(closes)
    ]
    with engine.begin() as conn:
        conn.execute(prices.insert(), rows)


def test_daily_return_and_moving_averages(sqlite_engine):
    _seed(sqlite_engine, "TEST9.SA", [10.0, 11.0, 12.0])

    # all_daily_returns doesn't need STDDEV, so it's safe on SQLite and
    # exercises the same LAG-based subquery price_analytics() builds on.
    df = queries.all_daily_returns(engine=sqlite_engine)
    df = df.sort_values("trade_date").reset_index(drop=True)

    assert df["daily_return"].iloc[0] is None or pd.isna(df["daily_return"].iloc[0])  # first row: no prior close
    assert df["daily_return"].iloc[1] == pytest.approx(0.1, abs=1e-3)          # (11-10)/10
    # SQLite's NUMERIC storage rounds to a few decimal places (Postgres won't),
    # so this assertion uses a looser tolerance than the exact 1/11 ratio.
    assert df["daily_return"].iloc[2] == pytest.approx(1 / 11, abs=1e-3)       # (12-11)/11


def test_cumulative_return_rebases_to_zero_on_first_day(sqlite_engine):
    _seed(sqlite_engine, "TEST9.SA", [10.0, 11.0, 12.0])

    df = queries.all_cumulative_returns(engine=sqlite_engine).sort_values("trade_date").reset_index(drop=True)

    assert df["cum_return"].iloc[0] == pytest.approx(0.0)      # day 1 vs itself
    assert df["cum_return"].iloc[1] == pytest.approx(0.1)      # (11/10) - 1
    assert df["cum_return"].iloc[2] == pytest.approx(0.2)      # (12/10) - 1


def test_relative_performance_against_benchmark(sqlite_engine):
    _seed(sqlite_engine, "TEST9.SA", [10.0, 12.0])            # +20% over the window
    _seed(sqlite_engine, "^BVSP", [100.0, 105.0], sector="Index", name="Ibovespa", role="benchmark",
          id_start=1000)  # +5%

    df = queries.relative_performance("TEST9.SA", benchmark="^BVSP", engine=sqlite_engine)
    latest = df.sort_values("trade_date").iloc[-1]

    assert latest["stock_cum_return"] == pytest.approx(0.2)
    assert latest["benchmark_cum_return"] == pytest.approx(0.05)
    assert latest["relative_performance"] == pytest.approx(0.15)   # 20% - 5%


def test_leaderboard_ranks_by_relative_performance(sqlite_engine, monkeypatch):
    _seed(sqlite_engine, "WINNER.SA", [10.0, 15.0], name="Winner Co", sector="Test", id_start=0)
    _seed(sqlite_engine, "LOSER.SA", [10.0, 9.0], name="Loser Co", sector="Test", id_start=1000)
    _seed(sqlite_engine, "^BVSP", [100.0, 100.0], sector="Index", name="Ibovespa", role="benchmark", id_start=2000)

    fake_universe = [
        {"ticker": "^BVSP", "name": "Ibovespa", "sector": "Index", "role": "benchmark"},
        {"ticker": "WINNER.SA", "name": "Winner Co", "sector": "Test", "role": "stock"},
        {"ticker": "LOSER.SA", "name": "Loser Co", "sector": "Test", "role": "stock"},
    ]
    monkeypatch.setattr("stockpipe.sources.registry.resolve_symbols", lambda: fake_universe)

    df = queries.leaderboard(engine=sqlite_engine)

    assert list(df["ticker"]) == ["WINNER.SA", "LOSER.SA"]  # best relative performance first
    assert df.iloc[0]["relative_performance"] > df.iloc[1]["relative_performance"]


@needs_live_db
def test_price_analytics_includes_volatility_against_live_db():
    df = queries.price_analytics(limit=5)
    assert "volatility_20" in df.columns
