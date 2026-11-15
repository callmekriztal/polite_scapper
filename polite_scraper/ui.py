"""Terminal UI layer built on `rich`.

All user-facing console output flows through this module so the scraper
stays quiet and polished by default, and verbose (--verbose / -v) turns on
the detailed per-request logs and checkpoints.
"""

import json
from typing import Any

from rich.console import Console
from rich.json import JSON
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

console = Console()

_VERBOSE = False


def set_verbose(value: bool) -> None:
    global _VERBOSE
    _VERBOSE = value


def is_verbose() -> bool:
    return _VERBOSE


def debug(message: str) -> None:
    """Low-level log line (fetch/cache details). Hidden unless --verbose."""
    if _VERBOSE:
        console.log(message)


def error(message: str) -> None:
    console.print(f"  [bold red]✗[/] {message}")


def warn(message: str) -> None:
    console.print(f"  [bold yellow]![/] {message}")


def info(message: str) -> None:
    console.print(f"  [bold cyan]›[/] {message}")


def success(message: str) -> None:
    console.print(f"  [bold green]✓[/] {message}")


def stage(title: str) -> None:
    console.print()
    console.rule(f"[bold cyan]{title}")


def make_progress() -> Progress:
    """Shared progress bar style for crawling/extraction phases."""
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    )


def banner(target_url: str, mode: str, pages: int, delay: float, cache_dir: str, run_dir: str) -> None:
    text = (
        f"[bold]Target[/]      {target_url}\n"
        f"[bold]Mode[/]        {mode}\n"
        f"[bold]Run folder[/]  {run_dir}\n"
        f"[bold]Max pages[/]   {pages}\n"
        f"[bold]Min delay[/]   {delay}s between requests\n"
        f"[bold]Cache[/]       {cache_dir}"
    )
    console.print(
        Panel(
            text,
            title="[bold cyan]The Polite Scraper[/]",
            subtitle="[dim]polite by design — rate-limited, cached, identify-yourself[/]",
            border_style="cyan",
        )
    )


def checkpoint(title: str, data: dict[str, Any]) -> None:
    """Raw record / stage checkpoint. Shown as a neat JSON panel, verbose-only."""
    if not _VERBOSE:
        return
    console.print(Panel(JSON.from_data(data), title=title, border_style="dim"))


def summary_table(rows: list[tuple[str, Any]]) -> None:
    table = Table(show_header=False, box=None, pad_edge=False)
    table.add_column(style="bold", justify="right")
    table.add_column()
    for label, value in rows:
        table.add_row(label, str(value))
    console.print(Panel(table, title="[bold cyan]Run Summary[/]", border_style="cyan"))


def files_table(files: list[tuple[str, str]]) -> None:
    table = Table(show_header=False, box=None, pad_edge=False)
    table.add_column(style="bold", justify="right")
    table.add_column()
    for label, path in files:
        table.add_row(label, path)
    console.print(Panel(table, title="[bold cyan]Output Files[/]", border_style="cyan"))


def errors_table(errors: list[dict[str, Any]], limit: int = 5) -> None:
    if not errors:
        return
    table = Table(title=f"Errors ({len(errors)})", border_style="red", show_lines=False)
    table.add_column("#", justify="right", style="dim", width=4)
    table.add_column("URL / Item", overflow="fold")
    table.add_column("Reason", overflow="fold")
    for i, err in enumerate(errors[:limit], 1):
        url = err.get("product_url") or err.get("url") or "?"
        reason = err.get("reason") or "?"
        table.add_row(str(i), str(url), str(reason))
    console.print(table)
    if len(errors) > limit:
        console.print(f"  [dim]... and {len(errors) - limit} more (see errors.json)[/]")
