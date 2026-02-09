"""Normalize currency values: strip symbols, standardize format."""

from __future__ import annotations

import re

import pandas as pd

from csv_me.menu import clear_screen, console, pick_columns, show_menu, show_status
from csv_me.session import Session

OPTIONS = [
    "Remove Currency Symbols ($, EUR, etc.)",
    "Round to 2 Decimal Places",
    "Convert to Plain Number (strip commas & symbols)",
]


def _strip_symbols(value: str) -> str:
    """Remove common currency symbols/codes but keep digits, dots, commas, minus."""
    cleaned = re.sub(r"[^\d.,-]", "", value)
    return cleaned if cleaned else value


def _round_2(value: str) -> str:
    """Round numeric value to 2 decimal places."""
    cleaned = _strip_symbols(value).replace(",", "")
    try:
        return f"{float(cleaned):.2f}"
    except ValueError:
        return value


def _to_number(value: str) -> str:
    """Strip all formatting and return a plain number string."""
    cleaned = re.sub(r"[^\d.,-]", "", value)
    cleaned = cleaned.replace(",", "")
    try:
        return str(float(cleaned))
    except ValueError:
        return value


FORMATTERS = [_strip_symbols, _round_2, _to_number]
LABELS = ["strip_symbols", "round_2dp", "plain_number"]


def run(session: Session) -> None:
    while True:
        clear_screen()
        show_status(session.current_filename)

        choice = show_menu("Normalize Currency", OPTIONS)
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

        step_label = f"normalize_currency_{mode_label}"
        out = session.save_step(df, step_label)
        session.logger.log(
            f"Normalize Currency — {label}",
            f"Columns: {columns} | Cells changed: {changed} | Saved: {out.name}",
        )

        console.print(
            f"\n[green]Done![/green] {changed} cell(s) changed across "
            f"{len(columns)} column(s). Saved as [bold]{out.name}[/bold]\n"
        )
        console.input("[dim]Press Enter to continue...[/dim]")
