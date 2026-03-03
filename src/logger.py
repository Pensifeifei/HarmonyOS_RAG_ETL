"""
Global logger module with cyberpunk-styled CLI output.

Provides a themed Rich console, structured logging, progress bars,
and a startup banner for the HarmonyOS RAG ETL pipeline.
"""

import logging
from typing import Optional

from rich.console import Console
from rich.logging import RichHandler
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.theme import Theme

# ---------------------------------------------------------------------------
# Custom theme: cyberpunk / geek palette
# ---------------------------------------------------------------------------
_THEME = Theme(
    {
        "info": "bold cyan",
        "success": "bold green",
        "warning": "bold yellow",
        "error": "bold red",
        "critical": "bold reverse red",
        "module": "bold magenta",
        "timestamp": "dim white",
        "banner": "bold bright_cyan",
        "accent": "bright_magenta",
    }
)

# Singleton console shared across the entire project
console = Console(theme=_THEME)


# ---------------------------------------------------------------------------
# ASCII banner
# ---------------------------------------------------------------------------
_BANNER = r"""
[banner] ╔══════════════════════════════════════════════════════════════╗
 ║  [accent]██╗  ██╗ █████╗ ██████╗ ███╗   ███╗ ██████╗ ███╗  ██╗██╗   ██╗[/accent] ║
 ║  [accent]██║  ██║██╔══██╗██╔══██╗████╗ ████║██╔═══██╗████╗ ██║╚██╗ ██╔╝[/accent] ║
 ║  [accent]███████║███████║██████╔╝██╔████╔██║██║   ██║██╔██╗██║ ╚████╔╝ [/accent] ║
 ║  [accent]██╔══██║██╔══██║██╔══██╗██║╚██╔╝██║██║   ██║██║╚████║  ╚██╔╝  [/accent] ║
 ║  [accent]██║  ██║██║  ██║██║  ██║██║ ╚═╝ ██║╚██████╔╝██║ ╚███║   ██║   [/accent] ║
 ║  [accent]╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝     ╚═╝ ╚═════╝ ╚═╝  ╚══╝   ╚═╝   [/accent] ║
 ║                                                              ║
 ║        [info]RAG · ETL Pipeline  —  Offline Knowledge Builder[/info]      ║
 ╚══════════════════════════════════════════════════════════════╝[/banner]
"""


def print_banner() -> None:
    """Print the startup ASCII art banner."""
    console.print(_BANNER)


# ---------------------------------------------------------------------------
# Structured logger factory
# ---------------------------------------------------------------------------
def setup_logger(
    name: str = "etl",
    level: int = logging.INFO,
    *,
    show_path: bool = False,
) -> logging.Logger:
    """Return a :class:`logging.Logger` wired to a :class:`RichHandler`.

    Args:
        name: Logger name (appears as the ``[module]`` tag).
        level: Minimum log level.
        show_path: Whether to show the source-file path in each log line.
    """
    logger = logging.getLogger(name)

    # Avoid duplicate handlers when called more than once
    if logger.handlers:
        return logger

    handler = RichHandler(
        console=console,
        rich_tracebacks=True,
        tracebacks_show_locals=True,
        show_path=show_path,
        markup=True,
        log_time_format="[%Y-%m-%d %H:%M:%S]",
    )
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.setLevel(level)
    return logger


# ---------------------------------------------------------------------------
# Progress bar factory
# ---------------------------------------------------------------------------
def create_progress(
    description: Optional[str] = None,
) -> Progress:
    """Create a cyberpunk-styled :class:`rich.progress.Progress` instance.

    Args:
        description: Optional static text prepended to the bar.
    """
    columns = [
        SpinnerColumn("dots", style="accent"),
        TextColumn(
            description or "[info]{task.description}[/info]",
            justify="left",
        ),
        BarColumn(bar_width=30, style="accent", complete_style="success"),
        TaskProgressColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
    ]
    return Progress(*columns, console=console)
