"""
Config Loader — parse ``config.json`` and return structured category/URL data.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from src.logger import setup_logger

log = setup_logger("config")

# Default config path (project root / config / config.json)
_DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "config.json"


@dataclass
class Category:
    """A named group of target URLs to crawl."""

    name: str
    urls: List[str] = field(default_factory=list)


def load_config(path: Path | str | None = None) -> List[Category]:
    """Load and validate the ETL configuration file.

    Args:
        path: Explicit path to ``config.json``.
              Falls back to ``<project_root>/config/config.json``.

    Returns:
        Parsed list of :class:`Category` objects.

    Raises:
        FileNotFoundError: If the config file does not exist.
        ValueError: If the JSON structure is invalid.
    """
    config_path = Path(path) if path else _DEFAULT_CONFIG_PATH

    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    log.info("[info]Loading config from[/info] %s", config_path)

    with open(config_path, "r", encoding="utf-8") as fh:
        raw: dict = json.load(fh)

    categories_raw = raw.get("categories")
    if not isinstance(categories_raw, list):
        raise ValueError("config.json must contain a top-level 'categories' list")

    categories: List[Category] = []
    for idx, cat in enumerate(categories_raw):
        name = cat.get("name")
        urls = cat.get("urls")
        if not name or not isinstance(name, str):
            raise ValueError(f"Category at index {idx} missing valid 'name'")
        if not isinstance(urls, list) or not all(isinstance(u, str) for u in urls):
            raise ValueError(f"Category '{name}' must have a 'urls' list of strings")
        categories.append(Category(name=name, urls=urls))

    total_urls = sum(len(c.urls) for c in categories)
    log.info(
        "[success]Loaded %d categories, %d URLs total[/success]",
        len(categories),
        total_urls,
    )
    return categories
