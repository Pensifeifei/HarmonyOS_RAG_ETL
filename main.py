"""
main.py — ETL pipeline entry point.

Orchestrates the full flow: Config → Fetch → Clean → Convert → Export.
Supports both full-pipeline mode and discovery-only mode.
Handles multiple documentation sections (guide, api, best-practices).

Failed URLs are collected and retried after the main pass, with remaining
failures saved to ``output/failed_urls.json`` for manual review.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from dataclasses import dataclass
from pathlib import Path

from src.config_loader import load_config, SECTION_DEFINITIONS
from src.cleaner import clean
from src.converter import convert
from src.exporter import export
from src.fetcher import create_browser, fetch_page, FetchError, CONCURRENCY_LIMIT
from src.logger import console, print_banner, setup_logger, create_progress

log = setup_logger("main")


# ---------------------------------------------------------------------------
# Data model for tracking failures
# ---------------------------------------------------------------------------

@dataclass
class FailedItem:
    """A URL that failed during the main ETL pass."""
    url: str
    section_name: str
    category_name: str
    error: str


# ---------------------------------------------------------------------------
# Single-page ETL helper
# ---------------------------------------------------------------------------

async def _process_page(
    url: str,
    section_name: str,
    category_name: str,
    browser,
    semaphore: asyncio.Semaphore,
    out: Path,
    overwrite: bool,
) -> str:
    """Process a single page through Fetch → Clean → Convert → Export.

    Returns:
        ``"success"``, ``"skipped"``, or raises on failure.
    """
    html = await fetch_page(url, browser, semaphore=semaphore)

    result = clean(html)
    if result is None:
        log.warning("[warning]⚠ No content found, skipping %s[/warning]", url)
        raise ValueError(f"No content found for {url}")

    md = convert(result.content)

    file_path = export(
        md,
        title=result.title,
        source_url=url,
        section=section_name,
        category=category_name,
        output_dir=out,
        overwrite=overwrite,
    )

    if file_path.exists() and not overwrite:
        return "skipped"
    return "success"


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

async def run_pipeline(
    config_path: str | None = None,
    output_dir: str | None = None,
    concurrency: int = CONCURRENCY_LIMIT,
    overwrite: bool = False,
    delay: float = 1.0,
) -> None:
    """Run the full ETL pipeline across all sections."""
    sections = load_config(config_path)

    total_urls = sum(len(c.urls) for s in sections for c in s.categories)
    console.rule("[accent]ETL Pipeline · Start[/accent]")
    log.info(
        "[info]Pipeline config: %d sections, %d URLs, concurrency=%d[/info]",
        len(sections),
        total_urls,
        concurrency,
    )

    out = Path(output_dir) if output_dir else Path("output")
    semaphore = asyncio.Semaphore(concurrency)

    # 日志持久化到文件
    log_file = out / "etl.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)-8s %(message)s")
    )
    logging.getLogger().addHandler(file_handler)
    log.info("[info]Log file: %s[/info]", log_file)

    stats = {"success": 0, "skipped": 0, "failed": 0}
    failed_list: list[FailedItem] = []

    pw, browser = await create_browser()
    try:
        # ==================================================================
        # Pass 1: Main ETL
        # ==================================================================
        with create_progress() as progress:
            task = progress.add_task("Processing pages", total=total_urls)

            for section in sections:
                console.rule(
                    f"[accent]Section · {section.name} "
                    f"({len(section.categories)} categories)[/accent]"
                )

                for category in section.categories:
                    for url in category.urls:
                        progress.update(
                            task,
                            description=(
                                f"[info][{section.name}] {category.name}[/info]"
                            ),
                        )

                        try:
                            result = await _process_page(
                                url, section.name, category.name,
                                browser, semaphore, out, overwrite,
                            )
                            stats[result] += 1

                        except FetchError as exc:
                            log.error("[error]✘ %s[/error]", exc)
                            stats["failed"] += 1
                            failed_list.append(FailedItem(
                                url=url,
                                section_name=section.name,
                                category_name=category.name,
                                error=str(exc),
                            ))
                        except Exception as exc:
                            log.error(
                                "[error]✘ Unexpected error for %s: %s[/error]",
                                url, exc,
                            )
                            stats["failed"] += 1
                            failed_list.append(FailedItem(
                                url=url,
                                section_name=section.name,
                                category_name=category.name,
                                error=str(exc),
                            ))

                        progress.advance(task)

                        if delay > 0:
                            await asyncio.sleep(delay)

        # ==================================================================
        # Pass 2: Retry failed URLs (with increased timeout)
        # ==================================================================
        if failed_list:
            console.rule(
                f"[accent]Retry Pass · {len(failed_list)} failed URLs[/accent]"
            )
            log.info(
                "[info]Retrying %d failed URLs with increased timeout…[/info]",
                len(failed_list),
            )

            # 临时增大超时进行第二轮重试
            from src import fetcher
            original_timeout = fetcher.DEFAULT_TIMEOUT_MS
            fetcher.DEFAULT_TIMEOUT_MS = 45_000

            still_failed: list[FailedItem] = []

            with create_progress() as progress:
                retry_task = progress.add_task(
                    "Retrying failed", total=len(failed_list)
                )

                for item in failed_list:
                    progress.update(
                        retry_task,
                        description=(
                            f"[warning][RETRY] {item.section_name}/{item.category_name}[/warning]"
                        ),
                    )

                    try:
                        result = await _process_page(
                            item.url, item.section_name, item.category_name,
                            browser, semaphore, out, overwrite,
                        )
                        # 重试成功：修正统计
                        stats["failed"] -= 1
                        stats[result] += 1
                        log.info(
                            "[success]✔ Retry succeeded:[/success] %s", item.url
                        )
                    except Exception as exc:
                        log.error(
                            "[error]✘ Retry also failed for %s: %s[/error]",
                            item.url, exc,
                        )
                        still_failed.append(FailedItem(
                            url=item.url,
                            section_name=item.section_name,
                            category_name=item.category_name,
                            error=str(exc),
                        ))

                    progress.advance(retry_task)

                    if delay > 0:
                        await asyncio.sleep(delay)

            # 恢复原始超时
            fetcher.DEFAULT_TIMEOUT_MS = original_timeout
            failed_list = still_failed

    finally:
        await browser.close()
        await pw.stop()

    # ==================================================================
    # Save remaining failures as config.json-compatible format
    # ==================================================================
    failed_path = out / "failed_urls.json"
    if failed_list:
        failed_config = _build_failed_config(failed_list)
        failed_path.write_text(
            json.dumps(failed_config, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        log.info(
            "[warning]⚠ %d URLs still failed after retry, saved to %s[/warning]",
            len(failed_list),
            failed_path,
        )
    elif failed_path.exists():
        # 上一次遗留的 failed_urls.json 已无用，清理掉
        failed_path.unlink()
        log.info("[success]✔ Previous failed_urls.json cleared (all succeeded)[/success]")

    # --- Summary ---
    console.rule("[accent]ETL Pipeline · Complete[/accent]")
    console.print(
        f"[success]✔ Success: {stats['success']}[/success]  "
        f"[warning]⏭ Skipped: {stats['skipped']}[/warning]  "
        f"[error]✘ Failed: {stats['failed']}[/error]"
    )
    if failed_list:
        console.print(
            f"[warning]📋 Failed URLs saved to: {failed_path}[/warning]"
        )
        console.print(
            "[warning]   Run [bold]python main.py retry[/bold] to re-process them[/warning]"
        )


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

async def run_discovery(
    entry_url: str | None = None,
    section_name: str = "guide",
    config_output: str | None = None,
    discover_all_flag: bool = False,
) -> None:
    """Run URL discovery for one or all sections."""
    if discover_all_flag:
        from src.discovery import discover_all
        await discover_all(SECTION_DEFINITIONS, config_output=config_output)
    else:
        from src.discovery import discover
        url = entry_url or SECTION_DEFINITIONS[0]["entry_url"]
        await discover(url, section_name=section_name, config_output=config_output)


# ---------------------------------------------------------------------------
# Failed URL config builder
# ---------------------------------------------------------------------------

def _build_failed_config(failed_list: list[FailedItem]) -> dict:
    """Convert a flat list of FailedItems into config.json-compatible format.

    Groups failures by section and category, producing the same ``sections``
    structure that :func:`load_config` expects.  This allows re-processing
    via ``python main.py retry`` or ``python main.py run -c output/failed_urls.json``.
    """
    from collections import OrderedDict

    # section_name -> category_name -> [urls]
    tree: dict[str, dict[str, list[str]]] = OrderedDict()
    for item in failed_list:
        cats = tree.setdefault(item.section_name, OrderedDict())
        cats.setdefault(item.category_name, []).append(item.url)

    sections = []
    for s_name, cats in tree.items():
        categories = [
            {"name": c_name, "urls": urls}
            for c_name, urls in cats.items()
        ]
        sections.append({"name": s_name, "categories": categories})

    return {"sections": sections}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    """CLI entry point."""
    print_banner()

    parser = argparse.ArgumentParser(
        description="HarmonyOS RAG ETL Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", help="Available commands")

    # --- discover ---
    p_disc = sub.add_parser("discover", help="Auto-discover URLs from sidebar tree")
    p_disc.add_argument(
        "entry_url", nargs="?", default=None,
        help="Section index page URL (omit if using --all)",
    )
    p_disc.add_argument(
        "--section", default="guide",
        help="Section name (guide/api/best-practices, default: guide)",
    )
    p_disc.add_argument(
        "--all", action="store_true", dest="discover_all",
        help="Discover all three sections (guide + api + best-practices)",
    )
    p_disc.add_argument(
        "-o", "--output", default=None, help="Output path for config.json",
    )

    # --- run ---
    p_run = sub.add_parser("run", help="Run the full ETL pipeline")
    p_run.add_argument(
        "-c", "--config", default=None, help="Path to config.json",
    )
    p_run.add_argument(
        "-o", "--output-dir", default=None, help="Output directory",
    )
    p_run.add_argument(
        "--concurrency", type=int, default=CONCURRENCY_LIMIT,
        help=f"Max concurrent fetches (default: {CONCURRENCY_LIMIT})",
    )
    p_run.add_argument(
        "--overwrite", action="store_true", help="Overwrite existing files",
    )
    p_run.add_argument(
        "--delay", type=float, default=1.0,
        help="Delay in seconds between requests (default: 1.0)",
    )

    # --- retry ---
    p_retry = sub.add_parser(
        "retry", help="Re-process failed URLs from output/failed_urls.json",
    )
    p_retry.add_argument(
        "-o", "--output-dir", default=None, help="Output directory",
    )
    p_retry.add_argument(
        "--concurrency", type=int, default=CONCURRENCY_LIMIT,
        help=f"Max concurrent fetches (default: {CONCURRENCY_LIMIT})",
    )
    p_retry.add_argument(
        "--delay", type=float, default=1.0,
        help="Delay in seconds between requests (default: 1.0)",
    )

    args = parser.parse_args()

    if args.command == "discover":
        asyncio.run(
            run_discovery(
                entry_url=args.entry_url,
                section_name=args.section,
                config_output=args.output,
                discover_all_flag=args.discover_all,
            )
        )
    elif args.command == "run":
        asyncio.run(
            run_pipeline(
                config_path=args.config,
                output_dir=args.output_dir,
                concurrency=args.concurrency,
                overwrite=args.overwrite,
                delay=args.delay,
            )
        )
    elif args.command == "retry":
        out = Path(args.output_dir) if args.output_dir else Path("output")
        failed_config = out / "failed_urls.json"
        if not failed_config.exists():
            console.print("[success]\u2714 No failed_urls.json found \u2014 nothing to retry[/success]")
            sys.exit(0)
        asyncio.run(
            run_pipeline(
                config_path=str(failed_config),
                output_dir=args.output_dir,
                concurrency=args.concurrency,
                overwrite=True,
                delay=args.delay,
            )
        )
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
