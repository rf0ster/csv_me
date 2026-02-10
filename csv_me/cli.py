"""Main CLI entry point for csv-me."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from csv_me.menu import clear_screen, show_menu, show_status
from csv_me.session import Session

console = Console()

# Menu entry: either a direct action (label, handler) or a submenu
# (label, [(sublabel, handler), ...]).
MenuEntry = tuple[str, "callable | list[tuple[str, callable]]"]

MENU: list[MenuEntry] = []


def _register_features() -> None:
    """Lazily import and register feature modules."""
    if MENU:
        return
    from csv_me.features.normalize_cols import run as normalize_cols
    from csv_me.features.normalize_phones import run as normalize_phones
    from csv_me.features.normalize_currency import run as normalize_currency
    from csv_me.features.remove_duplicates import run as remove_duplicates
    from csv_me.features.split_column import run as split_column
    from csv_me.features.join_csvs import run as join_csvs
    from csv_me.features.remove_columns import run as remove_columns
    from csv_me.features.split_join_rows import run as split_join_rows
    from csv_me.features.find_replace import run as find_replace
    from csv_me.features.remove_rows import run as remove_rows
    from csv_me.features.sort import run as sort_rows
    from csv_me.features.jump_back import run as jump_back
    from csv_me.features.manual_edit import run as manual_edit

    MENU.extend(
        [
            ("Normalize", [
                ("Columns", normalize_cols),
                ("Phone", normalize_phones),
                ("Currency", normalize_currency),
            ]),
            ("Remove", [
                ("Rows", remove_rows),
                ("Columns", remove_columns),
                ("Duplicates", remove_duplicates),
            ]),
            ("Wrangle", [
                ("Join CSVs", join_csvs),
                ("Search and Replace", find_replace),
                ("Sort", sort_rows),
                ("Split Columns", split_column),
                ("Split-Join", split_join_rows),
            ]),
            ("Revert", jump_back),
            ("Edit", manual_edit),
        ]
    )


def _get_input_path() -> str:
    """Get CSV path or output folder from CLI args or prompt."""
    if len(sys.argv) > 1:
        return sys.argv[1]
    return Prompt.ask(
        "[bold green]Enter the path to a CSV file or a previous output folder[/bold green]"
    )


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
        if Session.is_csv_me_output_dir(path):
            session = Session.from_output_dir(path)
            console.print(
                f"[green]Resumed session:[/green] [bold]{session.name}[/bold]  "
                f"— step {session.step}  "
                f"— {session.current_filename}\n"
                f"  ([dim]{session.output_dir}[/dim])\n"
            )
        elif Path(path).resolve().is_dir():
            console.print(
                f"[bold red]Error:[/bold red] '{path}' is a directory but not "
                f"a csv-me output folder (no {Session.MANIFEST_NAME} found).\n"
                f"Pass a CSV file to start a new session, or a previous "
                f"csv-me output folder to resume."
            )
            sys.exit(1)
        else:
            session_name = Prompt.ask(
                "[bold green]Enter a name for this session[/bold green]",
                default=Path(path).stem,
            )
            session = Session(path, name=session_name)
            console.print(
                f"[green]Loaded:[/green] {session.original_path.name}  "
                f"— session [bold]{session.name}[/bold]\n"
                f"  ([dim]{session.output_dir}[/dim])\n"
            )
    except json.JSONDecodeError:
        console.print(
            f"[bold red]Error:[/bold red] Session manifest in '{path}' is "
            f"corrupted (invalid JSON)."
        )
        sys.exit(1)
    except (FileNotFoundError, ValueError) as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        sys.exit(1)

    while True:
        clear_screen()
        show_status(session.current_filename)

        labels = [label for label, _ in MENU]
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

        label, entry = MENU[choice - 1]

        if isinstance(entry, list):
            # Submenu
            while True:
                clear_screen()
                show_status(session.current_filename)

                sub_labels = [sl for sl, _ in entry]
                sub_choice = show_menu(label, sub_labels)

                if sub_choice == 0:
                    break

                _, handler = entry[sub_choice - 1]
                handler(session)
        else:
            # Direct action
            entry(session)
