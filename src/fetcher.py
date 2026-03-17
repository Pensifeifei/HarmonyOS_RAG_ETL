"""
Fetcher — async Playwright engine for rendering HarmonyOS SPA pages.

Handles timeout, exponential-backoff retry, and concurrency limiting.
"""

from __future__ import annotations

import asyncio
from typing import Optional

from playwright.async_api import async_playwright, Browser, Page

from src.logger import setup_logger

log = setup_logger("fetcher")

# ---------------------------------------------------------------------------
# Tunables
# ---------------------------------------------------------------------------
DEFAULT_TIMEOUT_MS: int = 45_000
MAX_RETRIES: int = 3
BACKOFF_BASE: float = 1.5
CONCURRENCY_LIMIT: int = 3

# CSS selector that signals the SPA has finished rendering doc content
_CONTENT_READY_SELECTOR = "div.idpContent"


class FetchError(Exception):
    """Raised when all retry attempts for a URL are exhausted."""


async def fetch_page(
    url: str,
    browser: Browser,
    *,
    semaphore: Optional[asyncio.Semaphore] = None,
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
    max_retries: int = MAX_RETRIES,
) -> str:
    """Render a single SPA page and return its full HTML.

    Args:
        url: Target documentation URL.
        browser: A running Playwright :class:`Browser` instance.
        semaphore: Optional concurrency limiter.
        timeout_ms: Maximum wait (ms) for the content selector to appear.
        max_retries: Number of retry attempts on failure.

    Returns:
        The fully-rendered HTML string of the page.

    Raises:
        FetchError: If all retries are exhausted.
    """
    sem = semaphore or asyncio.Semaphore(CONCURRENCY_LIMIT)

    async with sem:
        last_exc: Optional[Exception] = None

        for attempt in range(1, max_retries + 1):
            page: Optional[Page] = None
            try:
                page = await browser.new_page()
                log.info(
                    "[info]Fetching[/info] (attempt %d/%d) %s",
                    attempt,
                    max_retries,
                    url,
                )

                # domcontentloaded 即可——Angular SPA 有持续连接，networkidle 会永久等待
                await page.goto(url, wait_until="domcontentloaded", timeout=60_000)

                # 等待 SPA 渲染完成：正文容器挂载到 DOM
                # 使用 attached 而非 visible —— 某些页面在渲染初期
                # 元素短暂 0 高度，visible 状态会误判超时
                await page.wait_for_selector(
                    _CONTENT_READY_SELECTOR,
                    state="attached",
                    timeout=timeout_ms,
                )

                # 等待内容完全渲染（代码高亮、图片懒加载等）
                await page.wait_for_timeout(1500)

                html: str = await page.content()
                log.info("[success]✔ Fetched[/success] %s", url)
                return html

            except Exception as exc:
                last_exc = exc
                delay = BACKOFF_BASE**attempt
                log.warning(
                    "[warning]Attempt %d failed for %s: %s — retrying in %.1fs[/warning]",
                    attempt,
                    url,
                    exc,
                    delay,
                )
                await asyncio.sleep(delay)
            finally:
                if page:
                    await page.close()

        raise FetchError(
            f"All {max_retries} attempts failed for {url}: {last_exc}"
        )


async def create_browser() -> tuple:
    """Launch a Playwright Chromium browser.

    Returns:
        A ``(playwright_instance, browser)`` tuple.
        Caller is responsible for cleanup.
    """
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=True)
    log.info("[success]✔ Chromium browser launched (headless)[/success]")
    return pw, browser
