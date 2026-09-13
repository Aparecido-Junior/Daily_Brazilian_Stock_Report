# Stage 5 — Analytics

> *"Is this stock trending up or down?" is a warm-up question. "Is it beating*
> *the index?" is the one that actually matters."*

## What this stage is

Stages 1-4 only answer "what happened": here are the prices, straight out of
the warehouse. This stage turns those raw rows into the numbers an analyst
would actually ask for — daily return, moving averages, rolling volatility,
and (the one that matters most for a single-market report like this)
performance *relative to the Ibovespa benchmark*.

Design choice, and it's the important one: these are **computed queries, not
new tables**. `stockpipe/analytics/queries.py` doesn't write anything back to
the database — every function runs a read query against the same `prices`
table from Stage 3, using SQL window functions, and returns a DataFrame. That
keeps Stage 3's storage contract exactly as simple as it was (one tidy table)
while still letting this stage express fairly rich analysis. If a metric ever
turns out to be too expensive to recompute on every request, *that's* the
moment to consider materializing it into its own table — not before.

## The metrics

| Function | Returns |
|---|---|
| `price_analytics(ticker)` | Daily return, 20/50/200-day moving averages, 20-day rolling volatility |
| `all_daily_returns()` | Daily return for every tracked symbol, long format — feeds the Stage 6 correlation heatmap |
| `all_cumulative_returns()` | Cumulative return since first date on record, every symbol rebased to 0% — feeds the Stage 6 overlay chart |
| `relative_performance(ticker)` | The stock's cumulative return minus the Ibovespa's, day by day |
| `leaderboard()` | Every tracked stock's latest relative performance, ranked best to worst |

All five are exposed as new `/analytics/*` endpoints in Stage 4's API
(`stockpipe/api/main.py`) — the serving-layer rule from Stage 4 still holds
exactly as before: nothing outside that one file talks to the database, this
module included. `stockpipe/analytics/queries.py` gets called *by* the API,
the same way `stockpipe/storage/db.py` does.

## A SQL lesson worth keeping

You cannot nest one window function directly inside another in a single
`SELECT` — you can't write `STDDEV(x) OVER (...)` where `x` is itself
`LAG(...) OVER (...)` in the same query. The fix is the classic one: compute
the first window function in a subquery, then apply the second window
function to *that subquery's output column*. `_daily_return_subquery()` in
`queries.py` exists for exactly this reason — `price_analytics()` needs a
rolling volatility *of daily returns*, and daily returns are themselves a
window function (`LAG` compared against the previous row).

The same subquery pattern shows up again in `_cum_return_subquery()`, which
uses `FIRST_VALUE(...) OVER (...)` to rebase every ticker's price series to
its own starting point — that's what makes a R$100 stock and a R$10 stock
comparable on the same chart in Stage 6.

## Why "relative performance" instead of just "return"

A stock up 10% while the Ibovespa is up 20% quietly *underperformed* the
market — the raw price, or even the raw return, won't tell you that on its
own. `relative_performance()` computes `stock_cum_return - benchmark_cum_return`
day by day, so positive means "beating the index since the start of the
window" and negative means "lagging it." `leaderboard()` is just "everyone's
latest relative-performance number, sorted" — built on top of
`relative_performance()` rather than a separate query, since there's no
reason to duplicate the underlying SQL.

## Testing without a live database

Most of the queries here only use SQL features SQLite also understands
(`LAG`, `FIRST_VALUE`, `AVG` with a window frame, joins), so
`tests/test_analytics.py` seeds an in-memory SQLite database with small,
hand-checkable fixtures and asserts on the actual numbers — no Postgres
connection needed, no network, runs in CI on every push.

`price_analytics()`'s rolling-volatility column is the one exception: it uses
`STDDEV()`, which SQLite doesn't implement. That one test is marked
`needs_live_db` and skips itself automatically when `DATABASE_URL` isn't set
— the same pattern already used for the live-database test in
`tests/test_storage.py`. Nothing is silently assumed to work; the test suite
is honest about exactly what is and isn't verified without a real database.

## Try it

```bash
uvicorn stockpipe.api.main:app --reload
```

Then, with Stage 2/3 having run at least once so there's real data to query:

```
http://127.0.0.1:8000/analytics/prices/PETR4.SA
http://127.0.0.1:8000/analytics/leaderboard
```

## What's next

Stage 6 (Visualization) turns these numbers into something to *look at*:
`notebooks/explore.ipynb` plots the moving averages, the cumulative-return
overlay, the correlation heatmap and the leaderboard directly from these
endpoints, and `scripts/generate_report_images.py` produces the same charts
as static PNGs embedded straight in this repo's `README.md`.
