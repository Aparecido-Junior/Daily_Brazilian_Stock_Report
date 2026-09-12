"""STAGE 2 — INGESTION.

The job of this stage is to actually reach out to the sources Stage 1
catalogued, pull their data, and hand back a single **tidy** table — one row
per (ticker, date) — that every later stage can rely on having the same
shape, regardless of which source or ticker a row came from.

This is where the ETL/ELT distinction shows up:
  - We pull the *raw* bars for every symbol (Extract).
  - We reshape them into one consistent long-format table, tag each row with
    its ticker/name/sector/role, and coerce types (a light Transform) —
    because Stage 3 (Storage) needs one stable shape to write, not one shape
    per ticker.
  - We do NOT compute indicators, rankings, or signals here — that is
    Stage 4/5. Ingestion's only job is: fetch, tidy, hand off.

Why per-symbol failures don't kill the run: a flaky network call or a
delisted ticker should not stop the other 8 symbols from landing. Each
symbol is fetched independently and failures are collected, not raised.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import pandas as pd
import yfinance as yf

from stockpipe import config

logger = logging.getLogger(__name__)

# The tidy contract every row of this stage's output obeys.
# (Mirrors the `contract` fields declared in Stage 1's SourceDef.)
OUTPUT_COLUMNS = [
    "date", "ticker", "name", "sector", "role",
    "open", "high", "low", "close", "adj_close", "volume",
]


@dataclass
class IngestionResult:
    """What one ingestion run produced."""
    frame: pd.DataFrame          # tidy rows, OUTPUT_COLUMNS
    ok_symbols: list[str]
    failed_symbols: list[tuple[str, str]]  # (ticker, error message)

    @property
    def row_count(self) -> int:
        return len(self.frame)


def _fetch_one(ticker: str, lookback_days: int) -> pd.DataFrame:
    """Pull raw OHLCV history for a single ticker.

    Isolated in its own function so tests can monkeypatch exactly this call
    without touching the network, and so one bad ticker can be caught by the
    caller without aborting the batch.
    """
    hist = yf.Ticker(ticker).history(period=f"{lookback_days}d", auto_adjust=False)
    if hist.empty:
        raise ValueError(f"no data returned for {ticker!r}")
    hist = hist.reset_index()
    hist.columns = [str(c).lower().replace(" ", "_") for c in hist.columns]
    # yfinance sometimes calls the adjusted close "adj_close", sometimes not,
    # depending on auto_adjust — normalise so downstream code has one name.
    if "adj_close" not in hist.columns and "close" in hist.columns:
        hist["adj_close"] = hist["close"]
    return hist


def fetch_prices(symbols: list[dict] | None = None, lookback_days: int | None = None) -> IngestionResult:
    """Fetch OHLCV history for every symbol in the resolved universe.

    Parameters default to the real pipeline inputs (Stage 1's resolved
    universe, and settings.yml's lookback_days) but can be overridden —
    that's what lets tests pass in two fake symbols instead of nine real
    network calls.
    """
    if symbols is None:
        from stockpipe.sources import registry
        symbols = registry.resolve_symbols()
    if lookback_days is None:
        lookback_days = config.settings()["ingestion"]["lookback_days"]

    rows: list[pd.DataFrame] = []
    ok: list[str] = []
    failed: list[tuple[str, str]] = []

    for sym in symbols:
        ticker = sym["ticker"]
        try:
            hist = _fetch_one(ticker, lookback_days)
        except Exception as exc:  # noqa: BLE001 - one bad symbol must not kill the run
            logger.warning("ingestion failed for %s: %s", ticker, exc)
            failed.append((ticker, str(exc)))
            continue

        tidy = pd.DataFrame({
            "date": pd.to_datetime(hist["date"]).dt.date,
            "ticker": ticker,
            "name": sym["name"],
            "sector": sym["sector"],
            "role": sym["role"],
            "open": hist["open"],
            "high": hist["high"],
            "low": hist["low"],
            "close": hist["close"],
            "adj_close": hist["adj_close"],
            "volume": hist["volume"],
        })
        rows.append(tidy)
        ok.append(ticker)

    frame = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(columns=OUTPUT_COLUMNS)
    return IngestionResult(frame=frame, ok_symbols=ok, failed_symbols=failed)


def describe(result: IngestionResult) -> str:
    """Human-readable summary of an ingestion run — run this to *see* the stage."""
    lines = ["=" * 68, "STAGE 2 — INGESTION (fetch + tidy)", "=" * 68, ""]
    lines.append(f"Symbols requested : {len(result.ok_symbols) + len(result.failed_symbols)}")
    lines.append(f"Succeeded         : {len(result.ok_symbols)}  {result.ok_symbols}")
    if result.failed_symbols:
        lines.append(f"Failed            : {len(result.failed_symbols)}")
        for ticker, err in result.failed_symbols:
            lines.append(f"  - {ticker}: {err}")
    lines.append(f"Rows produced     : {result.row_count}")
    if not result.frame.empty:
        lines.append("-" * 68)
        lines.append(result.frame.tail(5).to_string(index=False))
    return "\n".join(lines)


if __name__ == "__main__":
    # Makes the stage runnable:  python -m stockpipe.ingestion.yahoo
    logging.basicConfig(level=logging.INFO)
    res = fetch_prices()
    print(describe(res))
