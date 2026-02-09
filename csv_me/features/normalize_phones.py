"""Normalize phone numbers: strip chars, standardize formats."""

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


def _digits(value: str) -> str:
    return re.sub(r"\D", "", value)


def _format_parens(value: str) -> str:
    digits = _digits(value)
    # Strip leading 1 for US numbers
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    return value  # can't format, leave as-is


def _format_dashes(value: str) -> str:
    digits = _digits(value)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) == 10:
        return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
    return value


def _format_e164(value: str) -> str:
    digits = _digits(value)
    if len(digits) == 11 and digits.startswith("1"):
        return f"+{digits}"
    if len(digits) == 10:
        return f"+1{digits}"
    return value


FORMATTERS = [_digits, _format_parens, _format_dashes, _format_e164]
LABELS = ["digits_only", "parens", "dashes", "e164"]


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
        for col in columns:
            if col not in df.columns:
                continue
            original = df[col].astype(str).copy()
            df[col] = df[col].astype(str).apply(
                lambda v: formatter(v) if v and v != "nan" else v
            )
            changed += (original != df[col].astype(str)).sum()

        step_label = f"normalize_phones_{mode_label}"
        out = session.save_step(df, step_label)
        session.logger.log(
            f"Normalize Phones — {label}",
            f"Columns: {columns} | Cells changed: {changed} | Saved: {out.name}",
        )

        console.print(
            f"\n[green]Done![/green] {changed} cell(s) changed across "
            f"{len(columns)} column(s). Saved as [bold]{out.name}[/bold]\n"
        )
        console.input("[dim]Press Enter to continue...[/dim]")
