"""Shared condition logic for row-level predicates."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Union

import pandas as pd
from rich.prompt import Prompt

from csv_me.menu import console


# ---------------------------------------------------------------------------
# Leaf node
# ---------------------------------------------------------------------------

@dataclass
class Condition:
    """A single predicate evaluated against a row."""

    input_col: str
    operator: str  # "not_empty" | "equals" | "not_equals" | "contains" | "word_count" | "alpha_only"
    value: str | None  # None for not_empty


# ---------------------------------------------------------------------------
# Composite expression types
# ---------------------------------------------------------------------------

@dataclass
class AndExpr:
    """All children must be true."""

    children: list[Expression] = field(default_factory=list)


@dataclass
class OrExpr:
    """Any child must be true."""

    children: list[Expression] = field(default_factory=list)


@dataclass
class NotExpr:
    """Negate one expression."""

    child: Expression


Expression = Union[Condition, AndExpr, OrExpr, NotExpr]


OPERATORS: list[tuple[str, str]] = [
    ("not_empty", "Column is not empty"),
    ("equals", "Column equals value"),
    ("not_equals", "Column does not equal value"),
    ("contains", "Column contains value"),
    ("word_count", "Word count comparison"),
    ("alpha_only", "Column contains only letters and spaces"),
]

WORD_COUNT_COMPARISONS: list[tuple[str, str]] = [
    ("gt", "Greater than"),
    ("lt", "Less than"),
    ("eq", "Equal to"),
]


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

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
    if cond.operator == "word_count":
        parts = (cond.value or "").split(":", 1)
        if len(parts) == 2:
            cmp_op, num = parts
            sym = {"gt": ">", "lt": "<", "eq": "="}.get(cmp_op, cmp_op)
            return f'"{cond.input_col}" word count {sym} {num}'
        return f'"{cond.input_col}" word count {cond.value}'
    if cond.operator == "alpha_only":
        return f'"{cond.input_col}" is alpha-only'
    return f'"{cond.input_col}" {cond.operator} "{cond.value}"'


def format_expression(expr: Expression, depth: int = 0) -> str:
    """Return an indented tree display of a boolean expression."""
    indent = "  " * depth
    if isinstance(expr, Condition):
        return f"{indent}{format_condition(expr)}"
    if isinstance(expr, AndExpr):
        if not expr.children:
            return f"{indent}ALL of: (empty)"
        lines = [f"{indent}ALL of:"]
        for child in expr.children:
            lines.append(format_expression(child, depth + 1))
        return "\n".join(lines)
    if isinstance(expr, OrExpr):
        if not expr.children:
            return f"{indent}ANY of: (empty)"
        lines = [f"{indent}ANY of:"]
        for child in expr.children:
            lines.append(format_expression(child, depth + 1))
        return "\n".join(lines)
    if isinstance(expr, NotExpr):
        lines = [f"{indent}NOT:"]
        lines.append(format_expression(expr.child, depth + 1))
        return "\n".join(lines)
    return f"{indent}(unknown expression)"


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

def _evaluate_single_condition(row: pd.Series, cond: Condition) -> bool:
    """Evaluate one Condition against a row."""
    raw = row.get(cond.input_col, "")
    val = "" if pd.isna(raw) else str(raw).strip()

    if cond.operator == "not_empty":
        return val != ""
    if cond.operator == "equals":
        return val == (cond.value or "")
    if cond.operator == "not_equals":
        return val != (cond.value or "")
    if cond.operator == "contains":
        return (cond.value or "") in val
    if cond.operator == "word_count":
        count = len(val.split()) if val else 0
        parts = (cond.value or "").split(":", 1)
        if len(parts) != 2:
            return False
        cmp_op, num_str = parts
        try:
            num = int(num_str)
        except ValueError:
            return False
        if cmp_op == "gt":
            return count > num
        if cmp_op == "lt":
            return count < num
        if cmp_op == "eq":
            return count == num
    if cond.operator == "alpha_only":
        return val.replace(" ", "").isalpha() if val else False
    return False


def evaluate_conditions(
    row: pd.Series, conditions: list[Condition]
) -> bool:
    """Evaluate all conditions against a row (AND logic).

    Returns True if all conditions pass or if the list is empty.
    """
    for cond in conditions:
        if not _evaluate_single_condition(row, cond):
            return False
    return True


def evaluate_expression(row: pd.Series, expr: Expression) -> bool:
    """Recursively evaluate a boolean expression tree against a row."""
    if isinstance(expr, Condition):
        return _evaluate_single_condition(row, expr)
    if isinstance(expr, AndExpr):
        return all(evaluate_expression(row, c) for c in expr.children)
    if isinstance(expr, OrExpr):
        return any(evaluate_expression(row, c) for c in expr.children)
    if isinstance(expr, NotExpr):
        return not evaluate_expression(row, expr.child)
    return False


# ---------------------------------------------------------------------------
# Building conditions (old flat API — preserved for backwards compat)
# ---------------------------------------------------------------------------

def _prompt_word_count_value() -> str | None:
    """Prompt for word-count comparison type and number.

    Returns a string like ``"gt:5"`` or None on invalid input.
    """
    console.print("[bold]Select comparison:[/bold]")
    for i, (_, label) in enumerate(WORD_COUNT_COMPARISONS, 1):
        console.print(f"  [bold]{i}.[/bold] {label}")
    console.print()

    raw = Prompt.ask("[bold green]Enter choice[/bold green]")
    try:
        cmp_idx = int(raw.strip())
    except ValueError:
        return None
    if not (1 <= cmp_idx <= len(WORD_COUNT_COMPARISONS)):
        console.print("[yellow]Invalid selection.[/yellow]")
        return None

    cmp_op = WORD_COUNT_COMPARISONS[cmp_idx - 1][0]

    num_raw = Prompt.ask("[bold green]Enter word count number[/bold green]")
    try:
        num = int(num_raw.strip())
    except ValueError:
        console.print("[yellow]Invalid number.[/yellow]")
        return None

    return f"{cmp_op}:{num}"


def _build_single_condition(
    columns: list[str],
    header_fn: Callable[[], None] | None = None,
) -> Condition | None:
    """Prompt for one condition (operator, column, value).

    Returns a Condition, or None if the user picks an invalid option.
    """
    # Pick condition type
    console.print("[bold]Select condition type:[/bold]")
    for i, (_, label) in enumerate(OPERATORS, 1):
        console.print(f"  [bold]{i}.[/bold] {label}")
    console.print()

    raw = Prompt.ask("[bold green]Enter choice[/bold green]")
    try:
        idx = int(raw.strip())
    except ValueError:
        return None
    if not (1 <= idx <= len(OPERATORS)):
        console.print("[yellow]Invalid selection.[/yellow]")
        return None

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
        return None
    if not (1 <= col_idx <= len(columns)):
        console.print("[yellow]Invalid selection.[/yellow]")
        return None

    in_col = columns[col_idx - 1]

    # Get comparison value if needed
    cond_value: str | None = None
    if op == "word_count":
        cond_value = _prompt_word_count_value()
        if cond_value is None:
            return None
    elif op not in ("not_empty", "alpha_only"):
        cond_value = Prompt.ask(
            f"[bold green]Enter value to compare with '{in_col}'[/bold green]"
        )

    return Condition(input_col=in_col, operator=op, value=cond_value)


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
        if op == "word_count":
            cond_value = _prompt_word_count_value()
            if cond_value is None:
                continue
        elif op not in ("not_empty", "alpha_only"):
            cond_value = Prompt.ask(
                f"[bold green]Enter value to compare with '{in_col}'[/bold green]"
            )

        conditions.append(Condition(input_col=in_col, operator=op, value=cond_value))
        console.print(
            f"[green]Added:[/green] {format_condition(conditions[-1])}"
        )

    return conditions


# ---------------------------------------------------------------------------
# Building expressions (new nested boolean API)
# ---------------------------------------------------------------------------

def _build_group(
    columns: list[str],
    group_type: str,
    header_fn: Callable[[], None] | None = None,
) -> AndExpr | OrExpr:
    """Recursive group builder for AND/OR groups.

    Args:
        columns: Available column names.
        group_type: "and" or "or".
        header_fn: Optional screen-refresh callback.

    Returns:
        An AndExpr or OrExpr containing the user's choices.
    """
    label = "AND" if group_type == "and" else "OR"
    children: list[Expression] = []

    while True:
        if header_fn:
            header_fn()

        if children:
            current = AndExpr(children=children) if group_type == "and" else OrExpr(children=children)
            console.print("[bold]Expression so far:[/bold]")
            console.print(format_expression(current))
            console.print()

        console.print(f"[bold]Add to {label} group:[/bold]")
        console.print(f"  [bold]1.[/bold] Add a condition")
        console.print(f"  [bold]2.[/bold] Add AND sub-group")
        console.print(f"  [bold]3.[/bold] Add OR sub-group")
        console.print(f"  [bold]4.[/bold] Add NOT (negate next item)")
        console.print(f"  [bold]0.[/bold] Done")
        console.print()

        raw = Prompt.ask("[bold green]Enter choice[/bold green]")
        try:
            choice = int(raw.strip())
        except ValueError:
            continue

        if choice == 0:
            break
        elif choice == 1:
            cond = _build_single_condition(columns, header_fn)
            if cond is not None:
                children.append(cond)
                console.print(f"[green]Added:[/green] {format_condition(cond)}")
        elif choice == 2:
            sub = _build_group(columns, "and", header_fn)
            if sub.children:
                children.append(sub)
                console.print("[green]Added AND sub-group.[/green]")
            else:
                console.print("[yellow]Empty sub-group discarded.[/yellow]")
        elif choice == 3:
            sub = _build_group(columns, "or", header_fn)
            if sub.children:
                children.append(sub)
                console.print("[green]Added OR sub-group.[/green]")
            else:
                console.print("[yellow]Empty sub-group discarded.[/yellow]")
        elif choice == 4:
            negated = _build_not(columns, header_fn)
            if negated is not None:
                children.append(negated)
                console.print("[green]Added NOT expression.[/green]")
        else:
            console.print("[yellow]Invalid selection.[/yellow]")

    if group_type == "and":
        return AndExpr(children=children)
    return OrExpr(children=children)


def _build_not(
    columns: list[str],
    header_fn: Callable[[], None] | None = None,
) -> NotExpr | None:
    """Prompt what to negate (condition, AND group, OR group), wrap in NotExpr."""
    if header_fn:
        header_fn()

    console.print("[bold]What to negate?[/bold]")
    console.print(f"  [bold]1.[/bold] A single condition")
    console.print(f"  [bold]2.[/bold] An AND group")
    console.print(f"  [bold]3.[/bold] An OR group")
    console.print(f"  [bold]0.[/bold] Cancel")
    console.print()

    raw = Prompt.ask("[bold green]Enter choice[/bold green]")
    try:
        choice = int(raw.strip())
    except ValueError:
        return None

    if choice == 0:
        return None
    elif choice == 1:
        cond = _build_single_condition(columns, header_fn)
        if cond is not None:
            return NotExpr(child=cond)
    elif choice == 2:
        sub = _build_group(columns, "and", header_fn)
        if sub.children:
            return NotExpr(child=sub)
        console.print("[yellow]Empty group — NOT discarded.[/yellow]")
    elif choice == 3:
        sub = _build_group(columns, "or", header_fn)
        if sub.children:
            return NotExpr(child=sub)
        console.print("[yellow]Empty group — NOT discarded.[/yellow]")
    else:
        console.print("[yellow]Invalid selection.[/yellow]")

    return None


def build_expression(
    columns: list[str],
    header_fn: Callable[[], None] | None = None,
) -> AndExpr:
    """Public entry point: build a nested boolean expression.

    Top-level items are implicitly ANDed (simple case stays simple;
    to get OR at the top level, add an OR sub-group).

    Returns:
        An AndExpr (may have zero children if user adds nothing).
    """
    return _build_group(columns, "and", header_fn)
