"""Session manager: tracks current file, output folder, and transformation chain."""

from __future__ import annotations

import os
import shutil
from datetime import datetime
from pathlib import Path

import pandas as pd

from csv_me.logger import TransformationLogger


class Session:
    """Manages the working session for CSV transformations."""

    def __init__(self, input_path: str) -> None:
        self.original_path = Path(input_path).resolve()
        if not self.original_path.exists():
            raise FileNotFoundError(f"File not found: {self.original_path}")
        if self.original_path.suffix.lower() != ".csv":
            raise ValueError(f"Not a CSV file: {self.original_path}")

        self.output_dir = self._create_output_dir()
        self.logger = TransformationLogger(self.output_dir)
        self.step = 0
        self.history: list[Path] = []

        # Copy original into the output folder as step 0
        initial_copy = self.output_dir / f"00_original_{self.original_path.name}"
        shutil.copy2(self.original_path, initial_copy)
        self.current_file = initial_copy
        self.history.append(initial_copy)
        self.logger.log("Session started", f"Loaded {self.original_path.name}")

    def _create_output_dir(self) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        stem = self.original_path.stem
        output_dir = self.original_path.parent / f"{stem}_csv_me_{timestamp}"
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir

    def read_current(self) -> pd.DataFrame:
        """Read the current working CSV into a DataFrame."""
        return pd.read_csv(self.current_file)

    def save_step(self, df: pd.DataFrame, label: str) -> Path:
        """Save a new step in the transformation chain.

        Args:
            df: The transformed DataFrame.
            label: Short description used in the filename (e.g. 'normalize_cols_lowercase').

        Returns:
            Path to the newly saved file.
        """
        self.step += 1
        safe_label = label.replace(" ", "_").lower()
        filename = f"{self.step:02d}_{safe_label}.csv"
        out_path = self.output_dir / filename
        df.to_csv(out_path, index=False)
        self.current_file = out_path
        self.history.append(out_path)
        return out_path

    @property
    def current_filename(self) -> str:
        return self.current_file.name
