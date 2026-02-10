"""Find and replace text in column values."""

from __future__ import annotations

from dataclasses import dataclass

from rich.prompt import Prompt
from rich.table import Table

from csv_me.menu import clear_screen, console, pick_columns, preview_df, show_menu, show_status
from csv_me.session import Session


@dataclass
class SearchTerm:
    """A single search term with its own matching options."""

    term: str
    case_sensitive: bool
    full_match: bool


OPTIONS = [
    "Add a search term",
    "View search terms",
    "Set replacement value",
    "Execute find & replace",
]


def _add_search_term() -> SearchTerm | None:
    """Prompt user for a search term with case/match options."""
    console.print()
    raw = Prompt.ask(
        "[bold green]Enter search term (or 'cancel' to go back)[/bold green]"
    )
    if raw.strip().lower() == "cancel":
        return None

    term = raw.strip()
    if not term:
        console.print("[red]Search term cannot be empty.[/red]")
        console.input("[dim]Press Enter to continue...[/dim]")
        return None

    case_sensitive = Prompt.ask(
        "[bold green]Case sensitive?[/bold green]",
        choices=["y", "n"],
        default="y",
    ) == "y"

    full_match = Prompt.ask(
        "[bold green]Full match only? (entire cell must equal the term)[/bold green]",
        choices=["y", "n"],
        default="n",
    ) == "y"

    console.print(
        f"\n[green]Added:[/green] '{term}' "
        f"(case sensitive: {'yes' if case_sensitive else 'no'}, "
        f"full match: {'yes' if full_match else 'no'})"
    )
    return SearchTerm(term=term, case_sensitive=case_sensitive, full_match=full_match)


def _show_search_terms(terms: list[SearchTerm], replacement: str) -> None:
    """Display all queued search terms in a table."""
    console.print()
    if not terms:
        console.print("[yellow]No search terms added yet.[/yellow]")
        return

    table = Table(title="Search Terms", show_lines=True)
    table.add_column("#", justify="right")
    table.add_column("Term")
    table.add_column("Case Sensitive")
    table.add_column("Full Match")

    for i, st in enumerate(terms, 1):
        table.add_row(
            str(i),
            st.term,
            "yes" if st.case_sensitive else "no",
            "yes" if st.full_match else "no",
        )
    console.print(table)

    detail = f"'{replacement}'" if replacement else "(remove)"
    console.print(f"\n[bold]Replace with:[/bold] {detail}")
    console.print()


def run(session: Session) -> None:
    terms: list[SearchTerm] = []
    replacement: str = ""

    while True:
        clear_screen()
        show_status(session.current_filename)

        if terms:
            detail = f"'{replacement}'" if replacement else "(remove)"
            console.print(
                f"[dim]Find & Replace: {len(terms)} term(s) queued  |  "
                f"Replace with: {detail}[/dim]\n"
            )

        choice = show_menu("Find & Replace", OPTIONS)

        if choice == 0:
            if terms:
                confirm = Prompt.ask(
                    "[yellow]You have queued terms. Discard and go back?[/yellow] (y/n)",
                    default="n",
                )
                if confirm.strip().lower() != "y":
                    continue
            return

        if choice == 1:
            # Add a search term
            result = _add_search_term()
            if result is not None:
                terms.append(result)
                console.print(f"({len(terms)} term(s) queued)")
            console.input("[dim]Press Enter to continue...[/dim]")

        elif choice == 2:
            # View search terms
            _show_search_terms(terms, replacement)
            console.input("[dim]Press Enter to continue...[/dim]")

        elif choice == 3:
            # Set replacement value
            console.print()
            replacement = Prompt.ask(
                "[bold green]Replace with (leave blank to remove matches)[/bold green]",
                default="",
            )
            detail = f"'{replacement}'" if replacement else "(remove)"
            console.print(f"[green]Replacement set to:[/green] {detail}")
            console.input("[dim]Press Enter to continue...[/dim]")

        elif choice == 4:
            # Execute find & replace
            if not terms:
                console.print("[yellow]No search terms added yet.[/yellow]")
                console.input("[dim]Press Enter to continue...[/dim]")
                continue

            df = session.read_current()
            columns = pick_columns(df, prompt_text="Apply find & replace to")

            total_changed = 0
            for col in columns:
                if col not in df.columns:
                    continue
                original = df[col].copy()
                for st in terms:
                    col_str = df[col].astype(str)
                    if st.full_match:
                        if st.case_sensitive:
                            mask = col_str == st.term
                        else:
                            mask = col_str.str.lower() == st.term.lower()
                        df[col] = col_str.where(~mask, replacement)
                    else:
                        df[col] = col_str.str.replace(
                            st.term, replacement, case=st.case_sensitive, regex=False,
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
            term_summaries = [
                f"'{st.term}' (case:{st.case_sensitive}, full:{st.full_match})"
                for st in terms
            ]
            step_label = "find_replace"
            out = session.save_step(df, step_label)
            session.logger.log(
                "Find & Replace",
                f"Terms: {term_summaries} -> {detail} | "
                f"Columns: {columns} | Cells changed: {total_changed} | Saved: {out.name}",
            )

            console.print(
                f"\n[green]Done![/green] {total_changed} cell(s) changed across "
                f"{len(columns)} column(s). Saved as [bold]{out.name}[/bold]\n"
            )

            # Reset terms
            terms.clear()
            console.input("[dim]Press Enter to continue...[/dim]")
