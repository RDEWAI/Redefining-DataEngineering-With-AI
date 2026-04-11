#!/usr/bin/env python3
"""Recalculate Excel formulas using LibreOffice.

Usage: python recalc.py <input.xlsx> [output.xlsx]

Requires LibreOffice to be installed.
If output is not specified, overwrites the input file.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


def find_soffice() -> str | None:
    """Find LibreOffice soffice binary."""
    candidates = [
        "/Applications/LibreOffice.app/Contents/MacOS/soffice",
        "/usr/bin/soffice",
        "/usr/local/bin/soffice",
        shutil.which("soffice"),
    ]
    for path in candidates:
        if path and Path(path).exists():
            return path
    return None


def recalc(input_path: str, output_path: str | None = None):
    """Recalculate formulas in an Excel file."""
    soffice = find_soffice()
    if not soffice:
        print("ERROR: LibreOffice not found. Install with: brew install --cask libreoffice")
        sys.exit(1)

    input_file = Path(input_path)
    if not input_file.exists():
        print(f"ERROR: File not found: {input_path}")
        sys.exit(1)

    cmd = [
        soffice,
        "--headless",
        "--calc",
        "--convert-to",
        "xlsx",
        "--outdir",
        str(input_file.parent),
        str(input_file),
    ]
    subprocess.run(cmd, check=True, capture_output=True)

    if output_path and output_path != input_path:
        shutil.move(str(input_file), output_path)

    print(f"Recalculated: {output_path or input_path}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    recalc(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
