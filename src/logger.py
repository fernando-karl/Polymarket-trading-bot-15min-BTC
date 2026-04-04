"""
Enhanced logging and console output module.

Provides rich console output with colors, progress indicators, and better formatting.
"""

import logging
import sys
import os
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Optional

# Try to import rich for better console output, fallback to basic logging
try:
    from rich.console import Console
    from rich.logging import RichHandler
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    from rich import box
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    Console = None
    RichHandler = None
    Progress = None
    Table = None
    Panel = None
    Text = None
    box = None


def setup_logging(verbose: bool = False, use_rich: bool = True) -> logging.Logger:
    """
    Set up logging with optional rich formatting + rotating file handler.
    
    Args:
        verbose: Enable verbose (DEBUG) logging
        use_rich: Use rich console formatting if available
        
    Returns:
        Configured logger instance
    """
    level = logging.DEBUG if verbose else logging.INFO
    
    # Determine log directory (parent of src/, i.e. project root)
    log_dir = Path(__file__).parent.parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "bot.log"
    
    # Rotating file handler: 50MB per file, keep 5 backups (~250MB total)
    rotating_handler = RotatingFileHandler(
        filename=str(log_path),
        maxBytes=50 * 1024 * 1024,  # 50MB
        backupCount=5,
        encoding="utf-8",
    )
    rotating_handler.setLevel(logging.DEBUG)
    rotating_handler.setFormatter(logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    
    if use_rich and RICH_AVAILABLE:
        console = Console(stderr=True)
        rich_handler = RichHandler(
            console=console,
            show_time=True,
            show_path=False,
            rich_tracebacks=True,
            markup=True,
        )
        rich_handler.setLevel(level)
        
        logging.basicConfig(
            level=level,
            format="%(message)s",
            datefmt="[%X]",
            handlers=[rich_handler, rotating_handler],
        )
    else:
        logging.basicConfig(
            level=level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
            handlers=[rotating_handler],
        )
    
    # Suppress noisy HTTP logs
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("websockets").setLevel(logging.WARNING)
    
    return logging.getLogger(__name__)


def get_console() -> Optional[object]:
    """Get rich Console instance if available, None otherwise."""
    if RICH_AVAILABLE:
        return Console()
    return None


def print_success(message: str):
    """Print a success message with green color."""
    console = get_console()
    if console:
        console.print(f"[bold green]✓[/bold green] {message}")
    else:
        print(f"✓ {message}")


def print_error(message: str):
    """Print an error message with red color."""
    console = get_console()
    if console:
        console.print(f"[bold red]✗[/bold red] {message}")
    else:
        print(f"✗ {message}")


def print_warning(message: str):
    """Print a warning message with yellow color."""
    console = get_console()
    if console:
        console.print(f"[bold yellow]⚠[/bold yellow] {message}")
    else:
        print(f"⚠ {message}")


def print_info(message: str):
    """Print an info message."""
    console = get_console()
    if console:
        console.print(f"[bold blue]ℹ[/bold blue] {message}")
    else:
        print(f"ℹ {message}")


def print_header(message: str):
    """Print a header message."""
    console = get_console()
    if console:
        console.print(Panel(message, border_style="blue", title="BTC Arbitrage Bot"))
    else:
        print("=" * 70)
        print(message)
        print("=" * 70)


def create_stats_table(stats_data: dict) -> Optional[Table]:
    """Create a rich table for displaying statistics."""
    if not RICH_AVAILABLE:
        return None
    
    table = Table(box=box.ROUNDED, show_header=True, header_style="bold magenta")
    table.add_column("Metric", style="cyan", no_wrap=True)
    table.add_column("Value", style="green", justify="right")
    
    for key, value in stats_data.items():
        # Format the key nicely
        formatted_key = key.replace("_", " ").title()
        table.add_row(formatted_key, str(value))
    
    return table


def print_stats_table(stats_data: dict):
    """Print statistics in a formatted table."""
    console = get_console()
    if console:
        table = create_stats_table(stats_data)
        if table:
            console.print(table)
            return
    
    # Fallback to simple formatting
    print("\n" + "=" * 50)
    for key, value in stats_data.items():
        formatted_key = key.replace("_", " ").title()
        print(f"{formatted_key:30s}: {value}")
    print("=" * 50)

