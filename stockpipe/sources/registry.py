"""STAGE 1 — DATA SOURCES.

The job of this stage is NOT to fetch data. It is to *declare* what data
exists, where it comes from, and what shape it has. Think of it as an
inventory / catalogue of sources.

Why separate this from actual fetching (Stage 2)?
  - You can reason about your inputs before writing a line of network code.
  - Every source is described the same way (a common "contract"), so the
    ingestion stage can treat them uniformly.
  - Swapping a source later (e.g. Yahoo Finance -> brapi.dev) means editing
    one declaration here, not hunting through the codebase.

A source declaration answers, at minimum:
  - kind:      how do we reach it?  (api, file, database, ...)
  - location:  where is it?         (a URL, a host, a file path, a symbol)
  - contract:  what comes back?     (which columns/fields we expect)
  - cadence:   how fresh is it?     (how often it updates)
"""
from __future__ import annotations

from dataclasses import dataclass, field

from stockpipe import config


@dataclass(frozen=True)
class SourceDef:
    """A single, uniform description of one data source."""
    name: str                    # unique id, e.g. "yahoo_prices"
    kind: str                    # "api" | "file" | "database" | ...
    location: str                # url / path / provider handle
    description: str
    contract: list[str] = field(default_factory=list)  # expected fields
    cadence: str = "daily"       # how often the underlying data refreshes


def _yahoo_price_source() -> SourceDef:
    """The Yahoo Finance API — our primary source of daily OHLCV prices.

    OHLCV = Open, High, Low, Close, Volume: the standard daily price record
    for any traded instrument. This is the raw material of the whole report.
    """
    return SourceDef(
        name="yahoo_prices",
        kind="api",
        location="https://finance.yahoo.com  (via yfinance)",
        description="Daily OHLCV price bars for B3 tickers and the Ibovespa index.",
        contract=["date", "open", "high", "low", "close", "adj_close", "volume"],
        cadence="daily (end of trading day)",
    )


def _universe_source() -> SourceDef:
    """The ticker universe file — a file-based source.

    A curated config file counts as a data source: it's an input the pipeline
    depends on and that can change over time.
    """
    return SourceDef(
        name="universe",
        kind="file",
        location="config/tickers.yml",
        description="Curated list of B3 instruments to track, with sector labels.",
        contract=["ticker", "name", "sector"],
        cadence="manual (edited when the watchlist changes)",
    )


def all_sources() -> list[SourceDef]:
    """The full source catalogue for this pipeline."""
    return [_universe_source(), _yahoo_price_source()]


def resolve_symbols() -> list[dict]:
    """Expand the universe file into the concrete list of symbols to pull.

    This is the bridge from "declared source" to "actual things to fetch":
    the benchmark index plus every stock, each tagged so downstream stages
    know what it is. Stage 2 (Ingestion) will consume exactly this list.
    """
    t = config.tickers()
    symbols: list[dict] = []

    bench = t["benchmark"]
    symbols.append({
        "ticker": bench["ticker"],
        "name": bench["name"],
        "sector": "Index",
        "role": "benchmark",
    })

    for s in t["stocks"]:
        symbols.append({
            "ticker": s["ticker"],
            "name": s["name"],
            "sector": s["sector"],
            "role": "stock",
        })

    return symbols


def describe() -> str:
    """Human-readable summary of Stage 1 — run this to *see* the stage."""
    lines = ["=" * 68, "STAGE 1 — DATA SOURCES (catalogue)", "=" * 68, ""]

    for src in all_sources():
        lines.append(f"[{src.kind.upper():8}] {src.name}")
        lines.append(f"           location: {src.location}")
        lines.append(f"           refresh : {src.cadence}")
        lines.append(f"           fields  : {', '.join(src.contract)}")
        lines.append(f"           {src.description}")
        lines.append("")

    symbols = resolve_symbols()
    lines.append(f"Resolved universe: {len(symbols)} symbols to ingest")
    lines.append("-" * 68)
    for s in symbols:
        lines.append(f"  {s['ticker']:10} {s['role']:9} {s['sector']:22} {s['name']}")

    return "\n".join(lines)


if __name__ == "__main__":
    # Makes the stage runnable:  python -m stockpipe.sources.registry
    print(describe())
