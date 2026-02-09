"""Main CLI entry point for csv-me."""

from __future__ import annotations

import sys

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from csv_me.menu import clear_screen, show_menu, show_status
from csv_me.session import Session

console = Console()

# Feature registry: (menu label, handler function)
# Each handler takes a Session and returns None.
FEATURES: list[tuple[str, callable]] = []


def _register_features() -> None:
    """Lazily import and register feature modules."""
    if FEATURES:
        return
    from csv_me.features.normalize_cols import run as normalize_cols
    from csv_me.features.normalize_phones import run as normalize_phones
    from csv_me.features.normalize_currency import run as normalize_currency
    from csv_me.features.remove_duplicates import run as remove_duplicates
    from csv_me.features.split_column import run as split_column
    from csv_me.features.join_csvs import run as join_csvs

    FEATURES.extend(
        [
            ("Normalize Columns", normalize_cols),
            ("Normalize Phone Numbers", normalize_phones),
            ("Normalize Currency", normalize_currency),
            ("Remove Duplicates", remove_duplicates),
            ("Split Column", split_column),
            ("Join CSVs", join_csvs),
        ]
    )


def _get_input_path() -> str:
    """Get CSV path from CLI args or prompt."""
    if len(sys.argv) > 1:
        return sys.argv[1]
    return Prompt.ask("[bold green]Enter the path to your CSV file[/bold green]")


def main() -> None:
    _register_features()

    clear_screen()
    console.print(
        Panel(
            "[bold magenta]csv-me[/bold magenta]  —  CSV Cleaning & Transformation Tool",
            expand=False,
        )
    )

    path = _get_input_path()
    try:
        session = Session(path)
    except (FileNotFoundError, ValueError) as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        sys.exit(1)

    console.print(
        f"[green]Loaded:[/green] {session.original_path.name}  "
        f"([dim]{session.output_dir}[/dim])\n"
    )

    while True:
        clear_screen()
        show_status(session.current_filename)

        labels = [label for label, _ in FEATURES]
        choice = show_menu("Main Menu", labels, back_label="Quit")

        if choice == 0:
            console.print()
            console.print(
                Panel(
                    f"[bold green]Done![/bold green]  Output saved to:\n"
                    f"  {session.output_dir}",
                    expand=False,
                )
            )
            break

        _, handler = FEATURES[choice - 1]
        handler(session)
