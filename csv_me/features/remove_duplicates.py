"""Remove duplicate rows based on all or selected columns."""

from __future__ import annotations

import pandas as pd
from rich.prompt import Prompt

from csv_me.menu import clear_screen, console, show_menu, show_status
from csv_me.session import Session

OPTIONS = [
    "Remove Exact Duplicate Rows (all columns)",
    "Remove Duplicates by Selected Columns",
]


def _pick_columns_to_exclude(df: pd.DataFrame) -> list[str]:
    """Show all columns (selected by default) and let user deselect some.

    Returns the list of columns to USE for duplicate detection.
    """
    columns = list(df.columns)
    console.print()
    console.print("[bold]All columns are selected by default.[/bold]")
    console.print("Enter column numbers to [bold red]exclude[/bold red] from duplicate checking:")
    for i, col in enumerate(columns, 1):
        console.print(f"  [bold]{i}.[/bold] {col}")
    console.print()

    raw = Prompt.ask(
        "[bold green]Columns to exclude (comma-separated, or press Enter to keep all)[/bold green]",
        default="",
    )

    if not raw.strip():
        return columns

    exclude_indices: set[int] = set()
    for p in raw.split(","):
        try:
            idx = int(p.strip())
            if 1 <= idx <= len(columns):
                exclude_indices.add(idx - 1)
        except ValueError:
            pass

    selected = [col for i, col in enumerate(columns) if i not in exclude_indices]
    if not selected:
        console.print("[yellow]No columns remaining — using all columns.[/yellow]")
        return columns
    return selected


def run(session: Session) -> None:
    while True:
        clear_screen()
        show_status(session.current_filename)

        choice = show_menu("Remove Duplicates", OPTIONS)
        if choice == 0:
            return

        df = session.read_current()
        rows_before = len(df)

        if choice == 1:
            # All columns
            subset = None
            label_detail = "all columns"
        else:
            # Let user pick
            subset_cols = _pick_columns_to_exclude(df)
            subset = subset_cols
            label_detail = f"columns: {subset_cols}"

        df = df.drop_duplicates(subset=subset)
        rows_after = len(df)
        removed = rows_before - rows_after

        step_label = "remove_duplicates"
        out = session.save_step(df, step_label)
        session.logger.log(
            "Remove Duplicates",
            f"Based on {label_detail} | Rows before: {rows_before} | "
            f"Rows after: {rows_after} | Removed: {removed} | Saved: {out.name}",
        )

        console.print(
            f"\n[green]Done![/green] Removed {removed} duplicate row(s). "
            f"{rows_after} rows remaining. Saved as [bold]{out.name}[/bold]\n"
        )
        console.input("[dim]Press Enter to continue...[/dim]")
