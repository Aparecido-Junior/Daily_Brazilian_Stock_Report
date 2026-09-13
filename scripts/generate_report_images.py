"""Generate the chart images embedded in README.md, straight from the warehouse.

Deliberately queries stockpipe.analytics directly (not through the Stage 4
API over HTTP) — this script's whole job is to produce three PNGs, so
there's no reason to stand up a server just to call it. The API and this
script are two different clients of the same analytics functions, which is
the point of keeping that logic in one module instead of inlining SQL in
either place.

Run manually:      python scripts/generate_report_images.py
Run automatically:  the last step of .github/workflows/daily_pipeline.yml,
                     which also commits the refreshed PNGs back to the repo
                     — so the charts in README.md are never more than a day
                     stale, without anyone needing to remember to update them.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # no display available in CI or most terminals
import matplotlib.pyplot as plt
import pandas as pd

from stockpipe.analytics import queries as analytics
from stockpipe.storage import db

OUT_DIR = Path(__file__).resolve().parent.parent / "docs" / "assets"

# One consistent palette across all three charts, so the same ticker always
# gets the same color if you look at more than one image side by side.
_PALETTE = [
    "#4C72B0", "#DD8452", "#55A868", "#C44E52", "#8172B2",
    "#937860", "#DA8BC3", "#8C8C8C", "#CCB974",
]


def _color_map(tickers: list[str]) -> dict[str, str]:
    return {t: _PALETTE[i % len(_PALETTE)] for i, t in enumerate(sorted(tickers))}


def cumulative_returns_chart(out_path: Path) -> None:
    """'Which of these would you rather have owned' — every ticker rebased to 0%."""
    df = analytics.all_cumulative_returns()
    if df.empty:
        print(f"skipping {out_path.name}: no data yet")
        return

    df["trade_date"] = pd.to_datetime(df["trade_date"])
    colors = _color_map(df["ticker"].unique().tolist())

    fig, ax = plt.subplots(figsize=(10, 5.5))
    for ticker, g in df.sort_values("trade_date").groupby("ticker"):
        style = "--" if ticker == "^BVSP" else "-"
        width = 2.5 if ticker == "^BVSP" else 1.5
        ax.plot(g["trade_date"], g["cum_return"] * 100, style, label=ticker,
                color=colors[ticker], linewidth=width)

    ax.axhline(0, color="#888888", linewidth=0.8)
    ax.set_title("Cumulative return since first date on record")
    ax.set_ylabel("Return (%)")
    ax.legend(loc="upper left", fontsize=8, ncol=2)
    ax.grid(alpha=0.25)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"wrote {out_path}")


def correlation_heatmap(out_path: Path) -> None:
    """How closely each stock's daily moves track every other stock's."""
    df = analytics.all_daily_returns()
    if df.empty:
        print(f"skipping {out_path.name}: no data yet")
        return

    wide = df.pivot(index="trade_date", columns="ticker", values="daily_return")
    corr = wide.corr()

    fig, ax = plt.subplots(figsize=(7, 6))
    im = ax.imshow(corr, vmin=-1, vmax=1, cmap="RdBu_r")
    ax.set_xticks(range(len(corr.columns)))
    ax.set_xticklabels(corr.columns, rotation=45, ha="right", fontsize=8)
    ax.set_yticks(range(len(corr.columns)))
    ax.set_yticklabels(corr.columns, fontsize=8)
    for i in range(len(corr.columns)):
        for j in range(len(corr.columns)):
            ax.text(j, i, f"{corr.iloc[i, j]:.2f}", ha="center", va="center", fontsize=7,
                     color="white" if abs(corr.iloc[i, j]) > 0.5 else "black")
    ax.set_title("Daily-return correlation")
    fig.colorbar(im, ax=ax, shrink=0.8, label="correlation")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"wrote {out_path}")


def leaderboard_chart(out_path: Path) -> None:
    """Every tracked stock, ranked by performance vs. the Ibovespa benchmark."""
    df = analytics.leaderboard()
    if df.empty:
        print(f"skipping {out_path.name}: no data yet")
        return

    df = df.sort_values("relative_performance")
    colors = ["#55A868" if v >= 0 else "#C44E52" for v in df["relative_performance"]]

    fig, ax = plt.subplots(figsize=(8, 0.5 * len(df) + 1.5))
    ax.barh(df["ticker"], df["relative_performance"] * 100, color=colors)
    ax.axvline(0, color="#888888", linewidth=0.8)
    ax.set_xlabel("Return vs. Ibovespa (percentage points)")
    ax.set_title("Leaderboard: performance relative to the benchmark")
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"wrote {out_path}")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    engine = db.get_engine()  # fail fast with a clear error if DATABASE_URL is missing
    del engine

    cumulative_returns_chart(OUT_DIR / "cumulative_returns.png")
    correlation_heatmap(OUT_DIR / "correlation_heatmap.png")
    leaderboard_chart(OUT_DIR / "leaderboard.png")


if __name__ == "__main__":
    main()
