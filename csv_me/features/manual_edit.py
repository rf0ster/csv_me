"""Manual Edit: search for rows by criteria and edit column values interactively."""

from __future__ import annotations

import curses
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from rich.prompt import Confirm, Prompt

from csv_me.conditions import (
    build_expression,
    evaluate_expression,
    format_expression,
)
from csv_me.menu import clear_screen, console, preview_df, show_menu, show_status
from csv_me.session import Session


def _curses_text_input(stdscr: Any, prompt: str) -> str | None:
    """Inline text input at the bottom of the curses screen.

    Returns the entered string, or None if the user pressed Esc.
    """
    height, width = stdscr.getmaxyx()
    y = height - 1
    text = ""
    cursor = 0
    prompt_len = min(len(prompt), width - 1)

    while True:
        max_text = max(width - prompt_len - 1, 1)
        display = text[:max_text]
        try:
            stdscr.move(y, 0)
            stdscr.clrtoeol()
            stdscr.addnstr(y, 0, prompt, width - 1, curses.A_BOLD)
            if display:
                stdscr.addnstr(y, prompt_len, display, max_text)
            stdscr.move(y, prompt_len + min(cursor, max_text))
        except curses.error:
            pass
        stdscr.refresh()

        key = stdscr.getch()
        if key == 27:  # Esc — cancel
            return None
        elif key in (10, 13, curses.KEY_ENTER):
            return text.strip()
        elif key in (curses.KEY_BACKSPACE, 127, 8):
            if cursor > 0:
                text = text[: cursor - 1] + text[cursor:]
                cursor -= 1
        elif key == curses.KEY_LEFT:
            if cursor > 0:
                cursor -= 1
        elif key == curses.KEY_RIGHT:
            if cursor < len(text):
                cursor += 1
        elif 32 <= key <= 126:
            text = text[:cursor] + chr(key) + text[cursor:]
            cursor += 1


def _row_editor(
    stdscr: Any,
    columns: list[str],
    values: dict[str, str],
    row_info: str,
) -> tuple[dict[str, str], list[str], list[str]] | str | None:
    """Curses-based interactive row editor.

    Arrow keys navigate between fields, type to edit in-place,
    Enter saves the row, Esc skips it.  Ctrl+N adds a new column
    below the current field.

    Returns (edited_values, new_columns, ordered_columns) or None if
    user pressed Esc.  ``ordered_columns`` preserves the insertion
    position of any newly added columns.
    """
    curses.curs_set(1)
    curses.use_default_colors()
    stdscr.keypad(True)

    cols = list(columns)
    new_cols: list[str] = []
    current_field = 0
    edited = {col: str(v) for col, v in values.items()}
    cursor_pos = {col: len(edited[col]) for col in cols}
    scroll_offset = 0

    while True:
        height, width = stdscr.getmaxyx()
        stdscr.erase()

        max_col_len = max(len(c) for c in cols) if cols else 0

        # Header
        try:
            stdscr.addnstr(0, 0, f"  {row_info}", width - 1, curses.A_BOLD)
            stdscr.addnstr(
                2, 0,
                "  [\u2191\u2193] Navigate  [\u2190\u2192] Cursor  "
                "[Enter] Save  [Esc] Skip  [Ctrl+N] New column  [Ctrl+D] Remove",
                width - 1, curses.A_DIM,
            )
        except curses.error:
            pass

        # Scrolling
        field_start_y = 4
        field_area = max(height - field_start_y - 2, 1)

        if current_field < scroll_offset:
            scroll_offset = current_field
        elif current_field >= scroll_offset + field_area:
            scroll_offset = current_field - field_area + 1

        # Draw fields
        cursor_y, cursor_x = field_start_y, 0
        visible_end = min(len(cols), scroll_offset + field_area)

        for i in range(scroll_offset, visible_end):
            y = field_start_y + (i - scroll_offset)
            col = cols[i]
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
        col = cols[current_field]

        if key == 27:  # Esc
            return None
        elif key == 4:  # Ctrl+D — remove row
            return "remove"
        elif key in (10, 13, curses.KEY_ENTER):
            return edited, new_cols, cols
        elif key == 14:  # Ctrl+N — add new column
            name = _curses_text_input(stdscr, "New column name: ")
            if name and name not in cols:
                insert_at = current_field + 1
                cols.insert(insert_at, name)
                new_cols.append(name)
                edited[name] = ""
                cursor_pos[name] = 0
                current_field = insert_at
            elif name and name in cols:
                # Column already exists — flash a brief message
                try:
                    h, w = stdscr.getmaxyx()
                    stdscr.addnstr(
                        h - 1, 0,
                        f"Column '{name}' already exists.",
                        w - 1, curses.A_BOLD,
                    )
                    stdscr.refresh()
                    curses.napms(1000)
                except curses.error:
                    pass
        elif key == curses.KEY_UP:
            if current_field > 0:
                current_field -= 1
        elif key == curses.KEY_DOWN:
            if current_field < len(cols) - 1:
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
) -> tuple[dict[str, str], list[str], list[str]] | str | None:
    """Launch the curses row editor.

    Returns (edited_values, new_columns, ordered_columns), ``"remove"`` to
    delete the row, or None (skip).
    """
    return curses.wrapper(_row_editor, columns, values, row_info)


def _write_report(
    output_dir: Path,
    step_filename: str,
    columns: list[str],
    records: list[dict],
) -> Path:
    """Write a manual-edit change report to the output directory.

    Each record is a dict with keys:
        row_num: 1-based row number in the original DataFrame
        original: dict of original cell values
        edited: dict of edited cell values (or None if unchanged)
        new_row: dict of newly added row values (or None)
    """
    stem = Path(step_filename).stem
    report_path = output_dir / f"{stem}_report.txt"
    sep = "=" * 60

    with open(report_path, "w") as f:
        f.write(f"{sep}\n")
        f.write("Manual Edit Report\n")
        f.write(f"Step: {step_filename}\n")
        f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"{sep}\n\n")

        col_header = " | ".join(columns)
        f.write(f"Columns: {col_header}\n\n")

        for rec in records:
            f.write(f"--- Row {rec['row_num']} ---\n")

            orig_vals = " | ".join(rec["original"].get(c, "") for c in columns)
            f.write(f"  Original:  {orig_vals}\n")

            if rec["edited"] is not None:
                edit_vals = " | ".join(rec["edited"].get(c, "") for c in columns)
                f.write(f"  Edited:    {edit_vals}\n")

            if rec["new_row"] is not None:
                new_vals = " | ".join(rec["new_row"].get(c, "") for c in columns)
                f.write(f"  New Row:   {new_vals}\n")

            f.write("\n")

    return report_path


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

        expr = build_expression(columns, header_fn=header_fn)

        if not expr.children:
            console.print("[yellow]No conditions defined.[/yellow]")
            console.input("[dim]Press Enter to continue...[/dim]")
            continue

        clear_screen()
        show_status(filename)
        console.print("[bold]Search conditions:[/bold]")
        console.print(format_expression(expr))
        console.print()

        if not Confirm.ask("[bold green]Proceed with search?[/bold green]"):
            continue

        # Ask whether removed rows should be backed up
        backup_filename: str | None = None
        if Confirm.ask(
            "[bold green]Back up removed rows to a separate file?[/bold green]",
            default=False,
        ):
            name = Prompt.ask("[bold]Backup filename[/bold]", default="removed_rows.csv")
            if not name.endswith(".csv"):
                name += ".csv"
            backup_filename = name

        # Iterate and edit matching rows
        edited_count = 0
        added_rows: list[dict[str, str]] = []
        removed_rows: list[dict[str, str]] = []
        removed_indices: list[int] = []
        change_records: list[dict] = []
        total = len(df)

        for idx in list(df.index):
            row = df.loc[idx]
            if not evaluate_expression(row, expr):
                continue

            original = {
                col: ""
                if pd.isna(row.get(col, ""))
                else str(row.get(col, ""))
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

            if result == "remove":
                show_status(filename)
                removed_rows.append(original.copy())
                removed_indices.append(idx)
                console.print(f"[red]Row {idx + 1} removed.[/red]")
                if not Confirm.ask(
                    "[bold green]Continue to next match?[/bold green]"
                ):
                    break
                continue

            edited_values, new_cols, ordered_cols = result

            # Register any new columns in the DataFrame and update ordering
            for nc in new_cols:
                if nc not in df.columns:
                    df[nc] = ""
            columns = ordered_cols

            # Apply edits
            for col in columns:
                if col in edited_values:
                    df.at[idx, col] = edited_values[col]
            edited_count += 1

            # Track changes for the report
            changed_fields = any(
                edited_values.get(col, "") != original.get(col, "")
                for col in columns
            )
            current_record: dict | None = None
            if changed_fields:
                current_record = {
                    "row_num": idx + 1,
                    "original": original.copy(),
                    "edited": {c: edited_values.get(c, "") for c in columns},
                    "new_row": None,
                }

            show_status(filename)
            console.print(f"[green]Row {idx + 1} saved.[/green]\n")

            if Confirm.ask(
                "[bold green]Add a new row based on the original values?[/bold green]"
            ):
                new_result = _edit_row_curses(
                    columns,
                    {c: original.get(c, "") for c in columns},
                    f"New row (based on original Row {idx + 1})",
                )
                clear_screen()
                if new_result is not None:
                    new_values, extra_cols, new_ordered_cols = new_result
                    for nc in extra_cols:
                        if nc not in df.columns:
                            df[nc] = ""
                    columns = new_ordered_cols
                    added_rows.append(new_values)

                    # Attach new row to existing record or create one
                    if current_record is not None:
                        current_record["new_row"] = new_values.copy()
                    else:
                        current_record = {
                            "row_num": idx + 1,
                            "original": original.copy(),
                            "edited": None,
                            "new_row": new_values.copy(),
                        }

                    show_status(filename)
                    console.print("[green]New row added.[/green]\n")

            if current_record is not None:
                change_records.append(current_record)

        # Append new rows
        if added_rows:
            new_df = pd.DataFrame(added_rows, columns=columns)
            df = pd.concat([df, new_df], ignore_index=True)

        # Drop removed rows
        if removed_indices:
            df = df.drop(index=removed_indices).reset_index(drop=True)

        # Write backup file for removed rows
        if backup_filename and removed_rows:
            pd.DataFrame(removed_rows).to_csv(
                session.output_dir / backup_filename, index=False
            )

        if edited_count == 0 and not added_rows and not removed_indices:
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
            f"{len(added_rows)} row(s) added, "
            f"{len(removed_indices)} row(s) removed.[/dim]\n"
        )

        if not Confirm.ask("[bold green]Save changes?[/bold green]"):
            continue

        out = session.save_step(df, "manual_edit")
        session.logger.log(
            "Manual Edit",
            f"Edited {edited_count} row(s), added {len(added_rows)} row(s), "
            f"removed {len(removed_indices)} row(s). "
            f"Conditions: {format_expression(expr)} | "
            f"Saved: {out.name}",
        )

        # Write change report
        report_msg = ""
        if change_records:
            report_path = _write_report(
                session.output_dir, out.name, columns, change_records,
            )
            report_msg = f"  Report: [bold]{report_path.name}[/bold]\n"

        console.print(
            f"\n[green]Done![/green] Saved as [bold]{out.name}[/bold]\n"
            f"{report_msg}"
        )
        console.input("[dim]Press Enter to continue...[/dim]")
        return
