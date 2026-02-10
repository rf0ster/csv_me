"""Remove Rows: remove rows matching user-defined conditions."""

from __future__ import annotations

from rich.prompt import Confirm, Prompt

from csv_me.conditions import build_conditions, evaluate_conditions, format_condition
from csv_me.menu import clear_screen, console, preview_df, show_menu, show_status
from csv_me.session import Session


def run(session: Session) -> None:
    while True:
        clear_screen()
        show_status(session.current_filename)

        choice = show_menu("Remove Rows", ["Define conditions to remove rows"])
        if choice == 0:
            return

        df = session.read_current()
        columns = list(df.columns)
        filename = session.current_filename

        # Show current data
        clear_screen()
        show_status(filename)
        preview_df(df, title="Current Data")

        # Build conditions
        console.print(
            "[bold]Define conditions — rows where ALL conditions match "
            "will be [red]removed[/red].[/bold]\n"
        )

        def header_fn() -> None:
            clear_screen()
            show_status(filename)

        conditions = build_conditions(columns, header_fn=header_fn)

        if not conditions:
            console.print("[yellow]No conditions defined — nothing to remove.[/yellow]")
            console.input("[dim]Press Enter to continue...[/dim]")
            continue

        # Evaluate: keep rows where conditions do NOT all match
        mask = df.apply(
            lambda row: not evaluate_conditions(row, conditions), axis=1
        )
        result_df = df[mask].reset_index(drop=True)
        removed_count = len(df) - len(result_df)

        # Preview result
        clear_screen()
        show_status(filename)
        preview_df(result_df, title="Result After Removal")
        console.print(
            f"[bold]{removed_count}[/bold] row(s) will be removed, "
            f"[bold]{len(result_df)}[/bold] row(s) remaining.\n"
        )
        console.print("[bold]Conditions:[/bold]")
        for cond in conditions:
            console.print(f"  [cyan]IF[/cyan] {format_condition(cond)}")
        console.print()

        if not Confirm.ask("[bold green]Proceed with removal?[/bold green]"):
            continue

        # Ask for a name for the removed-rows file
        removed_name = Prompt.ask(
            "[bold green]Name for the removed-rows file[/bold green]",
            default="removed_rows",
        )
        safe_name = removed_name.strip().replace(" ", "_").lower()

        # Save the removed rows to a separate CSV in the output dir
        removed_df = df[~mask].reset_index(drop=True)
        removed_path = session.output_dir / f"{safe_name}.csv"
        removed_df.to_csv(removed_path, index=False)

        out = session.save_step(result_df, "remove_rows")
        condition_summary = [format_condition(c) for c in conditions]
        session.logger.log(
            "Remove Rows",
            f"Conditions: {condition_summary} | "
            f"Removed: {removed_count} | Remaining: {len(result_df)} | "
            f"Removed rows saved: {removed_path.name} | "
            f"Saved: {out.name}",
        )

        console.print(
            f"\n[green]Done![/green] Removed {removed_count} row(s). "
            f"{len(result_df)} row(s) remaining.\n"
            f"  Saved as [bold]{out.name}[/bold]\n"
            f"  Removed rows saved to [bold]{removed_path.name}[/bold]\n"
        )
        console.input("[dim]Press Enter to continue...[/dim]")
        return
