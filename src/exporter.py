"""
Exporter — write Markdown files with YAML frontmatter and incremental skip.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml

from src.logger import setup_logger

log = setup_logger("exporter")

# Default output root
_DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"


def _slug_from_url(url: str) -> str:
    """Derive a filesystem-safe slug from a HarmonyOS doc URL.

    Example
    -------
    >>> _slug_from_url("https://…/harmonyos-guides/arkts-rendering-control-ifelse")
    'arkts-rendering-control-ifelse'
    """
    # 取 URL 最后一段路径
    last_segment = url.rstrip("/").rsplit("/", maxsplit=1)[-1]
    # 移除不安全字符
    slug = re.sub(r"[^\w\-]", "_", last_segment)
    return slug


def _build_frontmatter(
    title: str,
    source_url: str,
    section: str,
    category: str,
    crawled_at: str,
) -> str:
    """Generate YAML frontmatter block."""
    meta = {
        "title": title,
        "source_url": source_url,
        "section": section,
        "category": category,
        "crawled_at": crawled_at,
    }
    # yaml.dump 默认 allow_unicode=True 以保留中文标题
    yaml_str = yaml.dump(meta, allow_unicode=True, default_flow_style=False, sort_keys=False)
    return f"---\n{yaml_str}---\n\n"


def export(
    markdown: str,
    *,
    title: str,
    source_url: str,
    section: str = "guide",
    category: str,
    output_dir: Optional[Path] = None,
    overwrite: bool = False,
) -> Path:
    """Write a Markdown file with frontmatter to the output directory.

    Args:
        markdown: The body Markdown content.
        title: Document title (goes into frontmatter).
        source_url: Original URL of the doc page.
        section: Section name (``guide``, ``api``, ``best-practices``).
                 Determines the top-level output subdirectory.
        category: Category name used as subdirectory under section.
        output_dir: Root output directory (default: ``<project>/output/``).
        overwrite: If ``False`` (default), skip files that already exist.

    Returns:
        The :class:`Path` of the written (or skipped) file.
    """
    root = output_dir or _DEFAULT_OUTPUT_DIR
    # 按 section / category 两层分目录
    cat_dir = root / section / category
    cat_dir.mkdir(parents=True, exist_ok=True)

    slug = _slug_from_url(source_url)
    file_path = cat_dir / f"{slug}.md"

    # 增量跳过
    if file_path.exists() and not overwrite:
        log.info("[warning]⏭  SKIP (exists)[/warning] %s", file_path)
        return file_path

    crawled_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    frontmatter = _build_frontmatter(title, source_url, section, category, crawled_at)

    full_content = frontmatter + markdown

    file_path.write_text(full_content, encoding="utf-8")
    log.info("[success]✔ Exported[/success] %s", file_path)
    return file_path
