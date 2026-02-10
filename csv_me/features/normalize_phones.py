"""Normalize phone numbers: strip chars, validate, standardize formats."""

from __future__ import annotations

import re

import pandas as pd

from csv_me.menu import clear_screen, console, pick_columns, show_menu, show_status
from csv_me.session import Session

OPTIONS = [
    "Digits Only (remove all non-digit characters)",
    "Format as (XXX) XXX-XXXX",
    "Format as XXX-XXX-XXXX",
    "Format as +1XXXXXXXXXX (E.164)",
]

LABELS = ["digits_only", "parens", "dashes", "e164"]


def _clean(value: str) -> str:
    """Remove parentheses, hyphens, and whitespace only."""
    return re.sub(r"[()\-\s]", "", value)


def _format_digits(digits: str) -> str:
    return digits


def _format_parens(digits: str) -> str:
    return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"


def _format_dashes(digits: str) -> str:
    return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"


def _format_e164(digits: str) -> str:
    return f"+1{digits}"


FORMATTERS = [_format_digits, _format_parens, _format_dashes, _format_e164]


def _normalize(value: str, formatter) -> tuple[str, bool]:
    """Normalize a single phone value.

    Returns (result, errored) where errored is True if the value
    could not be normalized and was left as the original.
    """
    if not isinstance(value, str):
        return value, False

    if not value or value.lower() == "nan" or value.strip() == "":
        return value, False

    # Pandas stores columns with NaN as float, so 5551234567 becomes
    # "5551234567.0" after astype(str). Strip the spurious decimal.
    if re.fullmatch(r"\d+\.0", value):
        value = value[:-2]

    cleaned = _clean(value)

    if not cleaned:
        return value, False

    if not cleaned.isdigit():
        return value, True

    digits = cleaned
    # Strip leading country code 1 for US numbers
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]

    if len(digits) < 10:
        return value, True

    return formatter(digits), False


def run(session: Session) -> None:
    while True:
        clear_screen()
        show_status(session.current_filename)

        choice = show_menu("Normalize Phone Numbers", OPTIONS)
        if choice == 0:
            return

        formatter = FORMATTERS[choice - 1]
        label = OPTIONS[choice - 1]
        mode_label = LABELS[choice - 1]

        df = session.read_current()
        columns = pick_columns(df, prompt_text=f"Apply '{label}' to")

        changed = 0
        errors = 0
        for col in columns:
            if col not in df.columns:
                continue
            original = df[col].copy()
            results = df[col].astype(str).apply(lambda v: _normalize(v, formatter))
            df[col] = results.apply(lambda r: r[0])
            col_errors = results.apply(lambda r: r[1]).sum()
            errors += col_errors
            changed += (original.astype(str) != df[col].astype(str)).sum()

        step_label = f"normalize_phones_{mode_label}"
        out = session.save_step(df, step_label)

        details = (
            f"Columns: {columns} | Cells changed: {changed} | "
            f"Errors (left as original): {errors} | Saved: {out.name}"
        )
        session.logger.log(f"Normalize Phones — {label}", details)

        console.print(
            f"\n[green]Done![/green] {changed} cell(s) changed across "
            f"{len(columns)} column(s). Saved as [bold]{out.name}[/bold]"
        )
        if errors:
            console.print(
                f"[yellow]{errors} cell(s) could not be normalized "
                f"(non-digits after cleaning or fewer than 10 digits) "
                f"and were left unchanged.[/yellow]"
            )
        console.print()
        console.input("[dim]Press Enter to continue...[/dim]")
