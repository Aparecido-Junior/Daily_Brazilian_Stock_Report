"""Central configuration loader.

One place that knows how to read the YAML config files. Every stage imports
from here instead of re-reading files, so configuration stays consistent
across the whole pipeline.
"""
from __future__ import annotations

from pathlib import Path
from functools import lru_cache

import yaml

# Repo root = two levels up from this file (stockpipe/config.py -> repo/).
ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"


def _load_yaml(name: str) -> dict:
    with open(CONFIG_DIR / name, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@lru_cache(maxsize=None)
def settings() -> dict:
    """Global settings from config/settings.yml (cached after first read)."""
    return _load_yaml("settings.yml")


@lru_cache(maxsize=None)
def tickers() -> dict:
    """The universe from config/tickers.yml (cached after first read)."""
    return _load_yaml("tickers.yml")


def path(layer: str) -> Path:
    """Absolute path to a storage layer ('raw', 'warehouse', 'reports')."""
    rel = settings()["paths"][layer]
    return ROOT / rel
