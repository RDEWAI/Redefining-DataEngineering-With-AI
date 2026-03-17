#!/usr/bin/env python3
"""LibreOffice soffice interface for Excel operations."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def find_soffice() -> str | None:
    """Locate the soffice binary."""
    candidates = [
        "/Applications/LibreOffice.app/Contents/MacOS/soffice",
        "/usr/bin/soffice",
        "/usr/local/bin/soffice",
        shutil.which("soffice"),
    ]
    for c in candidates:
        if c and Path(c).exists():
            return c
    return None


def is_available() -> bool:
    """Check if LibreOffice is available."""
    return find_soffice() is not None


def convert(input_path: str, output_format: str = "xlsx", output_dir: str | None = None) -> str:
    """Convert a file using LibreOffice."""
    soffice = find_soffice()
    if not soffice:
        raise RuntimeError("LibreOffice not found")

    out_dir = output_dir or str(Path(input_path).parent)
    cmd = [
        soffice,
        "--headless",
        "--convert-to",
        output_format,
        "--outdir",
        out_dir,
        input_path,
    ]
    subprocess.run(cmd, check=True, capture_output=True)

    stem = Path(input_path).stem
    return str(Path(out_dir) / f"{stem}.{output_format}")
