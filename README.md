# Daily Brazilian Stock Report — a data pipeline, built to learn

This repo is a **hands-on tour of the classic 6-stage data pipeline**, built
around a real use case: producing a daily report on Brazilian (B3) stocks.

The goal is learning the *framework* first, the app second. Each stage is built
and explained one at a time, with a short note in [`docs/`](docs/) and runnable
code you can execute to *see* the stage work.

## The pipeline

```
1. SOURCES  ->  2. INGESTION  ->  3. STORAGE  ->  4. PROCESSING  ->  5. ANALYTICS  ->  6. VISUALIZATION
   what data      extract &         data lake +      clean /            signals,          report,
   exists         land it raw       warehouse        transform          rankings          charts, alerts
                              \___________________ ⟳ MONITOR / OPTIMIZE / GOVERN ___________________/
```

| Stage | Status | Doc |
|-------|--------|-----|
| 1. Data Sources | ✅ built | [docs/01_data_sources.md](docs/01_data_sources.md) |
| 2. Ingestion | ⬜ next | — |
| 3. Storage | ⬜ | — |
| 4. Processing | ⬜ | — |
| 5. Analytics | ⬜ | — |
| 6. Visualization & Insights | ⬜ | — |
| ⟳ Monitor / Govern | ⬜ (woven throughout) | — |

## Tech choices (all swappable — that's the point of the layered design)

- **Python** — richest ecosystem for financial data
- **Yahoo Finance** (`yfinance`) — free B3 data, no API key
- **parquet** — columnar files for the raw data lake
- **DuckDB** — lightweight SQL warehouse over those files

## Project layout

```
config/           # settings + ticker universe   (Governance: config-as-code)
stockpipe/        # the pipeline package
  config.py       #   central config loader
  sources/        #   Stage 1: source catalogue
docs/             # one learning note per stage
data/
  raw/            #   Stage 3: data lake  (raw, immutable)
  warehouse/      #   Stage 3: warehouse  (curated, query-ready)
  reports/        #   Stage 6: outputs
tests/
```

## Setup

```bash
pip install -r requirements.txt
python -m stockpipe.sources.registry   # run Stage 1
```
