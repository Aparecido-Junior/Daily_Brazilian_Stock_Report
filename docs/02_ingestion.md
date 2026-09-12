# Stage 2 — Ingestion

> *"The catalogue told us what exists. Now we go get it."*

## What this stage is

Ingestion is where the pipeline first reaches out to the real world. Stage 1
declared the `yahoo_prices` source and its contract (`date, open, high, low,
close, adj_close, volume`); this stage actually calls Yahoo Finance for every
symbol in the resolved universe and turns the response into one **tidy**
table that obeys that contract.

"Tidy" has a specific meaning here: **one row per (ticker, date)**, same
columns for every row, regardless of whether it's a stock or the benchmark
index. Every later stage can then treat the data uniformly — Stage 3 doesn't
need to know which rows came from which ticker's API response.

## ETL vs ELT — which is this?

- **E**xtract: pull the raw OHLCV bars per ticker.
- **T**ransform: a *light* one here — reshape into the tidy contract, tag
  each row with its ticker/name/sector/role. We deliberately do **not**
  compute moving averages, returns, or rankings in this stage — that's
  Stage 4/5 (Processing/Analytics). Ingestion's contract is "fetch and tidy,"
  nothing more.
- **L**oad: happens in Stage 3, not here. This stage hands back a DataFrame;
  it doesn't know or care where it ends up.

Keeping Transform this thin is what makes this an "EL(t)" pipeline rather
than a heavy ETL — most of the real transformation work is pushed later,
closer to where it's actually needed, on top of data that's already durably
stored.

## Failure isolation

A pipeline that pulls 9 symbols and dies because 1 ticker was delisted is a
bad pipeline. `fetch_prices()` fetches each symbol independently, catches
per-symbol errors, and keeps going — the result tells you both what
succeeded and exactly what failed and why, instead of losing 8 good symbols
to 1 bad one.

## Why this is testable without hitting Yahoo Finance

The actual network call lives in one small function, `_fetch_one()`. Every
test in `tests/test_ingestion.py` monkeypatches *that* function with canned
data — so what's actually under test is our tidying and error-isolation
logic, not Yahoo Finance's uptime. This matters: a test suite that needs the
internet (and a live market) to pass is a test suite that fails randomly and
teaches you not to trust red X's.

## Run it

```bash
python -m stockpipe.ingestion.yahoo
```

You'll see how many symbols succeeded, any failures, and a preview of the
tidy rows produced — this stage's output, seen directly, before Stage 3
touches it.

## What's next — Stage 3 (Storage)

The tidy DataFrame this stage returns needs somewhere durable to live. Stage
3 takes it from here and writes it into a real Postgres warehouse — not a
file on this laptop — so it survives past this one Python process and any
other stage (or the API in Stage 4) can query it.
