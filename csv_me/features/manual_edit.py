"""Manual Edit: search for rows by criteria and edit column values interactively."""

from __future__ import annotations

import curses
from typing import Any

import pandas as pd
from rich.prompt import Confirm

from csv_me.conditions import (
    build_conditions,
    evaluate_conditions,
    format_condition,
)
from csv_me.menu import clear_screen, console, preview_df, show_menu, show_status
from csv_me.session import Session


def _row_editor(
    stdscr: Any,
    columns: list[str],
    values: dict[str, str],
    row_info: str,
) -> dict[str, str] | None:
    """Curses-based interactive row editor.

    Arrow keys navigate between fields, type to edit in-place,
    Enter saves the row, Esc skips it.

    Returns edited values dict, or None if user pressed Esc.
    """
    curses.curs_set(1)
    curses.use_default_colors()
    stdscr.keypad(True)

    current_field = 0
    edited = {col: str(v) for col, v in values.items()}
    cursor_pos = {col: len(edited[col]) for col in columns}
    scroll_offset = 0
    max_col_len = max(len(col) for col in columns) if columns else 0

    while True:
        height, width = stdscr.getmaxyx()
        stdscr.erase()

        # Header
        try:
            stdscr.addnstr(0, 0, f"  {row_info}", width - 1, curses.A_BOLD)
            stdscr.addnstr(
                2, 0,
                "  [\u2191\u2193] Navigate  [\u2190\u2192] Cursor  [Enter] Save  [Esc] Skip",
                width - 1, curses.A_DIM,
            )
        except curses.error:
            pass

        # Scrolling
        field_start_y = 4
        field_area = max(height - field_start_y - 1, 1)

        if current_field < scroll_offset:
            scroll_offset = current_field
        elif current_field >= scroll_offset + field_area:
            scroll_offset = current_field - field_area + 1

        # Draw fields
        cursor_y, cursor_x = field_start_y, 0
        visible_end = min(len(columns), scroll_offset + field_area)

        for i in range(scroll_offset, visible_end):
            y = field_start_y + (i - scroll_offset)
            col = columns[i]
            val = edited[col]
            padded = col.rjust(max_col_len)

            try:
                if i == current_field:
                    prefix = " \u25b8 "
                    label = f"{padded}:  "
                    val_x = len(prefix) + len(label)
                    max_val = max(width - val_x - 1, 0)
                    display_val = val[:max_val]

                    stdscr.addnstr(y, 0, prefix, width - 1, curses.A_BOLD)
                    stdscr.addnstr(
                        y, len(prefix), label,
                        max(width - 1 - len(prefix), 0), curses.A_BOLD,
                    )
                    if display_val:
                        stdscr.addnstr(y, val_x, display_val, max_val)

                    cursor_y = y
                    cursor_x = val_x + min(cursor_pos[col], max_val)
                else:
                    line = f"   {padded}:  {val}"
                    stdscr.addnstr(y, 0, line, width - 1)
            except curses.error:
                pass

        try:
            stdscr.move(cursor_y, cursor_x)
        except curses.error:
            pass

        stdscr.refresh()

        key = stdscr.getch()
        col = columns[current_field]

        if key == 27:  # Esc
            return None
        elif key in (10, 13, curses.KEY_ENTER):
            return edited
        elif key == curses.KEY_UP:
            if current_field > 0:
                current_field -= 1
        elif key == curses.KEY_DOWN:
            if current_field < len(columns) - 1:
                current_field += 1
        elif key == curses.KEY_LEFT:
            if cursor_pos[col] > 0:
                cursor_pos[col] -= 1
        elif key == curses.KEY_RIGHT:
            if cursor_pos[col] < len(edited[col]):
                cursor_pos[col] += 1
        elif key in (curses.KEY_BACKSPACE, 127, 8):
            pos = cursor_pos[col]
            if pos > 0:
                edited[col] = edited[col][: pos - 1] + edited[col][pos:]
                cursor_pos[col] = pos - 1
        elif key == curses.KEY_DC:  # Delete
            pos = cursor_pos[col]
            if pos < len(edited[col]):
                edited[col] = edited[col][:pos] + edited[col][pos + 1 :]
        elif key == curses.KEY_HOME:
            cursor_pos[col] = 0
        elif key == curses.KEY_END:
            cursor_pos[col] = len(edited[col])
        elif 32 <= key <= 126:  # Printable ASCII
            pos = cursor_pos[col]
            edited[col] = edited[col][:pos] + chr(key) + edited[col][pos:]
            cursor_pos[col] = pos + 1


def _edit_row_curses(
    columns: list[str],
    values: dict[str, str],
    row_info: str,
) -> dict[str, str] | None:
    """Launch the curses row editor. Returns edited values or None (skip)."""
    return curses.wrapper(_row_editor, columns, values, row_info)


def run(session: Session) -> None:
    while True:
        clear_screen()
        show_status(session.current_filename)

        choice = show_menu("Manual Edit", ["Search & edit rows"])
        if choice == 0:
            return

        df = session.read_current()
        columns = list(df.columns)
        filename = session.current_filename

        # Build search conditions
        clear_screen()
        show_status(filename)
        console.print("[bold]Define search criteria to find rows to edit.[/bold]\n")

        def header_fn() -> None:
            clear_screen()
            show_status(filename)
            console.print(
                "[bold]Define search criteria to find rows to edit.[/bold]\n"
            )

        conditions = build_conditions(columns, header_fn=header_fn)

        if not conditions:
            console.print("[yellow]No conditions defined.[/yellow]")
            console.input("[dim]Press Enter to continue...[/dim]")
            continue

        clear_screen()
        show_status(filename)
        console.print("[bold]Search conditions:[/bold]")
        for c in conditions:
            console.print(f"  [cyan]IF[/cyan] {format_condition(c)}")
        console.print()

        if not Confirm.ask("[bold green]Proceed with search?[/bold green]"):
            continue

        # Iterate and edit matching rows
        edited_count = 0
        added_rows: list[dict[str, str]] = []
        total = len(df)

        for idx, row in df.iterrows():
            if not evaluate_conditions(row, conditions):
                continue

            original = {
                col: "" if pd.isna(row[col]) else str(row[col])
                for col in columns
            }

            result = _edit_row_curses(
                columns, original, f"Match \u2014 Row {idx + 1} of {total}"
            )
            clear_screen()

            if result is None:
                show_status(filename)
                console.print(f"[dim]Skipped row {idx + 1}.[/dim]")
                if not Confirm.ask(
                    "[bold green]Continue to next match?[/bold green]"
                ):
                    break
                continue

            # Apply edits
            for col in columns:
                df.at[idx, col] = result[col]
            edited_count += 1

            show_status(filename)
            console.print(f"[green]Row {idx + 1} saved.[/green]\n")

            if Confirm.ask(
                "[bold green]Add a new row based on the original values?[/bold green]"
            ):
                new_result = _edit_row_curses(
                    columns,
                    dict(original),
                    f"New row (based on original Row {idx + 1})",
                )
                clear_screen()
                if new_result is not None:
                    added_rows.append(new_result)
                    show_status(filename)
                    console.print("[green]New row added.[/green]\n")

        # Append new rows
        if added_rows:
            new_df = pd.DataFrame(added_rows, columns=columns)
            df = pd.concat([df, new_df], ignore_index=True)

        if edited_count == 0 and not added_rows:
            clear_screen()
            show_status(filename)
            console.print("[yellow]No rows edited.[/yellow]")
            console.input("[dim]Press Enter to continue...[/dim]")
            continue

        # Preview and save
        clear_screen()
        show_status(filename)
        preview_df(df, title="Manual Edit Result")
        console.print(
            f"[dim]{edited_count} row(s) edited, "
            f"{len(added_rows)} row(s) added.[/dim]\n"
        )

        if not Confirm.ask("[bold green]Save changes?[/bold green]"):
            continue

        out = session.save_step(df, "manual_edit")
        session.logger.log(
            "Manual Edit",
            f"Edited {edited_count} row(s), added {len(added_rows)} row(s). "
            f"Conditions: {[format_condition(c) for c in conditions]} | "
            f"Saved: {out.name}",
        )

        console.print(
            f"\n[green]Done![/green] Saved as [bold]{out.name}[/bold]\n"
        )
        console.input("[dim]Press Enter to continue...[/dim]")
        return
