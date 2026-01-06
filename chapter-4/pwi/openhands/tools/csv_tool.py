"""CSV analysis tools for PWI OpenHands agents.

This module provides tools for analyzing CSV files:
- analyze_csv: Analyze CSV structure, columns, and data types
- csv_stats: Get statistics about CSV file content
- csv_sample: Get sample rows from a CSV file
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from pwi.openhands.tools.base import create_tool, register_tool
from pwi.utils.logging import get_logger

logger = get_logger("openhands.tools.csv")


# =============================================================================
# Tool Definitions
# =============================================================================

AnalyzeCSVTool = create_tool(
    name="analyze_csv",
    description="Analyze a CSV file to get its structure, columns, data types, and sample data",
    parameters={
        "file_path": {
            "type": "string",
            "description": "Path to the CSV file",
        },
        "sample_rows": {
            "type": "integer",
            "description": "Number of sample rows to include (default: 5)",
        },
        "infer_types": {
            "type": "boolean",
            "description": "Whether to infer data types (default: true)",
        },
    },
    required=["file_path"],
)

CSVStatsTool = create_tool(
    name="csv_stats",
    description="Get statistics about a CSV file: row count, null counts, unique values",
    parameters={
        "file_path": {
            "type": "string",
            "description": "Path to the CSV file",
        },
        "columns": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Specific columns to analyze (analyzes all if not specified)",
        },
    },
    required=["file_path"],
)

CSVSampleTool = create_tool(
    name="csv_sample",
    description="Get sample rows from a CSV file",
    parameters={
        "file_path": {
            "type": "string",
            "description": "Path to the CSV file",
        },
        "num_rows": {
            "type": "integer",
            "description": "Number of rows to sample (default: 10)",
        },
        "columns": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Specific columns to include",
        },
    },
    required=["file_path"],
)


# =============================================================================
# Tool Executors
# =============================================================================

def _infer_type(value: str) -> str:
    """Infer the data type of a string value.

    Args:
        value: String value to analyze.

    Returns:
        Inferred type name.
    """
    if not value or value.lower() in ("", "null", "none", "na", "n/a"):
        return "null"

    # Try integer
    try:
        int(value)
        return "integer"
    except ValueError:
        pass

    # Try float
    try:
        float(value)
        return "float"
    except ValueError:
        pass

    # Check for boolean
    if value.lower() in ("true", "false", "yes", "no", "1", "0"):
        return "boolean"

    # Check for date patterns
    import re
    date_patterns = [
        r"^\d{4}-\d{2}-\d{2}$",  # YYYY-MM-DD
        r"^\d{2}/\d{2}/\d{4}$",  # MM/DD/YYYY
        r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}",  # ISO datetime
    ]
    for pattern in date_patterns:
        if re.match(pattern, value):
            return "datetime" if "T" in value else "date"

    return "string"


def _get_column_types(rows: list[list[str]], headers: list[str]) -> dict[str, str]:
    """Infer column types from sample data.

    Args:
        rows: Sample data rows.
        headers: Column headers.

    Returns:
        Dictionary mapping column names to inferred types.
    """
    type_counts: dict[str, dict[str, int]] = {h: {} for h in headers}

    for row in rows:
        for i, value in enumerate(row):
            if i < len(headers):
                col = headers[i]
                inferred = _infer_type(value)
                type_counts[col][inferred] = type_counts[col].get(inferred, 0) + 1

    # Pick the most common non-null type for each column
    result = {}
    for col, counts in type_counts.items():
        # Remove null counts for type determination
        non_null_counts = {k: v for k, v in counts.items() if k != "null"}
        if non_null_counts:
            result[col] = max(non_null_counts, key=non_null_counts.get)
        else:
            result[col] = "string"

    return result


def execute_analyze_csv(
    file_path: str,
    sample_rows: int = 5,
    infer_types: bool = True,
) -> dict[str, Any]:
    """Analyze a CSV file structure.

    Args:
        file_path: Path to CSV file.
        sample_rows: Number of sample rows.
        infer_types: Whether to infer data types.

    Returns:
        Analysis results dictionary.
    """
    try:
        path = Path(file_path)
        if not path.exists():
            return {
                "success": False,
                "error": f"File not found: {file_path}",
            }

        with open(path, newline="", encoding="utf-8") as f:
            # Detect delimiter
            sample = f.read(8192)
            f.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample)
            except csv.Error:
                dialect = csv.excel

            reader = csv.reader(f, dialect)
            headers = next(reader)

            # Read sample rows
            rows = []
            for i, row in enumerate(reader):
                if i >= sample_rows:
                    break
                rows.append(row)

            # Count total rows (read rest of file)
            total_rows = len(rows)
            for _ in reader:
                total_rows += 1

        # Infer types if requested
        column_types = {}
        if infer_types and rows:
            column_types = _get_column_types(rows, headers)

        # Build column info
        columns = []
        for i, header in enumerate(headers):
            col_info = {
                "index": i,
                "name": header,
            }
            if infer_types:
                col_info["inferred_type"] = column_types.get(header, "string")
            columns.append(col_info)

        logger.info(f"Analyzed CSV: {path.name}, {len(headers)} columns, {total_rows} rows")

        return {
            "success": True,
            "file_path": str(path),
            "file_name": path.name,
            "columns": columns,
            "column_count": len(headers),
            "row_count": total_rows,
            "sample_data": rows,
            "headers": headers,
        }

    except Exception as e:
        logger.error(f"CSV analysis failed: {e}")
        return {
            "success": False,
            "error": str(e),
        }


def execute_csv_stats(
    file_path: str,
    columns: list[str] | None = None,
) -> dict[str, Any]:
    """Get statistics about a CSV file.

    Args:
        file_path: Path to CSV file.
        columns: Specific columns to analyze.

    Returns:
        Statistics dictionary.
    """
    try:
        path = Path(file_path)
        if not path.exists():
            return {
                "success": False,
                "error": f"File not found: {file_path}",
            }

        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames or []

            # Filter columns if specified
            analyze_cols = columns if columns else headers

            # Initialize stats
            stats: dict[str, dict[str, Any]] = {}
            for col in analyze_cols:
                if col in headers:
                    stats[col] = {
                        "null_count": 0,
                        "non_null_count": 0,
                        "unique_values": set(),
                    }

            row_count = 0
            for row in reader:
                row_count += 1
                for col in analyze_cols:
                    if col in row:
                        value = row[col]
                        if not value or value.lower() in ("", "null", "none", "na"):
                            stats[col]["null_count"] += 1
                        else:
                            stats[col]["non_null_count"] += 1
                            # Only track unique values up to a limit
                            if len(stats[col]["unique_values"]) < 1000:
                                stats[col]["unique_values"].add(value)

        # Convert sets to counts
        result_stats = {}
        for col, col_stats in stats.items():
            result_stats[col] = {
                "null_count": col_stats["null_count"],
                "non_null_count": col_stats["non_null_count"],
                "null_percentage": round(
                    col_stats["null_count"] / row_count * 100, 2
                ) if row_count > 0 else 0,
                "unique_count": len(col_stats["unique_values"]),
                "unique_limited": len(col_stats["unique_values"]) >= 1000,
            }

        logger.info(f"CSV stats computed for {path.name}")

        return {
            "success": True,
            "file_path": str(path),
            "row_count": row_count,
            "column_stats": result_stats,
        }

    except Exception as e:
        logger.error(f"CSV stats failed: {e}")
        return {
            "success": False,
            "error": str(e),
        }


def execute_csv_sample(
    file_path: str,
    num_rows: int = 10,
    columns: list[str] | None = None,
) -> dict[str, Any]:
    """Get sample rows from a CSV file.

    Args:
        file_path: Path to CSV file.
        num_rows: Number of rows to sample.
        columns: Specific columns to include.

    Returns:
        Sample data dictionary.
    """
    try:
        path = Path(file_path)
        if not path.exists():
            return {
                "success": False,
                "error": f"File not found: {file_path}",
            }

        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames or []

            # Filter columns
            include_cols = columns if columns else headers

            rows = []
            for i, row in enumerate(reader):
                if i >= num_rows:
                    break
                filtered_row = {k: row.get(k, "") for k in include_cols if k in headers}
                rows.append(filtered_row)

        logger.info(f"Sampled {len(rows)} rows from {path.name}")

        return {
            "success": True,
            "file_path": str(path),
            "columns": include_cols,
            "rows": rows,
            "row_count": len(rows),
        }

    except Exception as e:
        logger.error(f"CSV sample failed: {e}")
        return {
            "success": False,
            "error": str(e),
        }


# =============================================================================
# Register Tools
# =============================================================================

def register_csv_tools() -> None:
    """Register all CSV tools with the global registry."""
    register_tool(AnalyzeCSVTool, execute_analyze_csv)
    register_tool(CSVStatsTool, execute_csv_stats)
    register_tool(CSVSampleTool, execute_csv_sample)
    logger.info("CSV tools registered")


# Auto-register on import
register_csv_tools()
