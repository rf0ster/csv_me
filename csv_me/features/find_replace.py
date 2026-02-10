"""Find and replace text in column values."""

from __future__ import annotations

import re

from rich.prompt import Prompt

from csv_me.menu import clear_screen, console, pick_columns, preview_df, show_status
from csv_me.session import Session


def _parse_search_terms(raw: str) -> list[str]:
    """Extract terms wrapped in single quotes from the input string."""
    return re.findall(r"'([^']*)'", raw)


def run(session: Session) -> None:
    while True:
        clear_screen()
        show_status(session.current_filename)

        console.print("[bold yellow]Find & Replace[/bold yellow]\n")
        console.print(
            "[dim]Wrap each search term in single quotes.\n"
            "Examples:  'foo'   'hello world'   'foo' 'bar'[/dim]\n"
        )

        raw = Prompt.ask(
            "[bold green]Enter search term(s) (or 'q' to go back)[/bold green]"
        )
        if raw.strip().lower() == "q":
            return

        terms = _parse_search_terms(raw)
        if not terms:
            console.print(
                "[red]No valid terms found.[/red] "
                "Wrap each term in single quotes, e.g. 'foo' 'bar'\n"
            )
            console.input("[dim]Press Enter to continue...[/dim]")
            continue

        console.print(f"[cyan]Search terms:[/cyan] {terms}\n")

        replacement = Prompt.ask(
            "[bold green]Replace with (leave blank to remove)[/bold green]",
            default="",
        )

        case_sensitive = Prompt.ask(
            "[bold green]Case sensitive?[/bold green]",
            choices=["y", "n"],
            default="y",
        ) == "y"

        df = session.read_current()
        columns = pick_columns(df, prompt_text="Apply find & replace to")

        total_changed = 0
        for col in columns:
            if col not in df.columns:
                continue
            original = df[col].copy()
            for term in terms:
                df[col] = df[col].astype(str).str.replace(
                    term, replacement, case=case_sensitive, regex=False,
                )
            total_changed += (original.astype(str) != df[col].astype(str)).sum()

        preview_df(df, title="Preview after find & replace")

        confirm = Prompt.ask(
            "[bold green]Save this step?[/bold green]",
            choices=["y", "n"],
            default="y",
        )
        if confirm != "y":
            console.print("[yellow]Discarded.[/yellow]\n")
            console.input("[dim]Press Enter to continue...[/dim]")
            continue

        detail = f"'{replacement}'" if replacement else "(removed)"
        step_label = "find_replace"
        out = session.save_step(df, step_label)
        session.logger.log(
            "Find & Replace",
            f"Terms: {terms} -> {detail} | Case sensitive: {case_sensitive} | "
            f"Columns: {columns} | Cells changed: {total_changed} | Saved: {out.name}",
        )

        console.print(
            f"\n[green]Done![/green] {total_changed} cell(s) changed across "
            f"{len(columns)} column(s). Saved as [bold]{out.name}[/bold]\n"
        )
        console.input("[dim]Press Enter to continue...[/dim]")
