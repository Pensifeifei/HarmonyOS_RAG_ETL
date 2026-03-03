"""
main.py — ETL pipeline entry point.

Orchestrates the full flow: Config → Fetch → Clean → Convert → Export.
Supports both full-pipeline mode and discovery-only mode.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from src.config_loader import load_config
from src.cleaner import clean
from src.converter import convert
from src.exporter import export
from src.fetcher import create_browser, fetch_page, FetchError, CONCURRENCY_LIMIT
from src.logger import console, print_banner, setup_logger, create_progress

log = setup_logger("main")


async def run_pipeline(
    config_path: str | None = None,
    output_dir: str | None = None,
    concurrency: int = CONCURRENCY_LIMIT,
    overwrite: bool = False,
    delay: float = 1.0,
) -> None:
    """Run the full ETL pipeline."""
    categories = load_config(config_path)

    total_urls = sum(len(c.urls) for c in categories)
    console.rule("[accent]ETL Pipeline · Start[/accent]")
    log.info(
        "[info]Pipeline config: %d categories, %d URLs, concurrency=%d[/info]",
        len(categories),
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

    pw, browser = await create_browser()
    try:
        with create_progress() as progress:
            task = progress.add_task("Processing pages", total=total_urls)

            for category in categories:
                for url in category.urls:
                    progress.update(task, description=f"[info]{category.name}[/info]")

                    try:
                        # --- Fetch ---
                        html = await fetch_page(url, browser, semaphore=semaphore)

                        # --- Clean ---
                        result = clean(html)
                        if result is None:
                            log.warning(
                                "[warning]⚠ No content found, skipping %s[/warning]", url
                            )
                            stats["failed"] += 1
                            progress.advance(task)
                            continue

                        # --- Convert ---
                        md = convert(result.content)

                        # --- Export ---
                        file_path = export(
                            md,
                            title=result.title,
                            source_url=url,
                            category=category.name,
                            output_dir=out,
                            overwrite=overwrite,
                        )

                        # 判断是 skip 还是 success
                        if file_path.exists() and not overwrite:
                            stats["skipped"] += 1
                        else:
                            stats["success"] += 1

                    except FetchError as exc:
                        log.error("[error]✘ %s[/error]", exc)
                        stats["failed"] += 1
                    except Exception as exc:
                        log.error(
                            "[error]✘ Unexpected error for %s: %s[/error]", url, exc
                        )
                        stats["failed"] += 1

                    progress.advance(task)

                    # 请求间延迟，避免触发反爬
                    if delay > 0:
                        await asyncio.sleep(delay)

    finally:
        await browser.close()
        await pw.stop()

    # --- Summary ---
    console.rule("[accent]ETL Pipeline · Complete[/accent]")
    console.print(
        f"[success]✔ Success: {stats['success']}[/success]  "
        f"[warning]⏭ Skipped: {stats['skipped']}[/warning]  "
        f"[error]✘ Failed: {stats['failed']}[/error]"
    )


async def run_discovery(entry_url: str, config_output: str | None = None) -> None:
    """Run URL discovery from sidebar tree."""
    from src.discovery import discover
    await discover(entry_url, config_output=config_output)


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
    p_disc.add_argument("entry_url", help="Guide index page URL")
    p_disc.add_argument(
        "-o", "--output", default=None, help="Output path for config.json"
    )

    # --- run ---
    p_run = sub.add_parser("run", help="Run the full ETL pipeline")
    p_run.add_argument(
        "-c", "--config", default=None, help="Path to config.json"
    )
    p_run.add_argument(
        "-o", "--output-dir", default=None, help="Output directory"
    )
    p_run.add_argument(
        "--concurrency", type=int, default=CONCURRENCY_LIMIT,
        help=f"Max concurrent fetches (default: {CONCURRENCY_LIMIT})",
    )
    p_run.add_argument(
        "--overwrite", action="store_true", help="Overwrite existing files"
    )
    p_run.add_argument(
        "--delay", type=float, default=1.0,
        help="Delay in seconds between requests (default: 1.0)",
    )

    args = parser.parse_args()

    if args.command == "discover":
        asyncio.run(run_discovery(args.entry_url, args.output))
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
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
