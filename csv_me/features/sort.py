"""Sort rows by a selected column."""

from __future__ import annotations

from rich.prompt import Prompt

from csv_me.menu import clear_screen, console, pick_columns, preview_df, show_menu, show_status
from csv_me.session import Session


def run(session: Session) -> None:
    while True:
        clear_screen()
        show_status(session.current_filename)

        df = session.read_current()
        columns = list(df.columns)
        console.print(f"[dim]Columns: {', '.join(columns)}[/dim]\n")

        selected = pick_columns(df, prompt_text="Select column to sort by")
        if len(selected) > 1:
            console.print("[yellow]Please select only one column.[/yellow]")
            console.input("[dim]Press Enter to continue...[/dim]")
            continue

        col = selected[0]

        clear_screen()
        show_status(session.current_filename)

        choice = show_menu(f"Sort by '{col}'", ["Ascending", "Descending"])
        if choice == 0:
            continue

        ascending = choice == 1
        direction = "ascending" if ascending else "descending"

        result = df.sort_values(by=col, ascending=ascending, ignore_index=True)

        preview_df(result, title=f"Sorted by '{col}' ({direction})")

        confirm = Prompt.ask(
            f"[bold green]Sort by '{col}' ({direction}) and save?[/bold green] (y/n)",
            default="y",
        )
        if confirm.strip().lower() != "y":
            continue

        out = session.save_step(result, f"sort_{direction}")
        session.logger.log(
            "Sort",
            f"Sorted by '{col}' ({direction}) | Saved: {out.name}",
        )

        console.print(
            f"\n[green]Done![/green] Sorted by '{col}' ({direction}). "
            f"Saved as [bold]{out.name}[/bold]\n"
        )
        console.input("[dim]Press Enter to continue...[/dim]")
        return
