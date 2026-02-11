"""Squash: merge equivalent rows by identity columns with user-guided value selection."""

from __future__ import annotations

import curses
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from rich.prompt import Confirm, Prompt

from csv_me.menu import clear_screen, console, pick_columns, preview_df, show_menu, show_status
from csv_me.session import Session


def _best_effort_values(group: pd.DataFrame, all_columns: list[str], id_columns: list[str]) -> dict[str, str]:
    """Build a best-effort squashed row using the most common value per column.

    For identity columns the value is constant across the group.
    For other columns the mode (most frequent non-null value) is used.
    """
    result: dict[str, str] = {}
    for col in all_columns:
        if col not in group.columns:
            result[col] = ""
            continue
        if col in id_columns:
            result[col] = str(group[col].iloc[0])
            continue
        non_null = group[col].dropna()
        if non_null.empty:
            result[col] = ""
            continue
        mode = non_null.astype(str).mode()
        result[col] = str(mode.iloc[0]) if not mode.empty else str(non_null.iloc[0])
    return result


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


def _squash_editor(
    stdscr: Any,
    columns: list[str],
    values: dict[str, str],
    group: pd.DataFrame,
    header_info: str,
) -> tuple[dict[str, str], list[str], list[str]] | str | None:
    """Curses-based squash editor.

    Top section shows the original rows in compact text.
    Bottom section shows the editable suggested squash row with
    arrow-key navigation and inline editing (same UX as manual_edit).

    Returns (edited_values, new_columns, ordered_columns), ``"remove"``
    to remove the entire group, ``"terminate"`` to stop the squash early,
    or None to skip.
    """
    curses.curs_set(1)
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_YELLOW, -1)
    modified_attr = curses.color_pair(1) | curses.A_BOLD
    stdscr.keypad(True)

    original_values = {col: str(v) for col, v in values.items()}
    cols = list(columns)
    new_cols: list[str] = []
    edited = {col: str(v) for col, v in values.items()}
    cursor_pos = {col: len(edited[col]) for col in cols}
    current_field = 0
    scroll_offset = 0
    col_scroll = 0   # horizontal scroll index for original rows display
    row_scroll = 0   # vertical scroll index for original rows display

    max_col_len = max(len(c) for c in cols) if cols else 0

    # Find max width per column (considering header name and all cell values)
    col_widths: dict[str, int] = {}
    for col in cols:
        w = len(col)
        for _, row in group.iterrows():
            val = "" if pd.isna(row.get(col, "")) else str(row.get(col, ""))
            w = max(w, len(val))
        col_widths[col] = w

    # Pre-extract row data for display (keep original CSV row numbers, 1-based)
    row_data: list[tuple[int, dict[str, str]]] = []
    for idx, row in group.iterrows():
        row_data.append((idx + 1, {
            col: "" if pd.isna(row.get(col, "")) else str(row.get(col, ""))
            for col in cols
        }))

    SHIFT_UP = curses.KEY_SR
    SHIFT_DOWN = curses.KEY_SF
    SHIFT_LEFT = curses.KEY_SLEFT
    SHIFT_RIGHT = curses.KEY_SRIGHT

    while True:
        height, width = stdscr.getmaxyx()
        stdscr.erase()

        y = 0

        # Header
        try:
            stdscr.addnstr(y, 0, f"  {header_info}", width - 1, curses.A_BOLD)
            y += 1
            stdscr.addnstr(
                y, 0,
                "  [\u2191\u2193] Navigate  [\u2190\u2192] Cursor  "
                "[Shift+\u2191\u2193] Scroll rows  [Shift+\u2190\u2192] Scroll columns  "
                "[Ctrl+N] New col  [Ctrl+D] Remove  [Ctrl+U] Undo  [Ctrl+T] Stop  [Enter] Save  [Esc] Skip",
                width - 1, curses.A_DIM,
            )
            y += 2
        except curses.error:
            pass

        # Original rows section — built dynamically from col_scroll
        visible_cols = cols[col_scroll:]
        scroll_hint = f" (col {col_scroll + 1}+)" if col_scroll > 0 else ""

        try:
            stdscr.addnstr(y, 0, f"  Original rows:{scroll_hint}", width - 1, curses.A_DIM)
            y += 1
        except curses.error:
            pass

        # Build header + row lines from visible columns
        max_row_num = max(rn for rn, _ in row_data)
        row_num_width = len(str(max_row_num))
        row_prefix_len = len(f"    Row {'0' * row_num_width}:  ")
        header_line = " " * row_prefix_len + " | ".join(
            c.ljust(col_widths.get(c, len(c))) for c in visible_cols
        )

        # Build row lines from visible columns, apply row_scroll
        visible_row_data = row_data[row_scroll:]

        all_row_lines: list[str] = []
        for row_num, rd in visible_row_data:
            num_str = str(row_num).rjust(row_num_width)
            vals = [rd.get(col, "").ljust(col_widths.get(col, len(col))) for col in visible_cols]
            all_row_lines.append(f"    Row {num_str}:  " + " | ".join(vals))

        # Reserve at least (len(cols) + 3) lines for the edit section
        edit_section_min = len(cols) + 3
        # Budget: 1 for header + as many rows as fit
        orig_budget = max(height - y - edit_section_min - 1, 2)

        # Always show column header
        try:
            stdscr.addnstr(y, 0, header_line, width - 1, curses.A_DIM)
            y += 1
        except curses.error:
            pass
        row_budget = orig_budget - 1  # subtract header line

        for i, line in enumerate(all_row_lines):
            if i >= row_budget:
                remaining = len(all_row_lines) - i
                try:
                    stdscr.addnstr(y, 0, f"    ... ({remaining} more row{'s' if remaining != 1 else ''})", width - 1, curses.A_DIM)
                    y += 1
                except curses.error:
                    pass
                break
            try:
                stdscr.addnstr(y, 0, line, width - 1, curses.A_DIM)
                y += 1
            except curses.error:
                pass

        # Separator
        y += 1
        try:
            stdscr.addnstr(y, 0, "  Suggested squash:", width - 1, curses.A_BOLD)
            y += 1
        except curses.error:
            pass

        # Editable fields
        field_start_y = y
        field_area = max(height - field_start_y - 1, 1)

        if current_field < scroll_offset:
            scroll_offset = current_field
        elif current_field >= scroll_offset + field_area:
            scroll_offset = current_field - field_area + 1

        cursor_y, cursor_x = field_start_y, 0
        visible_end = min(len(cols), scroll_offset + field_area)

        for i in range(scroll_offset, visible_end):
            fy = field_start_y + (i - scroll_offset)
            col = cols[i]
            val = edited[col]
            padded = col.rjust(max_col_len)
            is_modified = val != original_values.get(col, "")

            try:
                if i == current_field:
                    prefix = " \u25b8 "
                    label = f"{padded}:  "
                    val_x = len(prefix) + len(label)
                    max_val = max(width - val_x - 1, 0)
                    display_val = val[:max_val]

                    label_attr = modified_attr if is_modified else curses.A_BOLD
                    stdscr.addnstr(fy, 0, prefix, width - 1, curses.A_BOLD)
                    stdscr.addnstr(
                        fy, len(prefix), label,
                        max(width - 1 - len(prefix), 0), label_attr,
                    )
                    if display_val:
                        stdscr.addnstr(fy, val_x, display_val, max_val)

                    cursor_y = fy
                    cursor_x = val_x + min(cursor_pos[col], max_val)
                else:
                    label_part = f"   {padded}:  "
                    label_attr = modified_attr if is_modified else 0
                    stdscr.addnstr(fy, 0, label_part, width - 1, label_attr)
                    val_x = len(label_part)
                    max_val = max(width - val_x - 1, 0)
                    if val and max_val > 0:
                        stdscr.addnstr(fy, val_x, val[:max_val], max_val)
            except curses.error:
                pass

        try:
            stdscr.move(cursor_y, cursor_x)
        except curses.error:
            pass

        stdscr.refresh()

        key = stdscr.getch()
        col = cols[current_field]

        if key == 27:  # Esc — skip
            return None
        elif key == 20:  # Ctrl+T — terminate squash early
            return "terminate"
        elif key == 4:  # Ctrl+D — remove group
            return "remove"
        elif key in (10, 13, curses.KEY_ENTER):
            return edited, new_cols, cols
        elif key == 21:  # Ctrl+U — undo all changes
            cols = list(columns)
            new_cols = []
            edited = {col: str(v) for col, v in values.items()}
            cursor_pos = {col: len(edited[col]) for col in cols}
            max_col_len = max(len(c) for c in cols) if cols else 0
            current_field = min(current_field, len(cols) - 1)
            scroll_offset = 0
        elif key == 14:  # Ctrl+N — add new column
            name = _curses_text_input(stdscr, "New column name: ")
            if name and name not in cols:
                insert_at = current_field + 1
                cols.insert(insert_at, name)
                new_cols.append(name)
                edited[name] = ""
                cursor_pos[name] = 0
                col_widths[name] = len(name)
                max_col_len = max(max_col_len, len(name))
                current_field = insert_at
            elif name and name in cols:
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
        elif key == SHIFT_LEFT:
            if col_scroll > 0:
                col_scroll -= 1
        elif key == SHIFT_RIGHT:
            if col_scroll < len(cols) - 1:
                col_scroll += 1
        elif key == SHIFT_UP:
            if row_scroll > 0:
                row_scroll -= 1
        elif key == SHIFT_DOWN:
            if row_scroll < len(row_data) - 1:
                row_scroll += 1
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


def _edit_squash_curses(
    columns: list[str],
    values: dict[str, str],
    group: pd.DataFrame,
    header_info: str,
) -> tuple[dict[str, str], list[str], list[str]] | str | None:
    """Launch the curses squash editor.

    Returns (edited_values, new_columns, ordered_columns), ``"remove"``,
    ``"terminate"``, or None to skip.
    """
    return curses.wrapper(_squash_editor, columns, values, group, header_info)


def _init_report(output_dir: Path, step: int, columns: list[str]) -> Path:
    """Create the squash report file with a header.

    Uses the next step number so the filename is unique per squash run.
    """
    report_path = output_dir / f"{step + 1:02d}_squash_report.txt"
    sep = "=" * 60

    with open(report_path, "w") as f:
        f.write(f"{sep}\n")
        f.write("Squash Report\n")
        f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"{sep}\n\n")

        col_header = " | ".join(columns)
        f.write(f"Columns: {col_header}\n\n")

    return report_path


def _append_report_record(
    report_path: Path,
    columns: list[str],
    record: dict,
) -> None:
    """Append a single squash record to the report file."""
    with open(report_path, "a") as f:
        f.write(
            f"--- Group {record['group_num']} ({record['id_desc']}) "
            f"[{len(record['original_rows'])} rows -> 1] ---\n"
        )

        for i, orig in enumerate(record["original_rows"], 1):
            vals = " | ".join(orig.get(c, "") for c in columns)
            f.write(f"  Row {i}:    {vals}\n")

        output_vals = " | ".join(record["output_row"].get(c, "") for c in columns)
        f.write(f"  Output:   {output_vals}\n")

        for i, new_row in enumerate(record.get("new_rows") or [], 1):
            new_vals = " | ".join(new_row.get(c, "") for c in columns)
            label = f"  New Row {i}:" if len(record.get("new_rows") or []) > 1 else "  New Row: "
            f.write(f"{label} {new_vals}\n")

        f.write("\n")


def run(session: Session) -> None:
    while True:
        clear_screen()
        show_status(session.current_filename)

        choice = show_menu("Squash", ["Squash equivalent rows"])
        if choice == 0:
            return

        df = session.read_current()
        columns = list(df.columns)
        filename = session.current_filename

        # --- Ask about separate file for squashed rows ---
        clear_screen()
        show_status(filename)
        squash_file: str | None = None
        if Confirm.ask(
            "[bold green]Output squashed (original) rows to a separate file for review?[/bold green]",
            default=True,
        ):
            name = Prompt.ask(
                "[bold]Filename for squashed rows[/bold]",
                default="squashed_rows.csv",
            )
            if not name.endswith(".csv"):
                name += ".csv"
            squash_file = name

        # --- Ask about separate file for removed rows ---
        remove_file: str | None = None
        if Confirm.ask(
            "[bold green]Output removed groups to a separate file?[/bold green]",
            default=True,
        ):
            name = Prompt.ask(
                "[bold]Filename for removed rows[/bold]",
                default="removed_rows.csv",
            )
            if not name.endswith(".csv"):
                name += ".csv"
            remove_file = name

        # --- Pick identity columns ---
        clear_screen()
        show_status(filename)
        console.print(
            "[bold]Select the columns that uniquely identify rows.[/bold]\n"
            "[dim]Rows with identical values in these columns will be squashed together.[/dim]\n"
        )
        id_columns = pick_columns(df, prompt_text="Identity columns")
        if not id_columns:
            console.print("[yellow]No columns selected.[/yellow]")
            console.input("[dim]Press Enter to continue...[/dim]")
            continue

        console.print(f"\n[dim]Identity columns: {', '.join(id_columns)}[/dim]\n")

        # --- Find groups with duplicates ---
        grouped = df.groupby(id_columns, sort=False)
        dup_groups = [(key, grp) for key, grp in grouped if len(grp) > 1]

        if not dup_groups:
            console.print("[yellow]No duplicate groups found for the selected columns.[/yellow]")
            console.input("[dim]Press Enter to continue...[/dim]")
            continue

        console.print(
            f"[bold]Found {len(dup_groups)} group(s) with duplicate rows.[/bold]\n"
        )
        if not Confirm.ask("[bold green]Proceed with squash?[/bold green]"):
            continue

        # --- Process each group ---
        squashed_count = 0
        removed_count = 0
        squashed_original_rows: list[pd.DataFrame] = []
        removed_original_rows: list[pd.DataFrame] = []
        result_rows: list[dict[str, str]] = []
        added_rows: list[dict[str, str]] = []
        skipped_groups: list[pd.DataFrame] = []
        report_path = _init_report(session.output_dir, session.step, columns)

        # Collect non-duplicate rows (pass through unchanged)
        non_dup_indices = set()
        for _, grp in grouped:
            if len(grp) == 1:
                non_dup_indices.update(grp.index.tolist())

        stopped_early = False
        processed_groups: set[int] = set()

        for group_num, (key, group) in enumerate(dup_groups, 1):
            processed_groups.add(group_num)

            # Build identity description
            if isinstance(key, tuple):
                id_desc = ", ".join(f"{c}={k}" for c, k in zip(id_columns, key))
            else:
                id_desc = f"{id_columns[0]}={key}"

            header = (
                f"Squash \u2014 Group {group_num} of {len(dup_groups)}  "
                f"({id_desc})  [{len(group)} rows]"
            )

            best = _best_effort_values(group, columns, id_columns)
            result = _edit_squash_curses(columns, best, group, header)
            clear_screen()

            if result == "terminate":
                skipped_groups.append(group)
                stopped_early = True
                break
            elif result is None:
                # Skipped
                skipped_groups.append(group)
                show_status(filename)
                console.print("[dim]Group skipped \u2014 original rows kept.[/dim]")
            elif result == "remove":
                removed_count += 1
                removed_original_rows.append(group)
                # Write removed rows to file incrementally
                if remove_file:
                    remove_path = session.output_dir / remove_file
                    write_header = not remove_path.exists()
                    group.to_csv(remove_path, mode="a", index=False, header=write_header)
                show_status(filename)
                console.print(
                    f"[red]Group removed![/red] "
                    f"({len(group)} rows removed)\n"
                )
            else:
                edited_values, new_cols, ordered_cols = result

                # Register any new columns and update column ordering
                for nc in new_cols:
                    if nc not in df.columns:
                        df[nc] = ""
                columns = ordered_cols

                # Got edited values back
                result_rows.append(edited_values)
                squashed_count += 1
                squashed_original_rows.append(group)

                show_status(filename)
                console.print(
                    f"[green]Group squashed![/green] "
                    f"({len(group)} rows \u2192 1)\n"
                )

                # Offer to create new rows based on the squashed values
                group_new_rows: list[dict[str, str]] = []
                new_row_count = 0
                while Confirm.ask(
                    "[bold green]Add a new row based on the squashed values?[/bold green]"
                ):
                    new_row_count += 1
                    new_header = (
                        f"New row {new_row_count} \u2014 Group {group_num} of {len(dup_groups)}  "
                        f"({id_desc})"
                    )
                    new_result = _edit_squash_curses(
                        columns,
                        {c: edited_values.get(c, "") for c in columns},
                        group,
                        new_header,
                    )
                    clear_screen()
                    if new_result is not None and new_result != "remove":
                        new_values, extra_cols, new_ordered_cols = new_result
                        for nc in extra_cols:
                            if nc not in df.columns:
                                df[nc] = ""
                        columns = new_ordered_cols
                        added_rows.append(new_values)
                        group_new_rows.append(new_values)
                        show_status(filename)
                        console.print(f"[green]New row {new_row_count} added.[/green]\n")
                    else:
                        show_status(filename)

                # Append to the report immediately
                orig_rows = []
                for _, row in group.iterrows():
                    orig_rows.append({
                        col: "" if pd.isna(row.get(col, "")) else str(row.get(col, ""))
                        for col in columns
                    })
                _append_report_record(report_path, columns, {
                    "group_num": group_num,
                    "id_desc": id_desc,
                    "original_rows": orig_rows,
                    "output_row": {c: edited_values.get(c, "") for c in columns},
                    "new_rows": [{c: nv.get(c, "") for c in columns} for nv in group_new_rows]
                    if group_new_rows
                    else None,
                })

                # Write squashed original rows to file incrementally
                if squash_file:
                    squash_path = session.output_dir / squash_file
                    write_header = not squash_path.exists()
                    group.to_csv(squash_path, mode="a", index=False, header=write_header)

        # Treat unprocessed groups as skipped
        if stopped_early:
            for i, (_, grp) in enumerate(dup_groups, 1):
                if i not in processed_groups:
                    skipped_groups.append(grp)

        if squashed_count == 0 and removed_count == 0 and not skipped_groups:
            if report_path.exists():
                report_path.unlink()
            console.print("[yellow]No groups were squashed or removed.[/yellow]")
            console.input("[dim]Press Enter to continue...[/dim]")
            continue

        # --- Build final DataFrame ---
        non_dup_df = df.loc[sorted(non_dup_indices)] if non_dup_indices else pd.DataFrame(columns=columns)

        parts = [non_dup_df]
        for grp in skipped_groups:
            parts.append(grp)
        if result_rows:
            squashed_df = pd.DataFrame(result_rows, columns=columns)
            parts.append(squashed_df)
        if added_rows:
            added_df = pd.DataFrame(added_rows, columns=columns)
            parts.append(added_df)

        final_df = pd.concat(parts, ignore_index=True)
        # Reorder columns to match the user's ordering (including new columns)
        final_df = final_df.reindex(columns=columns, fill_value="")

        # --- Preview and save ---
        clear_screen()
        show_status(filename)
        preview_df(final_df, title="Squash Result")

        total_squashed_rows = sum(len(grp) for grp in squashed_original_rows)
        total_removed_rows = sum(len(grp) for grp in removed_original_rows)
        console.print(
            f"[dim]{squashed_count} group(s) squashed "
            f"({total_squashed_rows} rows \u2192 {squashed_count}), "
            f"{len(added_rows)} row(s) added. "
            f"{removed_count} group(s) removed ({total_removed_rows} rows). "
            f"{len(skipped_groups)} group(s) skipped.[/dim]\n"
        )

        if not Confirm.ask("[bold green]Save changes?[/bold green]"):
            if squash_file:
                squash_path = session.output_dir / squash_file
                if squash_path.exists():
                    squash_path.unlink()
            if remove_file:
                remove_path = session.output_dir / remove_file
                if remove_path.exists():
                    remove_path.unlink()
            if report_path.exists():
                report_path.unlink()
            continue

        out = session.save_step(final_df, "squash")

        session.logger.log(
            "Squash",
            f"Identity columns: {id_columns} | "
            f"Groups squashed: {squashed_count} | "
            f"Rows added: {len(added_rows)} | "
            f"Groups removed: {removed_count} ({total_removed_rows} rows) | "
            f"Rows before: {len(df)} | Rows after: {len(final_df)} | "
            f"Saved: {out.name}"
            + (f" | Squashed rows file: {squash_file}" if squash_file else "")
            + (f" | Removed rows file: {remove_file}" if remove_file else ""),
        )

        report_msg = ""
        if squashed_count > 0:
            report_msg = f"  Report: [bold]{report_path.name}[/bold]"

        console.print(
            f"\n[green]Done![/green] Saved as [bold]{out.name}[/bold]\n"
        )
        if report_msg:
            console.print(report_msg)
        if squash_file:
            console.print(
                f"[dim]Original squashed rows saved to: {squash_file}[/dim]"
            )
        if remove_file and removed_count > 0:
            console.print(
                f"[dim]Removed rows saved to: {remove_file}[/dim]"
            )
        console.print()
        console.input("[dim]Press Enter to continue...[/dim]")
        return
