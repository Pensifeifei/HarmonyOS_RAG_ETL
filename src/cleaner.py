"""
Cleaner — BeautifulSoup DOM noise removal for HarmonyOS doc pages.

Extracts the main content container, strips navigation / chrome elements,
and normalises code blocks for downstream Markdown conversion.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional

from bs4 import BeautifulSoup, Tag

from src.logger import setup_logger

log = setup_logger("cleaner")

# ---------------------------------------------------------------------------
# Selectors
# ---------------------------------------------------------------------------

# 正文容器（按优先级排列，逐个尝试）
_CONTENT_SELECTORS: list[str] = [
    "div.idpContent.markdown-body",
    "div.idpContent",
    "div.markdown-body",
    "article",
]

# 页面标题
_TITLE_SELECTOR = "h1.doc-title"

# 需要剔除的噪声元素选择器列表
_NOISE_SELECTORS: List[str] = [
    "aui-header",
    "div#documentMenu",
    "nz-breadcrumb",
    "div.anchor-list-box",
    "app-doc-footer",
    "div.headerTipOut",
    "div.dhf-right",
    "div.share-container",
    "script",
    "style",
    "noscript",
    "iframe",
    # 文档内的反馈 / 点赞小部件
    "div.helpful-box",
    "div.doc-feedback",
    # 代码块工具栏（收起 / 自动换行 / 深色代码主题 / 复制）
    ".highlight-div-header",
    # 悬浮提示文本
    ".handle-hover-tips",
    # 标题锚点图标
    "i.anchor-icon",
    # 底部上一篇/下一篇导航
    ".preAndNextLink",
    # 展开章节按钮
    ".expand-button",
    # AI 代码解读按钮
    ".ai-button",
]


@dataclass
class CleanResult:
    """Container for cleaned DOM output."""

    title: str
    content: Tag


def _extract_title(soup: BeautifulSoup) -> str:
    """Extract the document title from ``h1.doc-title``."""
    tag = soup.select_one(_TITLE_SELECTOR)
    if tag:
        return tag.get_text(strip=True)
    # Fallback: first <h1>
    h1 = soup.find("h1")
    if h1:
        return h1.get_text(strip=True)
    return "Untitled"


def _remove_noise(soup: BeautifulSoup) -> None:
    """Remove all noise elements in-place."""
    for selector in _NOISE_SELECTORS:
        for el in soup.select(selector):
            el.decompose()


def _detect_language(pre_tag: Tag) -> str:
    """Guess the code language from CSS class names on a ``<pre>`` tag.

    HarmonyOS docs typically apply classes like ``language-typescript``,
    ``language-json``, etc., or shorthand such as ``.ts``, ``.json``.
    """
    classes = pre_tag.get("class", [])
    for cls in classes:
        # explicit language- prefix
        match = re.match(r"language-(\w+)", cls)
        if match:
            return match.group(1)
        # shorthand: .ts / .json / .xml …
        if cls in {"ts", "typescript", "json", "xml", "java", "c", "cpp", "ets"}:
            return cls
    return ""


def _normalise_code_blocks(content: Tag) -> None:
    """Convert line-numbered ``<ol class='linenums'>`` code blocks to plain ``<pre><code>``."""
    for pre in content.find_all("pre"):
        ol = pre.find("ol", class_="linenums")
        if not ol:
            continue

        lang = _detect_language(pre)

        # 拼接所有 <li> 的纯文本为代码内容
        lines = []
        for li in ol.find_all("li"):
            lines.append(li.get_text())
        code_text = "\n".join(lines)

        # 使用 BeautifulSoup 创建新的 <pre><code> 结构
        lang_attr = f' class="language-{lang}"' if lang else ""
        from bs4 import BeautifulSoup as _BS
        new_pre = _BS(
            f"<pre><code{lang_attr}>{code_text}</code></pre>", "html.parser"
        ).find("pre")
        pre.replace_with(new_pre)


def clean(html: str) -> Optional[CleanResult]:
    """Clean raw HTML and return the doc title + sanitised content tag.

    Args:
        html: Full rendered HTML string from Playwright.

    Returns:
        A :class:`CleanResult` with *title* and the cleaned *content*
        :class:`Tag`, or ``None`` if the content container was not found.
    """
    soup = BeautifulSoup(html, "lxml")

    title = _extract_title(soup)
    log.info("[info]Document title:[/info] %s", title)

    # 尝试多个候选选择器定位正文容器
    content = None
    matched_selector = None
    for sel in _CONTENT_SELECTORS:
        content = soup.select_one(sel)
        if content is not None:
            matched_selector = sel
            break

    if content is None:
        log.error(
            "[error]Content container not found! Tried: %s[/error]",
            ", ".join(_CONTENT_SELECTORS),
        )
        return None

    log.info("[info]Matched content selector:[/info] %s", matched_selector)

    # 在 content 内部执行降噪
    _remove_noise(content)

    # 代码块标准化
    _normalise_code_blocks(content)

    log.info("[success]✔ DOM cleaned[/success]")
    return CleanResult(title=title, content=content)
