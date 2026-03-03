"""
Converter — transform cleaned HTML (BS4 Tag) into Markdown.

Uses ``markdownify`` with custom overrides to preserve tables and code fences.
"""

from __future__ import annotations

import re
from typing import Optional

from markdownify import MarkdownConverter, markdownify

from src.logger import setup_logger

log = setup_logger("converter")


# ---------------------------------------------------------------------------
# Custom converter
# ---------------------------------------------------------------------------

class _HarmonyConverter(MarkdownConverter):
    """Subclass with overrides tailored for HarmonyOS documentation."""

    # --- Code blocks ---------------------------------------------------
    def convert_pre(self, el, text, *args, **kwargs):  # noqa: D401
        """Render ``<pre><code>`` as fenced code blocks with language hint."""
        code = el.find("code")
        if code is None:
            # Bare <pre> without <code> — wrap in fences
            return f"\n```\n{el.get_text()}\n```\n"

        lang = ""
        classes = code.get("class", [])
        for cls in classes:
            m = re.match(r"language-(\w+)", cls)
            if m:
                lang = m.group(1)
                break

        code_text = code.get_text()
        return f"\n```{lang}\n{code_text}\n```\n"

    # --- Images --------------------------------------------------------
    def convert_img(self, el, text, *args, **kwargs):
        alt = el.get("alt", "")
        src = el.get("src", "")
        if src:
            return f"![{alt}]({src})"
        return ""


_HUAWEI_DOC_ORIGIN = "https://developer.huawei.com"

# 代码块工具栏按钮残留的纯文本模式（Cleaner 的 DOM 剥离是第一道防线，
# 这里的正则是第二道保险，处理 Cleaner 未能覆盖的边缘情况）
_CODE_TOOLBAR_NOISE = re.compile(
    r"(?:^(?:收起|展开|自动换行|深色代码主题|浅色代码主题|复制|已复制)\s*$\n?)+",
    re.MULTILINE,
)

# 相对路径图片 → 绝对 URL
_RELATIVE_IMG = re.compile(r"(!\[[^\]]*\])\((/[^)]+)\)")


def _post_process(md: str) -> str:
    """Clean up the raw Markdown output.

    - Remove residual code-toolbar UI text
    - Convert relative image URLs to absolute
    - Collapse runs of 3+ blank lines into 2
    - Strip trailing whitespace per line
    """
    # 清除代码块工具栏残留噪声
    md = _CODE_TOOLBAR_NOISE.sub("", md)

    # 图片相对路径绝对化
    md = _RELATIVE_IMG.sub(rf"\1({_HUAWEI_DOC_ORIGIN}\2)", md)

    # 合并多余空行
    md = re.sub(r"\n{3,}", "\n\n", md)
    # 去除行尾空白
    md = "\n".join(line.rstrip() for line in md.splitlines())
    return md.strip() + "\n"


def convert(html_tag, *, strip: Optional[list[str]] = None) -> str:
    """Convert a BS4 Tag (cleaned content) to Markdown.

    Args:
        html_tag: A :class:`bs4.Tag` representing the cleaned doc content.
        strip: Optional list of HTML tag names to completely strip.

    Returns:
        The resulting Markdown string.
    """
    raw_html = str(html_tag)

    md = _HarmonyConverter(
        heading_style="ATX",
        bullets="-",
        strip=strip,
    ).convert(raw_html)

    result = _post_process(md)
    log.info("[success]✔ Converted to Markdown (%d chars)[/success]", len(result))
    return result
