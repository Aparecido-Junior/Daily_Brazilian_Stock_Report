# Stage 6 — Visualization & Insights

> *A pipeline nobody looks at isn't finished — it's just stored data.*

## What this stage is

Every stage before this one produces something correct; this stage produces
something *legible*. Two clients consume the exact same Stage 5 analytics
endpoints, for two different audiences:

| Client | Audience | File |
|---|---|---|
| `notebooks/explore.ipynb` | you, exploring interactively | a notebook that calls the API and plots the response |
| `scripts/generate_report_images.py` | anyone browsing this repo on GitHub | a script that produces static PNGs, embedded below |

Both are just HTTP clients (or, for the script, direct callers of
`stockpipe.analytics.queries` — see the note below on why). Neither one
touches Postgres directly, and neither duplicates a single SQL query: all the
actual analysis was already done in Stage 5.

## Why a script *and* a notebook

The notebook is for exploring — change the ticker, change the date range,
re-run a cell. It needs a person at the keyboard and a running API.

The charts below can't depend on that. A recruiter or a hiring manager
looking at this repo on GitHub isn't going to clone it, start Postgres,
launch the API, and open Jupyter just to see whether the pipeline works —
they're going to scroll the README. So `scripts/generate_report_images.py`
exists to turn Stage 5's numbers into three PNGs that live in the repo
itself and update automatically. That's a deliberate, portfolio-driven
choice: the proof that this project works should be visible *without
running any code*.

One implementation detail: that script calls `stockpipe.analytics.queries`
directly rather than going through the Stage 4 API over HTTP. That isn't a
violation of the "nothing but the API touches the database" rule from
Stage 4 — `stockpipe/analytics/queries.py` *is* the analysis code the API
endpoints call too; the API and this script are simply two different
callers of the same functions, chosen here because there's no reason to
stand up an HTTP server just to generate three images in CI.

## The three charts

**Cumulative return overlay** (`docs/assets/cumulative_returns.png`) —
every tracked stock's return since its first date on record, rebased to 0%,
with the Ibovespa (`^BVSP`) drawn as a heavier dashed line. Answers "which of
these would you rather have owned," on one comparable scale regardless of
each stock's actual price.

**Correlation heatmap** (`docs/assets/correlation_heatmap.png`) — how
closely each stock's daily moves track every other stock's (and the index).
Useful for spotting which names in the tracked universe are basically moving
together versus which ones are genuinely diversifying.

**Leaderboard** (`docs/assets/leaderboard.png`) — every tracked stock's
latest performance relative to the Ibovespa, ranked. Green means beating the
index since day one on record, red means lagging it.

## Keeping the charts fresh automatically

Static images go stale unless something regenerates them. The last step of
`.github/workflows/daily_pipeline.yml` runs
`python scripts/generate_report_images.py` right after the daily
ingestion-to-storage run, then commits the refreshed PNGs back to the repo if
they changed. That means the charts embedded in `README.md` are never more
than one trading day stale, and nobody has to remember to regenerate them by
hand — the same "let the scheduler do it" philosophy as the pipeline run
itself.

## Run it yourself

```bash
uvicorn stockpipe.api.main:app --reload &   # notebook needs the API running
jupyter notebook notebooks/explore.ipynb

python scripts/generate_report_images.py    # regenerates docs/assets/*.png directly from the warehouse
```

## What's next

The three-stage "signal → chart → written up" loop this stage completes is
the same one every later addition to this project will follow: a new
analytics function in Stage 5, a new endpoint in Stage 4, a new chart here.
Beyond that, the ⟳ Monitor / Optimize / Govern ring around the pipeline
diagram — logging, data-quality checks, alerting on a failed daily run — is
the natural next thing to build.
