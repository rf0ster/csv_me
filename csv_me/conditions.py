"""Shared condition logic for row-level predicates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pandas as pd
from rich.prompt import Prompt

from csv_me.menu import console


@dataclass
class Condition:
    """A single predicate evaluated against a row."""

    input_col: str
    operator: str  # "not_empty" | "equals" | "not_equals" | "contains"
    value: str | None  # None for not_empty


OPERATORS: list[tuple[str, str]] = [
    ("not_empty", "Column is not empty"),
    ("equals", "Column equals value"),
    ("not_equals", "Column does not equal value"),
    ("contains", "Column contains value"),
]


def format_condition(cond: Condition) -> str:
    """Return a human-readable description of a condition."""
    if cond.operator == "not_empty":
        return f'"{cond.input_col}" is not empty'
    if cond.operator == "equals":
        return f'"{cond.input_col}" equals "{cond.value}"'
    if cond.operator == "not_equals":
        return f'"{cond.input_col}" does not equal "{cond.value}"'
    if cond.operator == "contains":
        return f'"{cond.input_col}" contains "{cond.value}"'
    return f'"{cond.input_col}" {cond.operator} "{cond.value}"'


def evaluate_conditions(
    row: pd.Series, conditions: list[Condition]
) -> bool:
    """Evaluate all conditions against a row (AND logic).

    Returns True if all conditions pass or if the list is empty.
    """
    for cond in conditions:
        raw = row.get(cond.input_col, "")
        val = "" if pd.isna(raw) else str(raw).strip()

        if cond.operator == "not_empty":
            if val == "":
                return False
        elif cond.operator == "equals":
            if val != (cond.value or ""):
                return False
        elif cond.operator == "not_equals":
            if val == (cond.value or ""):
                return False
        elif cond.operator == "contains":
            if (cond.value or "") not in val:
                return False
    return True


def build_conditions(
    columns: list[str],
    header_fn: Callable[[], None] | None = None,
) -> list[Condition]:
    """Generic UI loop to build a list of conditions.

    Args:
        columns: Available column names to condition on.
        header_fn: Optional callback invoked at the start of each loop
            iteration (lets caller refresh screen, display context).

    Returns:
        List of Condition objects (may be empty).
    """
    conditions: list[Condition] = []

    while True:
        if header_fn:
            header_fn()

        if conditions:
            console.print("[bold]Conditions so far:[/bold]")
            for c in conditions:
                console.print(f"  [cyan]IF[/cyan] {format_condition(c)}")
            console.print()

        # Pick condition type
        console.print("[bold]Select condition type:[/bold]")
        for i, (_, label) in enumerate(OPERATORS, 1):
            console.print(f"  [bold]{i}.[/bold] {label}")
        console.print(f"  [bold]0.[/bold] Done adding conditions")
        console.print()

        raw = Prompt.ask("[bold green]Enter choice[/bold green]")
        try:
            idx = int(raw.strip())
        except ValueError:
            continue
        if idx == 0:
            break
        if not (1 <= idx <= len(OPERATORS)):
            console.print("[yellow]Invalid selection.[/yellow]")
            continue

        op = OPERATORS[idx - 1][0]

        # Pick column
        if header_fn:
            header_fn()
        console.print("[bold]Select column for condition:[/bold]")
        for i, col in enumerate(columns, 1):
            console.print(f"  [bold]{i}.[/bold] {col}")
        console.print()

        col_raw = Prompt.ask("[bold green]Enter column number[/bold green]")
        try:
            col_idx = int(col_raw.strip())
        except ValueError:
            continue
        if not (1 <= col_idx <= len(columns)):
            console.print("[yellow]Invalid selection.[/yellow]")
            continue

        in_col = columns[col_idx - 1]

        # Get comparison value if needed
        cond_value: str | None = None
        if op != "not_empty":
            cond_value = Prompt.ask(
                f"[bold green]Enter value to compare with '{in_col}'[/bold green]"
            )

        conditions.append(Condition(input_col=in_col, operator=op, value=cond_value))
        console.print(
            f"[green]Added:[/green] {format_condition(conditions[-1])}"
        )

    return conditions
