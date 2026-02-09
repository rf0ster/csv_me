"""Join multiple CSV files into one with a union of all columns."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from rich.prompt import Prompt
from rich.table import Table

from csv_me.menu import clear_screen, console, preview_df, show_menu, show_status
from csv_me.session import Session

OPTIONS = [
    "Add a CSV file by path",
    "Browse & select CSVs from directory",
    "View queued files & column summary",
    "Exclude columns from the result",
    "Execute join & save",
]


def _load_external_csv() -> tuple[pd.DataFrame, str] | None:
    """Prompt for a file path and load it as a DataFrame.

    Returns (DataFrame, filename) or None on failure/cancel.
    """
    console.print()
    raw = Prompt.ask(
        "[bold green]Enter the path to the CSV file (or 'cancel' to go back)[/bold green]"
    )
    if raw.strip().lower() == "cancel":
        return None

    path = Path(raw.strip()).resolve()
    if not path.exists():
        console.print(f"[bold red]File not found:[/bold red] {path}")
        console.input("[dim]Press Enter to continue...[/dim]")
        return None
    if path.suffix.lower() != ".csv":
        console.print(f"[bold red]Not a CSV file:[/bold red] {path.name}")
        console.input("[dim]Press Enter to continue...[/dim]")
        return None

    try:
        df = pd.read_csv(path)
    except Exception as e:
        console.print(f"[bold red]Error reading file:[/bold red] {e}")
        console.input("[dim]Press Enter to continue...[/dim]")
        return None

    if df.empty:
        console.print("[bold red]File is empty (no rows).[/bold red]")
        console.input("[dim]Press Enter to continue...[/dim]")
        return None

    console.print(
        f"[green]Loaded:[/green] {path.name}  "
        f"({len(df)} rows, {len(df.columns)} columns)"
    )
    return df, path.name


def _browse_and_select_csvs(session: Session) -> list[tuple[pd.DataFrame, str]]:
    """List CSV files in the original file's directory and let user pick multiple.

    Returns list of (DataFrame, filename) tuples for selected files.
    """
    source_dir = session.original_path.parent
    csv_files = sorted(
        [f for f in source_dir.iterdir() if f.suffix.lower() == ".csv" and f != session.original_path],
        key=lambda f: f.name.lower(),
    )

    if not csv_files:
        console.print(f"[yellow]No other CSV files found in {source_dir}[/yellow]")
        console.input("[dim]Press Enter to continue...[/dim]")
        return []

    console.print()
    console.print(f"[bold]CSV files in:[/bold] {source_dir}\n")
    for i, f in enumerate(csv_files, 1):
        console.print(f"  [bold]{i}.[/bold] {f.name}")
    console.print(f"  [bold]0.[/bold] Cancel")
    console.print()

    raw = Prompt.ask(
        "[bold green]Select files to add (comma-separated numbers, or 0 to cancel)[/bold green]"
    )

    if raw.strip() == "0":
        return []

    selected: list[tuple[pd.DataFrame, str]] = []
    for p in raw.split(","):
        try:
            idx = int(p.strip())
            if 1 <= idx <= len(csv_files):
                path = csv_files[idx - 1]
                try:
                    df = pd.read_csv(path)
                except Exception as e:
                    console.print(f"[bold red]Error reading {path.name}:[/bold red] {e}")
                    continue
                if df.empty:
                    console.print(f"[yellow]Skipping {path.name} (empty file).[/yellow]")
                    continue
                selected.append((df, path.name))
                console.print(
                    f"  [green]+[/green] {path.name}  "
                    f"({len(df)} rows, {len(df.columns)} columns)"
                )
        except ValueError:
            pass

    return selected


def _get_union_columns(
    current_df: pd.DataFrame, queued: list[tuple[pd.DataFrame, str]]
) -> list[str]:
    """Return ordered union of all column names.

    Current file's columns come first, then new columns from queued files
    in the order they appear.
    """
    seen: set[str] = set()
    result: list[str] = []
    for col in current_df.columns:
        if col not in seen:
            seen.add(col)
            result.append(col)
    for df, _ in queued:
        for col in df.columns:
            if col not in seen:
                seen.add(col)
                result.append(col)
    return result


def _show_queue_summary(
    current_name: str,
    current_df: pd.DataFrame,
    queued: list[tuple[pd.DataFrame, str]],
) -> None:
    """Display a Rich table summarising the queued files and column union."""
    console.print()
    table = Table(title="Queued Files", show_lines=True)
    table.add_column("#", justify="right")
    table.add_column("File")
    table.add_column("Rows", justify="right")
    table.add_column("Columns", justify="right")

    table.add_row("*", current_name, str(len(current_df)), str(len(current_df.columns)))
    for i, (df, name) in enumerate(queued, 1):
        table.add_row(str(i), name, str(len(df)), str(len(df.columns)))
    console.print(table)

    all_cols = _get_union_columns(current_df, queued)
    current_cols = set(current_df.columns)
    queued_cols: set[str] = set()
    for df, _ in queued:
        queued_cols.update(df.columns)

    console.print(f"\n[bold]Union of all columns ({len(all_cols)}):[/bold]")
    for col in all_cols:
        in_current = col in current_cols
        in_queued = col in queued_cols
        if in_current and in_queued:
            tag = "[green](all files)[/green]"
        elif in_current:
            tag = "[cyan](current only)[/cyan]"
        else:
            tag = "[yellow](queued only)[/yellow]"
        console.print(f"  - {col}  {tag}")
    console.print()


def _pick_columns_to_exclude(all_columns: list[str]) -> list[str]:
    """Show all columns and let the user pick which to exclude.

    Returns the list of columns to KEEP.
    """
    console.print()
    console.print("[bold]All columns in the union:[/bold]")
    console.print(
        "Enter column numbers to [bold red]exclude[/bold red] from the result:"
    )
    for i, col in enumerate(all_columns, 1):
        console.print(f"  [bold]{i}.[/bold] {col}")
    console.print()

    raw = Prompt.ask(
        "[bold green]Columns to exclude (comma-separated, or press Enter to keep all)[/bold green]",
        default="",
    )

    if not raw.strip():
        return all_columns

    exclude_indices: set[int] = set()
    for p in raw.split(","):
        try:
            idx = int(p.strip())
            if 1 <= idx <= len(all_columns):
                exclude_indices.add(idx - 1)
        except ValueError:
            pass

    selected = [col for i, col in enumerate(all_columns) if i not in exclude_indices]
    if not selected:
        console.print("[yellow]Cannot exclude all columns — keeping all.[/yellow]")
        return all_columns
    return selected


def run(session: Session) -> None:
    queued: list[tuple[pd.DataFrame, str]] = []
    excluded_cols: list[str] = []

    while True:
        clear_screen()
        show_status(session.current_filename)

        if queued:
            console.print(
                f"[dim]Join queue: {len(queued)} file(s) queued  |  "
                f"{len(excluded_cols)} column(s) excluded[/dim]\n"
            )

        choice = show_menu("Join CSVs", OPTIONS)

        if choice == 0:
            # Back — confirm if queue is non-empty
            if queued:
                confirm = Prompt.ask(
                    "[yellow]You have queued files. Discard and go back?[/yellow] (y/n)",
                    default="n",
                )
                if confirm.strip().lower() != "y":
                    continue
            return

        if choice == 1:
            # Add a CSV by path
            result = _load_external_csv()
            if result is not None:
                queued.append(result)
                console.print(
                    f"[green]Added to queue.[/green] "
                    f"({len(queued)} file(s) queued)"
                )
                console.input("[dim]Press Enter to continue...[/dim]")

        elif choice == 2:
            # Browse & select CSVs from directory
            selected = _browse_and_select_csvs(session)
            if selected:
                queued.extend(selected)
                console.print(
                    f"\n[green]Added {len(selected)} file(s) to queue.[/green] "
                    f"({len(queued)} total queued)"
                )
                console.input("[dim]Press Enter to continue...[/dim]")

        elif choice == 3:
            # View queue summary
            if not queued:
                console.print("[yellow]No files queued yet.[/yellow]")
                console.input("[dim]Press Enter to continue...[/dim]")
                continue
            current_df = session.read_current()
            _show_queue_summary(session.current_filename, current_df, queued)
            console.input("[dim]Press Enter to continue...[/dim]")

        elif choice == 4:
            # Exclude columns
            if not queued:
                console.print("[yellow]No files queued yet.[/yellow]")
                console.input("[dim]Press Enter to continue...[/dim]")
                continue
            current_df = session.read_current()
            all_cols = _get_union_columns(current_df, queued)
            keep_cols = _pick_columns_to_exclude(all_cols)
            excluded_cols = [c for c in all_cols if c not in keep_cols]
            if excluded_cols:
                console.print(
                    f"[green]Excluding {len(excluded_cols)} column(s):[/green] "
                    f"{', '.join(excluded_cols)}"
                )
            else:
                console.print("[green]Keeping all columns.[/green]")
            console.input("[dim]Press Enter to continue...[/dim]")

        elif choice == 5:
            # Execute join
            if not queued:
                console.print("[yellow]No files queued yet.[/yellow]")
                console.input("[dim]Press Enter to continue...[/dim]")
                continue

            current_df = session.read_current()
            queued_dfs = [df for df, _ in queued]
            combined = pd.concat(
                [current_df] + queued_dfs, ignore_index=True, sort=False
            )

            if excluded_cols:
                cols_to_drop = [c for c in excluded_cols if c in combined.columns]
                combined = combined.drop(columns=cols_to_drop)

            combined = combined.fillna("")

            if combined.empty or len(combined.columns) == 0:
                console.print(
                    "[bold red]Result has no columns — nothing to save.[/bold red]"
                )
                console.input("[dim]Press Enter to continue...[/dim]")
                continue

            preview_df(combined, title="Join Preview")

            confirm = Prompt.ask(
                "[bold green]Save this result?[/bold green] (y/n)", default="y"
            )
            if confirm.strip().lower() != "y":
                continue

            file_names = [name for _, name in queued]
            out = session.save_step(combined, "join_csvs")
            session.logger.log(
                "Join CSVs",
                f"Joined with: {file_names} | "
                f"Excluded columns: {excluded_cols or 'none'} | "
                f"Total rows: {len(combined)} | "
                f"Total columns: {len(combined.columns)} | "
                f"Saved: {out.name}",
            )

            console.print(
                f"\n[green]Done![/green] Joined {len(queued) + 1} file(s). "
                f"{len(combined)} rows, {len(combined.columns)} columns. "
                f"Saved as [bold]{out.name}[/bold]\n"
            )

            # Reset queue
            queued.clear()
            excluded_cols.clear()
            console.input("[dim]Press Enter to continue...[/dim]")
