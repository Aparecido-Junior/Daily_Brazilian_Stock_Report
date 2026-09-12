"""The daily entrypoint: wires Stage 2 (Ingestion) into Stage 3 (Storage).

This is the one script the scheduler (GitHub Actions, see
.github/workflows/daily_pipeline.yml) actually runs every day. It stays thin
on purpose — all the real logic lives in the stage modules, which you can
also run and test independently (`python -m stockpipe.ingestion.yahoo`,
`python -m stockpipe.storage.db`).
"""
from __future__ import annotations

import logging
import sys

from stockpipe.ingestion import yahoo
from stockpipe.storage import db

logger = logging.getLogger(__name__)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    logger.info("Stage 2: fetching prices...")
    result = yahoo.fetch_prices()
    logger.info(
        "Stage 2 done: %d rows, %d ok, %d failed",
        result.row_count, len(result.ok_symbols), len(result.failed_symbols),
    )
    for ticker, err in result.failed_symbols:
        logger.warning("  failed: %s (%s)", ticker, err)

    if result.frame.empty:
        logger.error("No data ingested — skipping storage write.")
        return 1

    logger.info("Stage 3: writing to warehouse...")
    db.init_db()
    written = db.upsert_prices(result.frame)
    logger.info("Stage 3 done: %d rows upserted", written)

    # A partial failure (some tickers ok, some not) still exits 0 so the
    # scheduled run isn't marked failed over one flaky symbol — but it's
    # logged loudly above so it's visible in the Actions run history.
    return 0


if __name__ == "__main__":
    sys.exit(main())
