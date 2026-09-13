"""STAGE 5 — ANALYTICS.

Stages 1-4 answer "what happened" (here are the prices). This stage answers
the questions an analyst actually asks: is this stock trending up or down,
is it more volatile than usual, and — the one that matters most for a
single-market report like this — *is it beating the index*?

Design choice: these are **computed queries, not new tables**. Nothing here
is written back to the database; every function below runs a read query
against `prices` (using SQL window functions, via SQLAlchemy Core) and
returns a DataFrame. That keeps Stage 3's storage contract exactly as
simple as it was — one tidy table — while still letting this stage express
fairly rich analysis. If a metric turns out to be expensive to recompute on
every request, *that's* the moment to consider materializing it; not before.

A SQL note worth keeping, because it trips people up: you cannot nest one
window function directly inside another in a single SELECT (e.g. you can't
write `STDDEV(x) OVER (...)` where `x` is itself `LAG(...) OVER (...)` in
the same query). The fix is the classic one — compute the first window
function in a subquery, then apply the second window function to *that*
subquery's output column. `_daily_return_subquery()` exists for exactly
this reason: `price_analytics()` needs a rolling volatility of daily
returns, and daily returns are themselves a window function.
"""
from __future__ import annotations

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.engine import Engine

from stockpipe.storage.db import get_engine, prices


def _daily_return_subquery():
    """Inner query: each row's close plus its day-over-day return.

    Isolated in its own function because two different outer queries need
    it: price_analytics() (for rolling volatility) and, indirectly, anyone
    wanting raw daily returns without the moving-average/volatility columns.
    """
    prev_close = func.lag(prices.c.close).over(
        partition_by=prices.c.ticker, order_by=prices.c.trade_date
    )
    return select(
        prices.c.ticker,
        prices.c.name,
        prices.c.sector,
        prices.c.role,
        prices.c.trade_date,
        prices.c.close,
        ((prices.c.close - prev_close) / prev_close).label("daily_return"),
    ).subquery("daily")


def _cum_return_subquery():
    """Inner query: each row's cumulative return since the first date on record.

    Used for both the relative-performance-vs-benchmark comparison and the
    all-tickers cumulative-return series behind the Stage 6 overlay chart.
    """
    first_close = func.first_value(prices.c.close).over(
        partition_by=prices.c.ticker, order_by=prices.c.trade_date
    )
    return select(
        prices.c.ticker,
        prices.c.trade_date,
        prices.c.close,
        ((prices.c.close / first_close) - 1).label("cum_return"),
    ).subquery("cum")


def price_analytics(ticker: str | None = None, limit: int = 400, engine: Engine | None = None) -> pd.DataFrame:
    """Daily return, 20/50/200-day moving averages, and 20-day rolling volatility.

    Moving averages and volatility use a window "frame" of the preceding N-1
    rows plus the current one (ROWS BETWEEN N-1 PRECEDING AND CURRENT ROW).
    Near the start of a ticker's history the frame simply clips to however
    many rows actually exist — a 20-day average on day 3 is an average of 3
    days, not null and not wrong, just an early-history caveat worth knowing
    about when reading the numbers.
    """
    inner = _daily_return_subquery()

    def moving_avg(window: int):
        return func.avg(inner.c.close).over(
            partition_by=inner.c.ticker, order_by=inner.c.trade_date, rows=(-(window - 1), 0)
        )

    volatility_20 = func.stddev(inner.c.daily_return).over(
        partition_by=inner.c.ticker, order_by=inner.c.trade_date, rows=(-19, 0)
    )

    query = select(
        inner.c.ticker,
        inner.c.name,
        inner.c.sector,
        inner.c.trade_date,
        inner.c.close,
        inner.c.daily_return,
        moving_avg(20).label("ma_20"),
        moving_avg(50).label("ma_50"),
        moving_avg(200).label("ma_200"),
        volatility_20.label("volatility_20"),
    ).order_by(inner.c.trade_date.desc())

    if ticker:
        query = query.where(inner.c.ticker == ticker)
    query = query.limit(limit)

    engine = engine or get_engine()
    with engine.connect() as conn:
        return pd.read_sql(query, conn)


def all_daily_returns(limit_per_ticker: int = 400, engine: Engine | None = None) -> pd.DataFrame:
    """Long-format (ticker, trade_date, daily_return) for every tracked symbol.

    Feeds the Stage 6 correlation heatmap: pivot this to wide (one column
    per ticker) and call .corr() on it.
    """
    inner = _daily_return_subquery()
    query = select(inner.c.ticker, inner.c.trade_date, inner.c.daily_return).order_by(
        inner.c.ticker, inner.c.trade_date.desc()
    )
    engine = engine or get_engine()
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)
    if limit_per_ticker and not df.empty:
        df = df.groupby("ticker", group_keys=False).head(limit_per_ticker)
    return df


def all_cumulative_returns(limit_per_ticker: int = 400, engine: Engine | None = None) -> pd.DataFrame:
    """Long-format (ticker, trade_date, cum_return) for every tracked symbol.

    Feeds the Stage 6 "which of these would you rather have owned" overlay
    chart — every line rebased to 0% on its first day on record.
    """
    cum = _cum_return_subquery()
    query = select(cum.c.ticker, cum.c.trade_date, cum.c.cum_return).order_by(
        cum.c.ticker, cum.c.trade_date.desc()
    )
    engine = engine or get_engine()
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)
    if limit_per_ticker and not df.empty:
        df = df.groupby("ticker", group_keys=False).head(limit_per_ticker)
    return df


def relative_performance(
    ticker: str, benchmark: str = "^BVSP", limit: int = 400, engine: Engine | None = None
) -> pd.DataFrame:
    """A stock's cumulative return minus the benchmark's, day by day.

    Positive means the stock has outperformed the Ibovespa since the start
    of the window; negative means it has lagged. This is the single number
    that answers "was this a good B3 stock to have held" better than the
    raw price ever could — a stock that's up 10% while the index is up 20%
    quietly underperformed, and the raw price alone won't tell you that.
    """
    cum = _cum_return_subquery()
    stock = cum.alias("stock")
    bench = cum.alias("bench")

    query = (
        select(
            stock.c.trade_date,
            stock.c.ticker,
            stock.c.cum_return.label("stock_cum_return"),
            bench.c.cum_return.label("benchmark_cum_return"),
            (stock.c.cum_return - bench.c.cum_return).label("relative_performance"),
        )
        .select_from(stock.join(bench, stock.c.trade_date == bench.c.trade_date))
        .where(stock.c.ticker == ticker, bench.c.ticker == benchmark)
        .order_by(stock.c.trade_date.desc())
        .limit(limit)
    )

    engine = engine or get_engine()
    with engine.connect() as conn:
        return pd.read_sql(query, conn)


def leaderboard(benchmark: str = "^BVSP", engine: Engine | None = None) -> pd.DataFrame:
    """Every tracked stock's most recent relative-performance-vs-benchmark, ranked.

    Built on top of relative_performance() rather than a separate query —
    the leaderboard is just "everyone's latest row," so there's no reason
    to duplicate the underlying SQL.
    """
    from stockpipe.sources import registry

    engine = engine or get_engine()
    rows = []
    for sym in registry.resolve_symbols():
        if sym["role"] == "benchmark":
            continue
        rp = relative_performance(sym["ticker"], benchmark=benchmark, limit=1, engine=engine)
        if rp.empty:
            continue
        latest = rp.iloc[0]
        rows.append({
            "ticker": sym["ticker"],
            "name": sym["name"],
            "sector": sym["sector"],
            "trade_date": latest["trade_date"],
            "stock_return_since_start": latest["stock_cum_return"],
            "benchmark_return_since_start": latest["benchmark_cum_return"],
            "relative_performance": latest["relative_performance"],
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("relative_performance", ascending=False).reset_index(drop=True)
    return df
