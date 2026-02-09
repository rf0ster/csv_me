"""Shared menu helpers used by the main CLI and feature modules."""

from __future__ import annotations

import os
from typing import Sequence

import pandas as pd
from rich.console import Console
from rich.panel import Panel
from rich.prompt import IntPrompt, Prompt
from rich.table import Table

console = Console()


def clear_screen() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def show_status(current_file: str) -> None:
    """Display a small status bar showing the current working file."""
    console.print(
        Panel(
            f"[bold cyan]Working file:[/bold cyan] {current_file}",
            style="dim",
            expand=False,
        )
    )
    console.print()


def show_menu(title: str, options: Sequence[str], *, back_label: str = "Back") -> int:
    """Display a numbered menu and return the 1-based choice (0 = back/quit).

    Returns:
        Selected option index (1-based), or 0 for back/quit.
    """
    console.print(Panel(f"[bold yellow]{title}[/bold yellow]", expand=False))
    for i, opt in enumerate(options, 1):
        console.print(f"  [bold]{i}.[/bold] {opt}")
    console.print(f"  [bold]0.[/bold] {back_label}")
    console.print()

    choice = IntPrompt.ask(
        "[bold green]Select an option[/bold green]",
        choices=[str(i) for i in range(len(options) + 1)],
        show_choices=False,
    )
    return choice


def pick_columns(df: pd.DataFrame, prompt_text: str = "Apply to") -> list[str]:
    """Let the user choose columns. Returns list of selected column names."""
    columns = list(df.columns)
    console.print()
    console.print(f"[bold]{prompt_text}:[/bold]")
    console.print(f"  [bold]0.[/bold] All columns")
    for i, col in enumerate(columns, 1):
        console.print(f"  [bold]{i}.[/bold] {col}")
    console.print()

    raw = Prompt.ask(
        "[bold green]Enter column numbers (comma-separated, or 0 for all)[/bold green]"
    )
    parts = [p.strip() for p in raw.split(",")]
    if "0" in parts:
        return columns

    selected: list[str] = []
    for p in parts:
        try:
            idx = int(p)
            if 1 <= idx <= len(columns):
                selected.append(columns[idx - 1])
        except ValueError:
            pass

    if not selected:
        console.print("[yellow]No valid columns selected — defaulting to all.[/yellow]")
        return columns
    return selected


def preview_df(df: pd.DataFrame, title: str = "Preview", max_rows: int = 5) -> None:
    """Show a quick rich table preview of the DataFrame."""
    table = Table(title=title, show_lines=True)
    for col in df.columns:
        table.add_column(str(col), overflow="fold")
    for _, row in df.head(max_rows).iterrows():
        table.add_row(*[str(v) for v in row])
    if len(df) > max_rows:
        table.add_row(*["..." for _ in df.columns])
    console.print(table)
    console.print(f"[dim]{len(df)} rows total[/dim]\n")
