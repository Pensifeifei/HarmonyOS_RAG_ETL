"""
Discovery — auto-discover all article URLs from the HarmonyOS sidebar tree.

Uses Playwright to render the Angular SPA, recursively expand the lazy-loaded
NG-ZORRO tree, then extract every article link with its category hierarchy.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Optional
from urllib.parse import urljoin

from playwright.async_api import async_playwright, Page

from src.logger import setup_logger, create_progress, console

log = setup_logger("discovery")

_BASE_URL = "https://developer.huawei.com"
_DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "config.json"

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class ArticleInfo:
    """A single discovered article."""
    title: str
    url: str


@dataclass
class CategoryNode:
    """A category (directory) in the sidebar tree."""
    name: str
    articles: List[ArticleInfo] = field(default_factory=list)
    children: List["CategoryNode"] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Sidebar expansion
# ---------------------------------------------------------------------------

async def _expand_all_nodes(page: Page, *, max_rounds: int = 50) -> int:
    """Recursively click all collapsed tree nodes until fully expanded.

    Returns:
        Total number of expansion clicks performed.
    """
    total_clicks = 0

    for round_num in range(1, max_rounds + 1):
        # 查找所有折叠状态的可展开节点
        # 注意：NG-ZORRO 类名使用下划线 _close 而非连字符 -close
        collapsed = await page.query_selector_all(
            "nz-tree-node.ant-tree-treenode-switcher-close "
            "nz-tree-node-switcher.ant-tree-switcher_close"
        )

        if not collapsed:
            log.info(
                "[success]✔ All nodes expanded after %d rounds (%d clicks)[/success]",
                round_num - 1,
                total_clicks,
            )
            break

        log.info(
            "[info]Round %d: expanding %d collapsed nodes…[/info]",
            round_num,
            len(collapsed),
        )

        for switcher in collapsed:
            try:
                await switcher.click()
                total_clicks += 1
            except Exception:
                # 节点可能已被 Angular 重新渲染，跳过
                pass

        # 等待 Angular 渲染新加载的子节点
        await page.wait_for_timeout(800)
    else:
        log.warning(
            "[warning]Reached max expansion rounds (%d), some nodes may not be expanded[/warning]",
            max_rounds,
        )

    return total_clicks


# ---------------------------------------------------------------------------
# Tree extraction
# ---------------------------------------------------------------------------

async def _extract_tree(page: Page) -> List[CategoryNode]:
    """Extract the full tree structure from the expanded sidebar DOM.

    Uses JavaScript to traverse all nz-tree-node elements, computing each
    node's depth from its indent-unit count, then reconstructing the tree.
    """
    # 在浏览器端提取扁平节点列表
    raw_nodes: list[dict] = await page.evaluate("""
    () => {
        const results = [];
        const nodes = document.querySelectorAll('#documentMenu nz-tree-node');
        nodes.forEach(node => {
            // 计算深度
            const indents = node.querySelectorAll(
                ':scope > .ant-tree-indent > .ant-tree-indent-unit'
            );
            const depth = indents.length;

            // 判断是否为叶子节点
            const switcher = node.querySelector(':scope > nz-tree-node-switcher');
            const isLeaf = switcher
                ? switcher.classList.contains('ant-tree-switcher-noop')
                : true;

            // 提取标题和链接
            const anchor = node.querySelector(
                ':scope > .ant-tree-node-content-wrapper a'
            );
            const title = anchor
                ? anchor.textContent.trim()
                : node.querySelector(':scope > .ant-tree-node-content-wrapper')
                    ?.textContent?.trim() || '';
            const href = anchor ? anchor.getAttribute('href') : null;

            results.push({ depth, isLeaf, title, href });
        });
        return results;
    }
    """)

    log.info("[info]Extracted %d raw tree nodes from DOM[/info]", len(raw_nodes))

    # 将扁平节点列表重建为树结构
    return _build_tree(raw_nodes)


def _build_tree(raw_nodes: list[dict]) -> List[CategoryNode]:
    """Reconstruct a tree from the flat depth-tagged node list."""
    # 使用栈来追踪当前路径上的分类节点
    root_categories: List[CategoryNode] = []

    # stack: list of (depth, CategoryNode)
    stack: list[tuple[int, CategoryNode]] = []

    for node in raw_nodes:
        depth: int = node["depth"]
        title: str = node["title"]
        href: Optional[str] = node["href"]
        is_leaf: bool = node["isLeaf"]

        if not title:
            continue

        # 退栈到当前深度的父级
        while stack and stack[-1][0] >= depth:
            stack.pop()

        if is_leaf and href:
            # 叶子节点 —— 添加到最近的父分类
            full_url = urljoin(_BASE_URL, href)
            article = ArticleInfo(title=title, url=full_url)
            if stack:
                stack[-1][1].articles.append(article)
            # 如果没有父级（depth=0 的叶子），创建独立分类
            else:
                cat = CategoryNode(name=title, articles=[article])
                root_categories.append(cat)
        else:
            # 分类节点
            cat = CategoryNode(name=title)

            # 如果自身也有链接，作为分类的首篇文章
            if href:
                full_url = urljoin(_BASE_URL, href)
                cat.articles.append(ArticleInfo(title=title, url=full_url))

            if stack:
                stack[-1][1].children.append(cat)
            else:
                root_categories.append(cat)

            stack.append((depth, cat))

    return root_categories


# ---------------------------------------------------------------------------
# Flatten tree → config.json format
# ---------------------------------------------------------------------------

def _flatten_categories(
    nodes: List[CategoryNode],
    prefix: str = "",
) -> list[dict]:
    """Flatten nested CategoryNode tree into config.json-style category list.

    Category names use ``/`` separators to preserve hierarchy, e.g.
    ``基础入门/ArkTS/渲染控制``.
    """
    results: list[dict] = []

    for node in nodes:
        full_name = f"{prefix}/{node.name}" if prefix else node.name

        # 收集本级文章
        if node.articles:
            urls = [a.url for a in node.articles]
            results.append({"name": full_name, "urls": urls})

        # 递归子分类
        if node.children:
            results.extend(_flatten_categories(node.children, prefix=full_name))

    return results


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def discover(
    entry_url: str,
    *,
    config_output: Path | str | None = None,
    headless: bool = True,
) -> list[dict]:
    """Discover all article URLs from a HarmonyOS guide entry page.

    Args:
        entry_url: The guide index page URL (e.g. the ``application-dev-guide-V5`` page).
        config_output: Path to write the generated ``config.json``.
                       Defaults to ``<project>/config/config.json``.
        headless: Whether to run the browser in headless mode.

    Returns:
        The generated categories list (same structure as config.json ``categories``).
    """
    output_path = Path(config_output) if config_output else _DEFAULT_CONFIG_PATH

    console.rule("[accent]Discovery · Auto URL Extraction[/accent]")
    log.info("[info]Entry URL:[/info] %s", entry_url)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=headless)
        page = await browser.new_page()

        try:
            log.info("[info]Navigating to entry page…[/info]")
            await page.goto(entry_url, wait_until="domcontentloaded", timeout=30_000)

            # 等待侧边栏加载（SPA 渲染 + 懒加载，headless 需要更长时间）
            await page.wait_for_selector("#documentMenu nz-tree-node", timeout=30_000)
            await page.wait_for_timeout(3000)

            # 递归展开所有折叠节点
            await _expand_all_nodes(page)

            # 提取树结构
            tree = await _extract_tree(page)

        finally:
            await browser.close()

    # 扁平化为 config.json 格式
    categories = _flatten_categories(tree)

    # 统计
    total_urls = sum(len(c["urls"]) for c in categories)
    log.info(
        "[success]✔ Discovered %d categories, %d URLs total[/success]",
        len(categories),
        total_urls,
    )

    # 写入 config.json
    config_data = {"categories": categories}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(config_data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    log.info("[success]✔ Config written to[/success] %s", output_path)

    return categories


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    url = sys.argv[1] if len(sys.argv) > 1 else (
        "https://developer.huawei.com/consumer/cn/doc/"
        "harmonyos-guides-V5/application-dev-guide-V5"
    )
    asyncio.run(discover(url))
