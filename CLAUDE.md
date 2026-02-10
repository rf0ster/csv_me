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

### Key modules

- `cli.py` — Entry point, feature registry (`FEATURES` list), main menu loop
- `session.py` — `Session` class: manages output dir, file chain, manifest, read/save
- `menu.py` — Shared TUI helpers: `show_menu`, `pick_columns`, `preview_df`, `clear_screen`
- `logger.py` — `TransformationLogger`: appends to the transformation log file
- `features/` — One module per feature, each exports a `run(session: Session)` function

### Adding a new feature

1. Create `csv_me/features/<name>.py` with a `run(session: Session)` function
2. Import it in `cli.py:_register_features()` and append a `(label, handler)` tuple to `FEATURES`

The `run` function should own its own sub-menu loop, use `session.read_current()` to get the working DataFrame, `session.save_step(df, label)` to persist changes, and `session.logger.log(action, details)` to record what happened.

## Conventions

- Python 3.10+, type hints throughout
- Build backend: `setuptools.build_meta`
- Dependencies: `rich>=13.0`, `pandas>=2.0`
- No tests yet — be careful with refactors
- Keep features self-contained in their own module
- Use `rich` for all terminal output (no bare `print`)
