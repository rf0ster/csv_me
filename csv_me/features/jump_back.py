"""Jump back to a previous transformation step, discarding later steps."""

from __future__ import annotations

from rich.prompt import Prompt

from csv_me.menu import clear_screen, console, show_menu, show_status
from csv_me.session import Session


def run(session: Session) -> None:
    while True:
        clear_screen()
        show_status(session.current_filename)

        if session.step < 2:
            console.print("[yellow]Nothing to jump back to — only the original file exists.[/yellow]\n")
            console.input("[dim]Press Enter to continue...[/dim]")
            return

        # Build menu options from history, excluding the current step
        options: list[str] = []
        for i, path in enumerate(session.history[:-1]):
            options.append(path.name)

        choice = show_menu("Jump to Previous Step", options)

        if choice == 0:
            return

        target_index = choice - 1
        target_path = session.history[target_index]
        steps_to_remove = session.step - target_index - 1

        console.print(
            f"\n[bold yellow]This will delete {steps_to_remove} step file(s) "
            f"and revert to:[/bold yellow] {target_path.name}\n"
        )
        confirm = Prompt.ask(
            "[bold red]Are you sure?[/bold red] (y/n)",
            default="n",
        )
        if confirm.strip().lower() != "y":
            continue

        result = session.jump_to_step(target_index)
        session.logger.log(
            "Jump to Previous Step",
            f"Reverted to step {target_index + 1} ({result.name}) | "
            f"Deleted {steps_to_remove} later step(s)",
        )

        console.print(
            f"\n[green]Done![/green] Jumped back to step {target_index + 1}: "
            f"[bold]{result.name}[/bold]\n"
        )
        console.input("[dim]Press Enter to continue...[/dim]")
        return
