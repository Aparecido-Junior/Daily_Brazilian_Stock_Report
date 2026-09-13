# Stage 4 — Serving (API)

> *"A database only you can query is a fancier file on your laptop."*

## What this stage is

This stage puts a small web API — built with [FastAPI](https://fastapi.tiangolo.com/)
— in front of the Postgres warehouse. It's the one rule that makes this a
real "serving layer": **nothing outside `stockpipe/api/main.py` talks to the
database directly.** Not the notebook, not a future dashboard, nothing.

Why that rule matters, concretely:

- The notebook (or a teammate, or a phone app) never needs the database
  password — just a URL.
- If Postgres is ever swapped for something else, only this one file needs
  to change; every client keeps working unmodified.
- You can add validation, rate-limiting, or caching in exactly one place.

## Endpoints

| Endpoint | Returns |
|---|---|
| `GET /health` | Whether the API can reach the database right now |
| `GET /symbols` | The tracked universe (Stage 1's catalogue, resolved) |
| `GET /prices/{ticker}?limit=100` | Recent OHLCV rows for one ticker |
| `GET /report/latest` | Most recent close for every tracked ticker |
| `GET /analytics/prices/{ticker}` | Daily return, moving averages, rolling volatility ([Stage 5](05_analytics.md)) |
| `GET /analytics/cumulative-returns` | Every symbol's return since day one, rebased to 0% |
| `GET /analytics/daily-returns` | Daily returns for every symbol, long format (feeds the correlation heatmap) |
| `GET /analytics/relative-performance/{ticker}` | A stock's return minus the Ibovespa's, day by day |
| `GET /analytics/leaderboard` | Every stock ranked by performance vs. the Ibovespa |

## Run it

```bash
uvicorn stockpipe.api.main:app --reload
```

Then open **http://127.0.0.1:8000/docs** — FastAPI generates a full
interactive API explorer automatically from the code, no extra work. Try
`/symbols` first (it needs no database rows to exist yet), then `/prices/PETR4.SA`
once Stage 2 + 3 have actually run at least once.

## Why `TestClient` instead of a running server, in tests

`tests/test_api.py` uses FastAPI's `TestClient`, which calls the app directly
in-process — no server needs to be listening, no port to manage, and it's
fast enough to run on every commit (see `.github/workflows/tests.yml`). The
database calls inside the endpoints are monkeypatched too, so these tests
check the *API's* behaviour (status codes, response shape, the 404 on an
unknown ticker) independent of whether a real database is reachable.

## What's next

The pattern from here repeats: Stage 5 ([docs/05_analytics.md](05_analytics.md))
adds real computation — moving averages, volatility, performance relative to
the Ibovespa — as new functions this same file exposes as new `/analytics/*`
endpoints, and Stage 6 ([docs/06_visualization.md](06_visualization.md)) turns
those endpoints into something to *look at*: `notebooks/explore.ipynb`, and
the chart images embedded in the repo's main [README](../README.md).
