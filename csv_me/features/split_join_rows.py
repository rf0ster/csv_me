"""Split-Join: split each input row into multiple output rows with user-defined mappings."""

from __future__ import annotations

import pandas as pd
from rich.prompt import Confirm, Prompt

from csv_me.conditions import (
    Condition,
    build_conditions,
    evaluate_conditions,
    format_condition,
)
from csv_me.menu import clear_screen, console, preview_df, show_menu, show_status
from csv_me.session import Session


def _define_conditions(
    filename: str,
    input_columns: list[str],
    row_num: int,
    output_headers: list[str],
    common_mappings: dict[str, str],
    row_mappings: list[dict[str, str]],
    row_conditions: list[list[Condition]],
) -> list[Condition]:
    """UI loop to define conditions for one output row template.

    Returns a list of Condition objects (may be empty).
    """
    _refresh(filename)
    _show_mapping_progress(
        output_headers, common_mappings, row_mappings, row_conditions
    )

    if not Confirm.ask(
        f"[bold green]Add conditions for Output Row {row_num}?[/bold green]"
    ):
        return []

    def header_fn() -> None:
        _refresh(filename)
        _show_mapping_progress(
            output_headers, common_mappings, row_mappings, row_conditions
        )

    return build_conditions(input_columns, header_fn=header_fn)


def _refresh(filename: str) -> None:
    """Clear screen and show the working file status bar."""
    clear_screen()
    show_status(filename)


def _show_input_columns(input_columns: list[str]) -> None:
    console.print("[bold]Input columns:[/bold]")
    for i, col in enumerate(input_columns, 1):
        console.print(f"  {i}. {col}")
    console.print()


def _show_mapping_progress(
    output_headers: list[str],
    common_mappings: dict[str, str],
    row_mappings: list[dict[str, str]] | None = None,
    row_conditions: list[list[Condition]] | None = None,
) -> None:
    """Display what has been mapped so far."""
    if not common_mappings and not row_mappings:
        return
    console.print("[bold]Mappings so far:[/bold]")
    if common_mappings:
        console.print("  [bold]Common:[/bold]")
        for out_col, in_col in common_mappings.items():
            console.print(f"    {out_col} <- {in_col}")
    if row_mappings:
        for i, mapping in enumerate(row_mappings, 1):
            console.print(f"  [bold]Output Row {i}:[/bold]")
            for out_col in output_headers:
                if out_col in common_mappings:
                    continue
                in_col = mapping.get(out_col, "(empty)")
                console.print(f"    {out_col} <- {in_col}")
            # Show conditions for this row if any
            if row_conditions and i <= len(row_conditions) and row_conditions[i - 1]:
                console.print(f"    [bold]Conditions (ALL must match):[/bold]")
                for cond in row_conditions[i - 1]:
                    console.print(f"      [cyan]IF[/cyan] {format_condition(cond)}")
    console.print()


def _ask_output_headers(filename: str, input_columns: list[str]) -> list[str] | None:
    """Prompt user to define the output column headers."""
    _refresh(filename)
    _show_input_columns(input_columns)

    raw = Prompt.ask(
        "[bold green]Enter the output column names (comma-separated)[/bold green]"
    )
    headers = [h.strip() for h in raw.split(",") if h.strip()]
    if not headers:
        console.print("[yellow]No column names provided.[/yellow]")
        return None
    return headers


def _pick_input_column(input_columns: list[str], prompt_text: str) -> str | None:
    """Let user pick one input column or leave blank to skip.

    Returns the input column name, or None if the user skips.
    """
    console.print(f"[bold]{prompt_text}:[/bold]")
    for i, col in enumerate(input_columns, 1):
        console.print(f"  [bold]{i}.[/bold] {col}")
    console.print(f"  [bold]0.[/bold] Leave empty")
    console.print()

    raw = Prompt.ask("[bold green]Enter column number (0 to skip)[/bold green]")
    try:
        idx = int(raw.strip())
    except ValueError:
        return None
    if idx == 0:
        return None
    if 1 <= idx <= len(input_columns):
        return input_columns[idx - 1]
    console.print("[yellow]Invalid selection.[/yellow]")
    return None


def _map_common_columns(
    filename: str,
    output_headers: list[str],
    input_columns: list[str],
) -> dict[str, str]:
    """Let user map output columns that are common across all output rows.

    Returns a dict of {output_col: input_col}.
    """
    common: dict[str, str] = {}

    _refresh(filename)
    console.print(f"[bold]Output columns:[/bold] {', '.join(output_headers)}\n")

    if not Confirm.ask(
        "[bold green]Do you want to specify common columns "
        "(copied to all output rows from a single input row)?[/bold green]"
    ):
        return common

    while True:
        unmapped = [h for h in output_headers if h not in common]
        if not unmapped:
            console.print("[yellow]All output columns are mapped as common.[/yellow]")
            break

        _refresh(filename)
        console.print(f"[bold]Output columns:[/bold] {', '.join(output_headers)}\n")
        _show_mapping_progress(output_headers, common)

        console.print("[bold]Select output column to map as common:[/bold]")
        for i, col in enumerate(unmapped, 1):
            console.print(f"  [bold]{i}.[/bold] {col}")
        console.print(f"  [bold]0.[/bold] Done with common columns")
        console.print()

        raw = Prompt.ask("[bold green]Enter column number[/bold green]")
        try:
            idx = int(raw.strip())
        except ValueError:
            continue
        if idx == 0:
            break
        if not (1 <= idx <= len(unmapped)):
            console.print("[yellow]Invalid selection.[/yellow]")
            continue

        out_col = unmapped[idx - 1]

        _refresh(filename)
        console.print(f"[bold]Output columns:[/bold] {', '.join(output_headers)}\n")
        _show_mapping_progress(output_headers, common)

        in_col = _pick_input_column(
            input_columns, f"Map common output '{out_col}' from input column"
        )
        if in_col:
            common[out_col] = in_col

    return common


def _map_output_rows(
    filename: str,
    output_headers: list[str],
    input_columns: list[str],
    common_mappings: dict[str, str],
) -> tuple[list[dict[str, str]], list[list[Condition]]]:
    """Let user define per-output-row mappings for non-common columns.

    Returns a tuple of (row_mappings, row_conditions) where:
    - row_mappings: list of dicts, one per output row template
    - row_conditions: parallel list of condition lists (empty = unconditional)
    """
    non_common = [h for h in output_headers if h not in common_mappings]

    if not non_common:
        # Every column is common — one output row per input row
        return [{}], [[]]

    row_mappings: list[dict[str, str]] = []
    row_conditions: list[list[Condition]] = []
    row_num = 1

    while True:
        mapping: dict[str, str] = {}

        for out_col in non_common:
            _refresh(filename)
            console.print(f"[bold]Output columns:[/bold] {', '.join(output_headers)}\n")
            _show_mapping_progress(output_headers, common_mappings, row_mappings, row_conditions)

            if mapping:
                console.print(f"  [bold]Output Row {row_num} (in progress):[/bold]")
                for mapped_col, mapped_in in mapping.items():
                    console.print(f"    {mapped_col} <- {mapped_in}")
                remaining = [c for c in non_common if c not in mapping]
                for c in remaining:
                    console.print(f"    {c} <- [dim]...[/dim]")
                console.print()

            in_col = _pick_input_column(
                input_columns, f"Output Row {row_num} '{out_col}'"
            )
            if in_col:
                mapping[out_col] = in_col

        row_mappings.append(mapping)
        # Temporarily add empty conditions so progress display is consistent
        row_conditions.append([])

        # Ask about conditions for this row template
        conditions = _define_conditions(
            filename, input_columns, row_num,
            output_headers, common_mappings, row_mappings, row_conditions,
        )
        row_conditions[-1] = conditions

        _refresh(filename)
        console.print(f"[bold]Output columns:[/bold] {', '.join(output_headers)}\n")
        _show_mapping_progress(output_headers, common_mappings, row_mappings, row_conditions)

        if not Confirm.ask(
            "[bold green]Map another output row from the same input row?[/bold green]"
        ):
            break
        row_num += 1

    return row_mappings, row_conditions


def run(session: Session) -> None:
    while True:
        clear_screen()
        show_status(session.current_filename)

        choice = show_menu("Split-Join Rows", ["Define new output mapping"])
        if choice == 0:
            return

        df = session.read_current()
        input_columns = list(df.columns)
        filename = session.current_filename

        # Step 1: Define output headers
        output_headers = _ask_output_headers(filename, input_columns)
        if output_headers is None:
            continue

        # Step 2: Common column mappings
        common_mappings = _map_common_columns(
            filename, output_headers, input_columns
        )

        # Step 3: Per-output-row mappings
        row_mappings, row_conditions = _map_output_rows(
            filename, output_headers, input_columns, common_mappings
        )

        # Summary before processing
        _refresh(filename)
        console.print(f"[bold]Output columns:[/bold] {', '.join(output_headers)}\n")
        _show_mapping_progress(output_headers, common_mappings, row_mappings, row_conditions)

        if not Confirm.ask("[bold green]Proceed with split-join?[/bold green]"):
            continue

        # Step 4: Process the data
        output_rows: list[dict[str, str]] = []
        for _, input_row in df.iterrows():
            for idx, mapping in enumerate(row_mappings):
                if not evaluate_conditions(input_row, row_conditions[idx]):
                    continue
                new_row: dict[str, str] = {}
                for out_col in output_headers:
                    if out_col in common_mappings:
                        new_row[out_col] = input_row[common_mappings[out_col]]
                    elif out_col in mapping:
                        new_row[out_col] = input_row[mapping[out_col]]
                    else:
                        new_row[out_col] = ""
                output_rows.append(new_row)

        result_df = pd.DataFrame(output_rows, columns=output_headers)

        _refresh(filename)
        preview_df(result_df, title="Split-Join Result")

        out = session.save_step(result_df, "split_join")
        condition_summary = {
            i + 1: [format_condition(c) for c in conds]
            for i, conds in enumerate(row_conditions)
            if conds
        }
        session.logger.log(
            "Split-Join",
            f"Common mappings: {common_mappings} | "
            f"Row mappings ({len(row_mappings)}): {row_mappings} | "
            f"Row conditions: {condition_summary or 'none'} | "
            f"Input rows: {len(df)} | Output rows: {len(result_df)} | "
            f"Saved: {out.name}",
        )

        console.print(
            f"\n[green]Done![/green] {len(df)} input row(s) -> "
            f"{len(result_df)} output row(s). "
            f"Saved as [bold]{out.name}[/bold]\n"
        )
        console.input("[dim]Press Enter to continue...[/dim]")
        return
