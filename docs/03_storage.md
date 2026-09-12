# Stage 3 — Storage

> *"Ingestion happens once a day and then the process exits. Storage is what's still there tomorrow."*

## What this stage is

Storage takes Stage 2's tidy DataFrame and writes it somewhere durable,
shared, and queryable: a real **Postgres** database, hosted in the cloud
(this project uses a free [Neon](https://neon.tech) or
[Supabase](https://supabase.com) instance — either works, the code only
needs a standard Postgres connection string).

This is a deliberate change from "just write a parquet file to disk." A file
on one laptop is invisible to anything else — another process, a teammate, a
scheduled job running on GitHub's servers instead of your machine. A hosted
database is reachable from all of them, which is what makes Stage 4 (an API)
and a scheduled daily run (GitHub Actions) both possible without copying
files around.

## The idempotency problem, and upserts

The pipeline re-runs every day and re-fetches a rolling lookback window
(`ingestion.lookback_days` in `settings.yml`) — so most days it re-pulls data
it already has, on purpose (it's simpler than tracking exactly what's new,
and it lets a late/corrected price from the exchange overwrite what we
stored yesterday).

That means storage must be **idempotent**: running the same day's ingestion
twice must leave the database in the same state as running it once — not
duplicate rows, not an error. The mechanism is a SQL **upsert**:

```sql
INSERT INTO prices (...) VALUES (...)
ON CONFLICT (ticker, trade_date) DO UPDATE SET ...
```

A `UNIQUE (ticker, trade_date)` constraint is what makes "conflict" mean
something — it's the database enforcing our tidy contract (one row per
ticker per day) even if the pipeline gets re-run, retried, or backfilled.

## Config-as-code, applied to credentials

Stage 1's `settings.yml` keeps *behaviour* out of hardcoded Python. This
stage applies the same principle to *credentials*: the connection string
lives in the `DATABASE_URL` environment variable, never in a source file.

- Locally: copy `.env.example` to `.env` and fill in your real connection
  string. `.env` is gitignored — it never reaches GitHub.
- In the scheduled run: `DATABASE_URL` is a **GitHub Actions secret**,
  injected as a real environment variable only for the duration of that
  run. See `.github/workflows/daily_pipeline.yml`.

If `DATABASE_URL` isn't set at all, `db.get_engine()` raises a clear
`StorageNotConfigured` error pointing you at `.env.example` — instead of a
confusing connection-refused stack trace three layers down.

## Run it

```bash
cp .env.example .env         # then edit .env with your real connection string
python -m stockpipe.storage.db
```

This creates the `prices` table if it doesn't exist yet and prints a summary
of what's in the warehouse right now.

## What's next — Stage 4 (Serving / API)

Data sitting in a database only you can query isn't much more useful than a
file on your laptop — it just moved. Stage 4 puts a small API in front of
it, so a notebook, a dashboard, or a teammate can get at the data over HTTP
without ever needing the database password.
