"""One-time helper: creates the 3 files that couldn't be written remotely
(.env and the two GitHub Actions workflow files) with the exact right
content. Safe to delete after running once.

Run:  python finish_setup.py
"""
import os

FILES = {
    ".env": """DATABASE_URL=postgresql://postgres.spkehnnjnkpooxqueusa:879561k9%40Cidoju@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres
""",
    ".github/workflows/daily_pipeline.yml": """name: Daily pipeline run

# This is the "scheduler" in the Monitor/Optimize/Govern ring around the
# pipeline diagram in the README: it's what actually triggers Stage 2 -> 3
# every day, on GitHub's own servers, so nobody has to remember to run it
# by hand. Free on public repos.
#
# Setup (one-time): add a repository secret named DATABASE_URL with your
# Neon/Supabase Postgres connection string.
# Settings -> Secrets and variables -> Actions -> New repository secret.

on:
  schedule:
    # 21:15 UTC = 18:15 America/Sao_Paulo — shortly after the B3 close.
    - cron: "15 21 * * 1-5"
  workflow_dispatch: {}  # lets you trigger a run manually from the Actions tab

jobs:
  run-pipeline:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run Stage 2 -> Stage 3
        env:
          DATABASE_URL: ${{ secrets.DATABASE_URL }}
        run: python -m stockpipe.run_daily
""",
    ".github/workflows/tests.yml": """name: Tests

# Runs the test suite on every push/PR. Note this does NOT need the
# DATABASE_URL secret: the storage tests that need a live database
# skip themselves when it's absent (see tests/test_storage.py).

on:
  push:
    branches: ["main"]
  pull_request:

jobs:
  pytest:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run tests
        run: pytest tests/ -v
""",
}

for relpath, content in FILES.items():
    os.makedirs(os.path.dirname(relpath) or ".", exist_ok=True)
    with open(relpath, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    print(f"wrote {relpath}")

print("\nDone. You can delete finish_setup.py now if you like.")
