# csv-me

Python CLI tool for CSV cleaning and transformation using `rich` and `pandas`.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Run via `csv-me <file.csv>` or `python -m csv_me <file.csv>`.
Pass a previous output folder to resume a session.

## Architecture

Session-based design: the original CSV is never modified. Each transformation saves a new numbered step file into an output directory alongside a JSON manifest (`.csv_me_session.json`) and a transformation log.

### Project structure

```
csv_me/
├── __init__.py          # Version string
├── __main__.py          # python -m csv_me entry point
├── cli.py               # Main CLI entry, feature registry, main menu loop
├── session.py           # Session class: output dir, file chain, manifest, read/save
├── menu.py              # Shared TUI helpers: show_menu, pick_columns, preview_df, clear_screen
├── logger.py            # TransformationLogger: appends timestamped entries to log file
└── features/
    ├── __init__.py
    ├── normalize_cols.py      # Case & whitespace transforms on column values
    ├── normalize_phones.py    # Phone number formatting (digits, parens, dashes, E.164)
    ├── normalize_currency.py  # Strip symbols, round, convert to plain numbers
    ├── remove_duplicates.py   # Remove exact or column-based duplicates
    ├── remove_columns.py      # Delete selected columns
    ├── split_column.py        # Split one column into multiple by separator
    ├── join_csvs.py           # Combine multiple CSVs with union of columns
    └── split_join_rows.py     # Advanced row transformation with conditional mappings
```

### Key modules

- **`cli.py`** — Entry point (`main()`), feature registry (`FEATURES` list of `(label, handler)` tuples), main menu loop. Features are lazy-imported in `_register_features()`.
- **`session.py`** — `Session` class: creates timestamped output dir, copies original as `00_original_*.csv`, manages step numbering, persists state to `.csv_me_session.json` manifest. Key methods: `read_current()`, `save_step(df, label)`, `from_output_dir(path)`.
- **`menu.py`** — Shared TUI functions using Rich: `show_menu()`, `pick_columns()`, `preview_df()`, `show_status()`, `clear_screen()`.
- **`logger.py`** — `TransformationLogger`: appends to `transformation_log.txt` with timestamps and action details.

### Adding a new feature

1. Create `csv_me/features/<name>.py` with a `run(session: Session)` function
2. Import it in `cli.py:_register_features()` and append a `(label, handler)` tuple to `FEATURES`

The `run` function should own its own sub-menu loop, use `session.read_current()` to get the working DataFrame, `session.save_step(df, label)` to persist changes, and `session.logger.log(action, details)` to record what happened.

### Session workflow

1. User provides a CSV path (or an existing output dir to resume)
2. Output directory created next to original: `{stem}_csv_me_{timestamp}/`
3. Original copied as `00_original_{name}.csv`; manifest and log initialized
4. Each transformation increments the step counter and saves `{NN}_{label}.csv`
5. Manifest (`.csv_me_session.json`) updated after every step with history, paths, timestamps
6. On quit, completion panel shows the output directory path

## Conventions

- Python 3.10+, type hints throughout
- Build backend: `setuptools.build_meta`
- Dependencies: `rich>=13.0`, `pandas>=2.0`
- No tests yet — be careful with refactors
- Keep features self-contained in their own module
- Use `rich` for all terminal output (no bare `print`)
- Column selection UI pattern: show numbered list, user enters indices
- Always preview data and confirm before saving a step
