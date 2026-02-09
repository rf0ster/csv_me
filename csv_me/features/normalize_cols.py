"""Normalize column values: lowercase, uppercase, title case, strip whitespace, replace spaces."""

from __future__ import annotations

from csv_me.menu import clear_screen, console, pick_columns, show_menu, show_status
from csv_me.session import Session

OPTIONS = [
    "Lowercase",
    "Uppercase",
    "Title Case",
    "Strip Whitespace",
    "Replace Spaces with Underscores",
]


def _apply(df, columns: list[str], mode: str) -> tuple[int, str]:
    """Apply normalization and return (cells_changed, label)."""
    changed = 0
    for col in columns:
        if col not in df.columns:
            continue
        original = df[col].copy()
        if mode == "lowercase":
            df[col] = df[col].astype(str).str.lower()
        elif mode == "uppercase":
            df[col] = df[col].astype(str).str.upper()
        elif mode == "title":
            df[col] = df[col].astype(str).str.title()
        elif mode == "strip":
            df[col] = df[col].astype(str).str.strip()
        elif mode == "underscores":
            df[col] = df[col].astype(str).str.replace(" ", "_")
        changed += (original.astype(str) != df[col].astype(str)).sum()
    return changed, mode


MODES = ["lowercase", "uppercase", "title", "strip", "underscores"]


def run(session: Session) -> None:
    while True:
        clear_screen()
        show_status(session.current_filename)

        choice = show_menu("Normalize Columns", OPTIONS)
        if choice == 0:
            return

        mode = MODES[choice - 1]
        label = OPTIONS[choice - 1]

        df = session.read_current()
        columns = pick_columns(df, prompt_text=f"Apply '{label}' to")

        changed, _ = _apply(df, columns, mode)

        step_label = f"normalize_cols_{mode}"
        out = session.save_step(df, step_label)
        session.logger.log(
            f"Normalize Columns — {label}",
            f"Columns: {columns} | Cells changed: {changed} | Saved: {out.name}",
        )

        console.print(
            f"\n[green]Done![/green] {changed} cell(s) changed across "
            f"{len(columns)} column(s). Saved as [bold]{out.name}[/bold]\n"
        )
        console.input("[dim]Press Enter to continue...[/dim]")
