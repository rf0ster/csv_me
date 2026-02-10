"""Session manager: tracks current file, output folder, and transformation chain."""

from __future__ import annotations

import json
import os
import shutil
from datetime import datetime
from pathlib import Path

import pandas as pd

from csv_me import __version__
from csv_me.logger import TransformationLogger


class Session:
    """Manages the working session for CSV transformations."""

    MANIFEST_NAME = ".csv_me_session.json"

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
        self._write_manifest()

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
        self._write_manifest()
        return out_path

    @property
    def current_filename(self) -> str:
        return self.current_file.name

    def _write_manifest(self) -> None:
        """Write session state to a JSON manifest in the output directory."""
        manifest = {
            "csv_me_version": __version__,
            "original_path": str(self.original_path),
            "original_filename": self.original_path.name,
            "created_at": self.history[0].stat().st_mtime
            if self.history
            else datetime.now().isoformat(),
            "last_updated_at": datetime.now().isoformat(),
            "step": self.step,
            "current_file": self.current_file.name,
            "history": [p.name for p in self.history],
        }
        manifest_path = self.output_dir / self.MANIFEST_NAME
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2, default=str)

    @staticmethod
    def is_csv_me_output_dir(path: str) -> bool:
        """Return True if path is a directory containing a csv-me manifest."""
        p = Path(path).resolve()
        return p.is_dir() and (p / Session.MANIFEST_NAME).is_file()

    @classmethod
    def from_output_dir(cls, path: str) -> "Session":
        """Resume a session from an existing output directory.

        Reads the manifest, validates the current file exists, and
        reconstructs a Session without running __init__.
        """
        output_dir = Path(path).resolve()
        manifest_path = output_dir / cls.MANIFEST_NAME

        with open(manifest_path) as f:
            manifest = json.load(f)

        for key in ("original_path", "step", "current_file", "history"):
            if key not in manifest:
                raise ValueError(
                    f"Invalid session manifest: missing required key '{key}'"
                )

        current_file = output_dir / manifest["current_file"]
        if not current_file.exists():
            raise ValueError(
                f"Current working file not found: {current_file}"
            )

        session = cls.__new__(cls)
        session.original_path = Path(manifest["original_path"])
        session.output_dir = output_dir
        session.step = manifest["step"]
        session.current_file = current_file
        session.history = [output_dir / name for name in manifest["history"]]
        session.logger = TransformationLogger(output_dir, append=True)
        session.logger.log(
            "Session resumed",
            f"Resumed at step {session.step} — {session.current_file.name}",
        )
        return session
