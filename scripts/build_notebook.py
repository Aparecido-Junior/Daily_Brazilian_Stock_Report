"""One-off generator for notebooks/explore.ipynb.

Not part of the pipeline itself — just a reproducible way to build the
starter notebook via nbformat instead of hand-editing JSON. Re-run this if
you want to regenerate the notebook from scratch:
    python scripts/build_notebook.py
"""
import nbformat as nbf

nb = nbf.v4.new_notebook()

md = lambda src: nbf.v4.new_markdown_cell(src)
code = lambda src: nbf.v4.new_code_cell(src)

nb.cells = [
    md("""\
# Exploring the Daily Brazilian Stock Report — as an API client

This notebook is deliberately **not** where the data lives. It's a client:
it talks to the Stage 4 API (`stockpipe/api/main.py`), the same way a
dashboard or another application would. That's the point of building a
serving layer — nothing needs direct database access, notebooks included.

**Before running this:** start the API in a terminal —

```bash
uvicorn stockpipe.api.main:app --reload
```
"""),
    code("""\
import requests
import pandas as pd

API = "http://127.0.0.1:8000"

requests.get(f"{API}/health").json()
"""),
    md("## The tracked universe (Stage 1, via the API)"),
    code("""\
symbols = requests.get(f"{API}/symbols").json()
pd.DataFrame(symbols)
"""),
    md("## Price history for one ticker"),
    code("""\
ticker = "PETR4.SA"
rows = requests.get(f"{API}/prices/{ticker}", params={"limit": 200}).json()
df = pd.DataFrame(rows)
df["trade_date"] = pd.to_datetime(df["trade_date"])
df = df.sort_values("trade_date")
df.tail()
"""),
    code("""\
import matplotlib.pyplot as plt

fig, ax = plt.subplots(figsize=(9, 4))
ax.plot(df["trade_date"], df["close"])
ax.set_title(f"{ticker} — close price")
ax.set_xlabel("Date")
ax.set_ylabel("Close (BRL)")
fig.autofmt_xdate()
plt.show()
"""),
    md("## Latest close across the whole universe"),
    code("""\
report = requests.get(f"{API}/report/latest").json()
pd.DataFrame(report["rows"]).sort_values("close", ascending=False)
"""),
    md("""\
## Stage 5 — Analytics: moving averages & volatility

Everything from here on calls the new `/analytics/*` endpoints added in
Stage 5. Same rule as before: this notebook never touches Postgres or SQL
directly — it's just another HTTP client of the Stage 4 API, which now
also serves computed metrics instead of only raw rows.
"""),
    code("""\
rows = requests.get(f"{API}/analytics/prices/{ticker}", params={"limit": 300}).json()
ma = pd.DataFrame(rows)
ma["trade_date"] = pd.to_datetime(ma["trade_date"])
ma = ma.sort_values("trade_date")
ma.tail()
"""),
    code("""\
fig, ax = plt.subplots(figsize=(10, 5))
ax.plot(ma["trade_date"], ma["close"], label="close", linewidth=1, color="#4C72B0")
ax.plot(ma["trade_date"], ma["ma_20"], label="20-day MA", linewidth=1.5, color="#DD8452")
ax.plot(ma["trade_date"], ma["ma_50"], label="50-day MA", linewidth=1.5, color="#55A868")
ax.set_title(f"{ticker} — price with moving averages")
ax.set_ylabel("Close (BRL)")
ax.legend()
fig.autofmt_xdate()
plt.show()
"""),
    md("""\
## Stage 6 — Visualization: which stock would you rather have owned?

Raw price charts don't compare well across tickers with different price
scales (a R$100 stock and a R$10 stock can't share a y-axis meaningfully).
Cumulative return since day one — everything rebased to 0% — fixes that,
and overlaying the Ibovespa (`^BVSP`) as the benchmark answers the
question that actually matters: not just "did it go up", but "did it beat
the index".
"""),
    code("""\
rows = requests.get(f"{API}/analytics/cumulative-returns").json()
cum = pd.DataFrame(rows)
cum["trade_date"] = pd.to_datetime(cum["trade_date"])

fig, ax = plt.subplots(figsize=(10, 5.5))
for tkr, g in cum.sort_values("trade_date").groupby("ticker"):
    style = "--" if tkr == "^BVSP" else "-"
    width = 2.5 if tkr == "^BVSP" else 1.3
    ax.plot(g["trade_date"], g["cum_return"] * 100, style, label=tkr, linewidth=width)

ax.axhline(0, color="#888888", linewidth=0.8)
ax.set_title("Cumulative return since first date on record")
ax.set_ylabel("Return (%)")
ax.legend(loc="upper left", fontsize=8, ncol=2)
fig.autofmt_xdate()
plt.show()
"""),
    md("## Correlation between tickers' daily moves"),
    code("""\
rows = requests.get(f"{API}/analytics/daily-returns").json()
daily = pd.DataFrame(rows)
wide = daily.pivot(index="trade_date", columns="ticker", values="daily_return")
corr = wide.corr()

fig, ax = plt.subplots(figsize=(7, 6))
im = ax.imshow(corr, vmin=-1, vmax=1, cmap="RdBu_r")
ax.set_xticks(range(len(corr.columns))); ax.set_xticklabels(corr.columns, rotation=45, ha="right", fontsize=8)
ax.set_yticks(range(len(corr.columns))); ax.set_yticklabels(corr.columns, fontsize=8)
fig.colorbar(im, ax=ax, shrink=0.8, label="correlation")
ax.set_title("Daily-return correlation")
plt.show()
"""),
    md("## Leaderboard: everyone vs. the Ibovespa"),
    code("""\
rows = requests.get(f"{API}/analytics/leaderboard").json()
board = pd.DataFrame(rows).sort_values("relative_performance")

colors = ["#55A868" if v >= 0 else "#C44E52" for v in board["relative_performance"]]
fig, ax = plt.subplots(figsize=(8, 0.5 * len(board) + 1.5))
ax.barh(board["ticker"], board["relative_performance"] * 100, color=colors)
ax.axvline(0, color="#888888", linewidth=0.8)
ax.set_xlabel("Return vs. Ibovespa (percentage points)")
ax.set_title("Leaderboard: performance relative to the benchmark")
plt.show()
"""),
]

with open("notebooks/explore.ipynb", "w") as f:
    nbf.write(nb, f)

print("wrote notebooks/explore.ipynb")
