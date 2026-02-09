"""Split a column into multiple new columns by one or more separators."""

from __future__ import annotations

import re

import pandas as pd
from rich.prompt import Prompt

from csv_me.menu import clear_screen, console, show_status
from csv_me.session import Session


def _pick_single_column(df: pd.DataFrame) -> str | None:
    """Let the user pick exactly one column. Returns column name or None."""
    columns = list(df.columns)
    console.print()
    console.print("[bold]Select the column to split:[/bold]")
    for i, col in enumerate(columns, 1):
        console.print(f"  [bold]{i}.[/bold] {col}")
    console.print(f"  [bold]0.[/bold] Cancel")
    console.print()

    raw = Prompt.ask("[bold green]Enter column number[/bold green]")
    try:
        idx = int(raw.strip())
    except ValueError:
        return None
    if idx == 0:
        return None
    if 1 <= idx <= len(columns):
        return columns[idx - 1]
    console.print("[yellow]Invalid selection.[/yellow]")
    return None


def _ask_separators() -> list[str] | None:
    """Prompt for separators in single quotes. Returns list of separator strings."""
    console.print()
    raw = Prompt.ask(
        "[bold green]Enter separator(s) in single quotes, comma-separated "
        "(e.g. ' ', ',', '-')[/bold green]"
    )
    # Extract everything between single quotes
    seps = re.findall(r"'([^']*)'", raw)
    if not seps:
        console.print("[yellow]No valid separators found.[/yellow]")
        return None
    return seps


def _ask_new_column_names() -> list[str] | None:
    """Prompt for the names of the new columns."""
    console.print()
    raw = Prompt.ask(
        "[bold green]Enter names for the new columns (comma-separated)[/bold green]"
    )
    names = [n.strip() for n in raw.split(",") if n.strip()]
    if not names:
        console.print("[yellow]No column names provided.[/yellow]")
        return None
    return names


def run(session: Session) -> None:
    while True:
        clear_screen()
        show_status(session.current_filename)

        df = session.read_current()

        col = _pick_single_column(df)
        if col is None:
            return

        seps = _ask_separators()
        if seps is None:
            continue

        new_names = _ask_new_column_names()
        if new_names is None:
            continue

        num_new = len(new_names)

        # Build a regex pattern that splits on any of the separators
        pattern = "|".join(re.escape(s) for s in seps)

        split_count = 0
        skipped_count = 0
        col_idx = df.columns.get_loc(col)

        # Prepare empty new columns, insert right after the source column
        for i, name in enumerate(new_names):
            df.insert(col_idx + 1 + i, name, "")

        for row_idx in range(len(df)):
            value = str(df.iloc[row_idx][col])
            parts = re.split(pattern, value)
            # Strip whitespace from parts
            parts = [p.strip() for p in parts]

            if len(parts) > num_new:
                # More parts than columns — skip this row
                skipped_count += 1
                continue

            # Fill in the new columns with the parts
            for i, name in enumerate(new_names):
                if i < len(parts):
                    df.at[df.index[row_idx], name] = parts[i]

            # Clear the original column for successfully split rows
            df.at[df.index[row_idx], col] = ""
            split_count += 1

        step_label = f"split_{col.lower().replace(' ', '_')}"
        out = session.save_step(df, step_label)

        details = (
            f"Column: '{col}' | Separators: {seps} | "
            f"New columns: {new_names} | "
            f"Rows split: {split_count} | Rows skipped (too many parts): {skipped_count} | "
            f"Saved: {out.name}"
        )
        session.logger.log("Split Column", details)

        console.print(
            f"\n[green]Done![/green] Split column [bold]'{col}'[/bold] into "
            f"{new_names}."
        )
        console.print(
            f"  Rows split: [bold]{split_count}[/bold]  |  "
            f"Rows skipped (too many parts): [bold yellow]{skipped_count}[/bold yellow]"
        )
        console.print(f"  Saved as [bold]{out.name}[/bold]\n")
        console.input("[dim]Press Enter to continue...[/dim]")
