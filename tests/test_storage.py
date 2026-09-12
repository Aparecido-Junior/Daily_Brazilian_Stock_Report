"""Tests for Stage 3 (Storage).

Two tiers, deliberately:
  - Logic that needs no live database (config handling, error messages) is
    tested unconditionally.
  - Anything that needs a real Postgres connection is skipped unless
    DATABASE_URL is set — CI/local runs without a database still pass, but
    setting DATABASE_URL (e.g. pointed at a Neon branch) exercises the real
    upsert path, including the ON CONFLICT behaviour SQLite can't emulate.
"""
from __future__ import annotations

import os

import pandas as pd
import pytest

from stockpipe.storage import db

needs_live_db = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="DATABASE_URL not set — skipping live-database test",
)


def test_get_engine_raises_clear_error_without_database_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    db.get_engine.cache_clear()

    with pytest.raises(db.StorageNotConfigured):
        db.get_engine()


@needs_live_db
def test_upsert_is_idempotent_on_ticker_and_date():
    db.get_engine.cache_clear()
    db.init_db()

    frame = pd.DataFrame([
        {
            "date": "2026-01-02", "ticker": "TEST9.SA", "name": "Test Co",
            "sector": "Test", "role": "stock", "open": 1.0, "high": 1.1,
            "low": 0.9, "close": 1.05, "adj_close": 1.05, "volume": 100,
        },
    ])

    written_first = db.upsert_prices(frame)
    written_second = db.upsert_prices(frame)  # same (ticker, date) again

    assert written_first == 1
    assert written_second == 1  # upsert, not a duplicate insert

    result = db.latest_prices(ticker="TEST9.SA", limit=10)
    assert len(result) == 1  # still one row, not two
