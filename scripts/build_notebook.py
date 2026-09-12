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
    md("## Latest close across the whole universe (Stage 6 preview)"),
    code("""\
report = requests.get(f"{API}/report/latest").json()
pd.DataFrame(report["rows"]).sort_values("close", ascending=False)
"""),
]

with open("notebooks/explore.ipynb", "w") as f:
    nbf.write(nb, f)

print("wrote notebooks/explore.ipynb")
