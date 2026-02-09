"""Transformation logger: records every change with timestamps."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path


class TransformationLogger:
    """Appends transformation records to a log file in the output directory."""

    def __init__(self, output_dir: Path) -> None:
        self.log_path = output_dir / "transformation_log.txt"
        # Write header
        with open(self.log_path, "w") as f:
            f.write("=" * 60 + "\n")
            f.write("CSV-ME Transformation Log\n")
            f.write(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 60 + "\n\n")

    def log(self, action: str, details: str = "") -> None:
        """Append a log entry."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(self.log_path, "a") as f:
            f.write(f"[{timestamp}] {action}\n")
            if details:
                f.write(f"  {details}\n")
            f.write("\n")
