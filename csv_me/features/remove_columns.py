"""Remove selected columns from the CSV."""

from __future__ import annotations

from rich.prompt import Prompt

from csv_me.menu import clear_screen, console, pick_columns, preview_df, show_status
from csv_me.session import Session


def run(session: Session) -> None:
    while True:
        clear_screen()
        show_status(session.current_filename)

        df = session.read_current()
        console.print(f"[dim]Current columns ({len(df.columns)}): {', '.join(df.columns)}[/dim]\n")

        selected = pick_columns(df, prompt_text="Select columns to remove")
        if set(selected) == set(df.columns):
            confirm = Prompt.ask(
                "[yellow]This would remove ALL columns. Continue?[/yellow] (y/n)",
                default="n",
            )
            if confirm.strip().lower() != "y":
                continue
            console.print("[bold red]Cannot remove all columns — nothing to save.[/bold red]")
            console.input("[dim]Press Enter to continue...[/dim]")
            continue

        remaining = [c for c in df.columns if c not in selected]
        result = df[remaining]

        preview_df(result, title="Preview after removal")

        confirm = Prompt.ask(
            f"[bold green]Remove {len(selected)} column(s) and save?[/bold green] (y/n)",
            default="y",
        )
        if confirm.strip().lower() != "y":
            continue

        out = session.save_step(result, "remove_columns")
        session.logger.log(
            "Remove Columns",
            f"Removed: {selected} | "
            f"Remaining: {len(result.columns)} column(s) | Saved: {out.name}",
        )

        console.print(
            f"\n[green]Done![/green] Removed {len(selected)} column(s): {', '.join(selected)}. "
            f"{len(result.columns)} columns remaining. Saved as [bold]{out.name}[/bold]\n"
        )
        console.input("[dim]Press Enter to continue...[/dim]")
        return
