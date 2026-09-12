"""STAGE 3 — STORAGE.

The job of this stage is to persist Stage 2's tidy output somewhere durable,
shared, and queryable — a real database — instead of a file sitting on one
laptop. That's the whole point of "storage" in a pipeline: once data is here,
any later stage (or any other application, via Stage 4's API) can get at it
without re-running ingestion.

Design choices, and why:
  - **Postgres** (not a local file / SQLite) — a real, hosted, multi-user
    database is the standard "warehouse" layer in a professional stack. We
    use a free hosted instance (Neon or Supabase); the code below only cares
    that it gets a standard Postgres connection string.
  - **One `prices` table**, long/tidy format (one row per ticker+date) —
    mirrors Stage 2's output shape exactly. No reshaping between stages.
  - **Upsert on (ticker, trade_date)** — the pipeline re-runs daily and will
    re-fetch overlapping history (the lookback window). Re-running must be
    *idempotent*: running it twice must not create duplicate rows or fail.
    An "upsert" (INSERT ... ON CONFLICT DO UPDATE) is exactly this.
  - **Connection string from the environment**, never hardcoded — this is
    the same "config, not code" governance principle as Stage 1's config
    files, applied to credentials. See `.env.example`.
"""
from __future__ import annotations

import os
from functools import lru_cache

import pandas as pd
from sqlalchemy import (
    BigInteger, Column, Date, MetaData, Numeric, String, Table,
    UniqueConstraint, create_engine, func, select, DateTime,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Engine

metadata = MetaData()

prices = Table(
    "prices",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("ticker", String(20), nullable=False),
    Column("name", String(120), nullable=False),
    Column("sector", String(60), nullable=False),
    Column("role", String(20), nullable=False),
    Column("trade_date", Date, nullable=False),
    Column("open", Numeric(18, 4)),
    Column("high", Numeric(18, 4)),
    Column("low", Numeric(18, 4)),
    Column("close", Numeric(18, 4)),
    Column("adj_close", Numeric(18, 4)),
    Column("volume", BigInteger),
    Column("ingested_at", DateTime(timezone=True), server_default=func.now()),
    UniqueConstraint("ticker", "trade_date", name="uq_prices_ticker_date"),
)


class StorageNotConfigured(RuntimeError):
    """Raised when DATABASE_URL isn't set — a clear error beats a stack trace."""


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Build (and cache) the SQLAlchemy engine from the DATABASE_URL env var.

    Reads a `.env` file if python-dotenv is available, so local development
    doesn't need the variable exported in every shell. In production (e.g.
    the GitHub Actions workflow) DATABASE_URL is set as a real environment
    variable / secret instead — dotenv is a local-dev convenience only.
    """
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    url = os.environ.get("DATABASE_URL")
    if not url:
        raise StorageNotConfigured(
            "DATABASE_URL is not set. Copy .env.example to .env and fill in "
            "your Postgres connection string (see docs/03_storage.md)."
        )
    return create_engine(url, pool_pre_ping=True)


def init_db(engine: Engine | None = None) -> None:
    """Create the `prices` table if it doesn't exist yet. Safe to call every run."""
    metadata.create_all(engine or get_engine())


def upsert_prices(frame: pd.DataFrame, engine: Engine | None = None) -> int:
    """Write a tidy Stage 2 DataFrame into `prices`, upserting on (ticker, trade_date).

    Returns the number of rows sent (not necessarily the number of *new* rows,
    since re-fetched overlapping days update existing rows rather than adding).
    """
    if frame.empty:
        return 0

    engine = engine or get_engine()
    records = frame.rename(columns={"date": "trade_date"}).to_dict(orient="records")

    stmt = pg_insert(prices).values(records)
    update_cols = {
        c.name: getattr(stmt.excluded, c.name)
        for c in prices.columns
        if c.name not in ("id", "ticker", "trade_date", "ingested_at")
    }
    stmt = stmt.on_conflict_do_update(
        constraint="uq_prices_ticker_date",
        set_=update_cols,
    )

    with engine.begin() as conn:
        conn.execute(stmt)

    return len(records)


def latest_prices(ticker: str | None = None, limit: int = 100, engine: Engine | None = None) -> pd.DataFrame:
    """Read back recent rows — the query Stage 4 (API) wraps in an endpoint."""
    engine = engine or get_engine()
    query = select(prices).order_by(prices.c.trade_date.desc())
    if ticker:
        query = query.where(prices.c.ticker == ticker)
    query = query.limit(limit)

    with engine.connect() as conn:
        return pd.read_sql(query, conn)


def describe() -> str:
    """Human-readable summary of Stage 3 — run this to *see* the stage."""
    lines = ["=" * 68, "STAGE 3 — STORAGE (Postgres warehouse)", "=" * 68, ""]
    engine = get_engine()
    init_db(engine)
    with engine.connect() as conn:
        count = conn.execute(select(func.count()).select_from(prices)).scalar_one()
        tickers = conn.execute(select(prices.c.ticker).distinct()).scalars().all()
    lines.append(f"Connected to      : {engine.url.render_as_string(hide_password=True)}")
    lines.append(f"Rows in `prices`  : {count}")
    lines.append(f"Distinct tickers  : {len(tickers)}  {sorted(tickers)}")
    return "\n".join(lines)


if __name__ == "__main__":
    # Makes the stage runnable:  python -m stockpipe.storage.db
    print(describe())
