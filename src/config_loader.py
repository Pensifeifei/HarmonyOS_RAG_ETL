"""
Config Loader — parse ``config.json`` and return structured section/category/URL data.

Supports both new multi-section format (``sections``) and legacy flat format
(``categories``). The legacy format is automatically wrapped into a single
``guide`` section for backward compatibility.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from src.logger import setup_logger

log = setup_logger("config")

# Default config path (project root / config / config.json)
_DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "config.json"


@dataclass
class Category:
    """A named group of target URLs to crawl."""

    name: str
    urls: List[str] = field(default_factory=list)


@dataclass
class Section:
    """A documentation section (e.g. guide, api, best-practices).

    Each section maps to a top-level output subdirectory and contains
    its own list of categories discovered from the sidebar tree.
    """

    name: str
    entry_url: str = ""
    categories: List[Category] = field(default_factory=list)


# Pre-defined section definitions for one-click discovery
SECTION_DEFINITIONS: List[dict] = [
    {
        "name": "guide",
        "entry_url": (
            "https://developer.huawei.com/consumer/cn/doc/"
            "harmonyos-guides/application-dev-guide"
        ),
    },
    {
        "name": "api",
        "entry_url": (
            "https://developer.huawei.com/consumer/cn/doc/"
            "harmonyos-references/development-intro-api"
        ),
    },
    {
        "name": "best-practices",
        "entry_url": (
            "https://developer.huawei.com/consumer/cn/doc/"
            "best-practices/bpta-best-practices-overview"
        ),
    },
]


def _parse_categories(raw_list: list, context: str = "") -> List[Category]:
    """Parse a list of raw category dicts into Category objects."""
    categories: List[Category] = []
    for idx, cat in enumerate(raw_list):
        name = cat.get("name")
        urls = cat.get("urls")
        if not name or not isinstance(name, str):
            raise ValueError(f"Category at index {idx}{context} missing valid 'name'")
        if not isinstance(urls, list) or not all(isinstance(u, str) for u in urls):
            raise ValueError(f"Category '{name}' must have a 'urls' list of strings")
        categories.append(Category(name=name, urls=urls))
    return categories


def load_config(path: Path | str | None = None) -> List[Section]:
    """Load and validate the ETL configuration file.

    Args:
        path: Explicit path to ``config.json``.
              Falls back to ``<project_root>/config/config.json``.

    Returns:
        Parsed list of :class:`Section` objects.

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

    # --- New multi-section format ---
    if "sections" in raw:
        sections_raw = raw["sections"]
        if not isinstance(sections_raw, list):
            raise ValueError("'sections' must be a list")

        sections: List[Section] = []
        for s_idx, s_raw in enumerate(sections_raw):
            s_name = s_raw.get("name")
            if not s_name or not isinstance(s_name, str):
                raise ValueError(f"Section at index {s_idx} missing valid 'name'")

            entry_url = s_raw.get("entry_url", "")
            cats = _parse_categories(
                s_raw.get("categories", []),
                context=f" in section '{s_name}'",
            )
            sections.append(Section(name=s_name, entry_url=entry_url, categories=cats))

        total_cats = sum(len(s.categories) for s in sections)
        total_urls = sum(len(c.urls) for s in sections for c in s.categories)
        log.info(
            "[success]Loaded %d sections, %d categories, %d URLs total[/success]",
            len(sections),
            total_cats,
            total_urls,
        )
        return sections

    # --- Legacy flat format (backward compatibility) ---
    categories_raw = raw.get("categories")
    if isinstance(categories_raw, list):
        cats = _parse_categories(categories_raw)
        section = Section(name="guide", categories=cats)

        total_urls = sum(len(c.urls) for c in cats)
        log.info(
            "[success]Loaded (legacy) 1 section, %d categories, %d URLs total[/success]",
            len(cats),
            total_urls,
        )
        return [section]

    raise ValueError(
        "config.json must contain either a 'sections' list or a 'categories' list"
    )
