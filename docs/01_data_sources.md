# Stage 1 — Data Sources

> *"You can't build a pipeline until you know what's flowing through it."*

## What this stage is

The first stage of any data pipeline is **identifying and describing** your
inputs — **not** fetching them yet. This is the difference between a catalogue
and a delivery truck: here we build the catalogue.

In the reference diagram this is the leftmost column: SQL databases, SaaS apps,
files/logs, APIs/devices. They're grouped together because, no matter how
different they look, a mature pipeline describes every one of them the *same
way* so later stages can treat them uniformly.

## The idea of a "source contract"

Every source we declare answers four questions:

| Question | Field | Example |
|----------|-------|---------|
| How do we reach it? | `kind` | `api`, `file`, `database` |
| Where is it? | `location` | a URL, a file path, a symbol |
| What comes back? | `contract` | the columns/fields we expect |
| How fresh is it? | `cadence` | daily, real-time, manual |

Writing the **contract** down matters: it's the promise a source makes. When a
source silently changes its shape (a column disappears), the contract is what
lets Stage 2's data-quality checks notice.

## What we built

Two sources, both described by the same `SourceDef` structure:

1. **`universe`** *(file)* — `config/tickers.yml`, the curated watchlist. A
   config file *is* a data source: it's an input that changes over time.
2. **`yahoo_prices`** *(api)* — Yahoo Finance, our daily OHLCV price feed.
   - **OHLCV** = Open, High, Low, Close, Volume — the standard daily price bar.

The registry also has `resolve_symbols()`, which expands the universe file into
the concrete list of things to fetch (benchmark index + each stock). That list
is the **hand-off to Stage 2**.

## Run it

```bash
python -m stockpipe.sources.registry
```

You'll see the source catalogue and the resolved 9-symbol universe.

## Key takeaways

- Stage 1 declares *what*, not *how* — no network code lives here.
- One uniform description (`SourceDef`) for wildly different source types.
- The contract is a promise you can later validate against.
- Config-as-source: your watchlist file is a first-class input.

## What's next — Stage 2 (Ingestion)

Now that we know *what* to pull, Stage 2 actually reaches out to Yahoo Finance,
pulls the OHLCV bars for every symbol, and lands an immutable raw copy in the
data lake. That's where the ETL/ELT distinction shows up.
