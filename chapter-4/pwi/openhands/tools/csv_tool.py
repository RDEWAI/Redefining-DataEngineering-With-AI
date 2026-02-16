"""CSV analysis tools for PWI OpenHands agents using SDK pattern.

This module provides tools for analyzing CSV files:
- analyze_csv: Analyze CSV structure, columns, and data types
- csv_stats: Get statistics about CSV file content
- csv_sample: Get sample rows from a CSV file

Usage:
    from pwi.openhands.tools.csv_tool import AnalyzeCSVTool
    # Tools are auto-registered on import
"""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any

from pydantic import Field

from openhands.sdk import Action, Observation
from openhands.sdk.tool import ToolDefinition, ToolExecutor, register_tool

from pwi.utils.logging import get_logger

logger = get_logger("openhands.tools.csv")


# =============================================================================
# Analyze CSV Tool
# =============================================================================


class AnalyzeCSVAction(Action):
    """Schema for CSV analysis action."""

    file_path: str = Field(description="Path to the CSV file to analyze")
    sample_rows: int = Field(default=5, description="Number of sample rows to include")
    infer_types: bool = Field(default=True, description="Whether to infer data types")


class AnalyzeCSVObservation(Observation):
    """Schema for CSV analysis result."""

    success: bool = Field(default=True)
    file_path: str = Field(default="")
    file_name: str = Field(default="")
    columns: list[dict[str, Any]] = Field(default_factory=list)
    column_count: int = Field(default=0)
    row_count: int = Field(default=0)
    sample_data: list[list[str]] = Field(default_factory=list)
    headers: list[str] = Field(default_factory=list)
    error: str | None = Field(default=None)


class AnalyzeCSVExecutor(ToolExecutor[AnalyzeCSVAction, AnalyzeCSVObservation]):
    """Executor for CSV analysis."""

    def _infer_type(self, value: str) -> str:
        """Infer the data type of a string value."""
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
        date_patterns = [
            r"^\d{4}-\d{2}-\d{2}$",  # YYYY-MM-DD
            r"^\d{2}/\d{2}/\d{4}$",  # MM/DD/YYYY
            r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}",  # ISO datetime
        ]
        for pattern in date_patterns:
            if re.match(pattern, value):
                return "datetime" if "T" in value else "date"

        return "string"

    def _get_column_types(
        self, rows: list[list[str]], headers: list[str]
    ) -> dict[str, str]:
        """Infer column types from sample data."""
        type_counts: dict[str, dict[str, int]] = {h: {} for h in headers}

        for row in rows:
            for i, value in enumerate(row):
                if i < len(headers):
                    col = headers[i]
                    inferred = self._infer_type(value)
                    type_counts[col][inferred] = type_counts[col].get(inferred, 0) + 1

        # Pick the most common non-null type for each column
        result = {}
        for col, counts in type_counts.items():
            non_null_counts = {k: v for k, v in counts.items() if k != "null"}
            if non_null_counts:
                result[col] = max(non_null_counts, key=non_null_counts.get)
            else:
                result[col] = "string"

        return result

    def __call__(
        self, action: AnalyzeCSVAction, conversation: Any = None
    ) -> AnalyzeCSVObservation:
        """Execute CSV analysis."""
        try:
            path = Path(action.file_path)
            if not path.exists():
                return AnalyzeCSVObservation(
                    success=False, error=f"File not found: {action.file_path}"
                )

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
                    if i >= action.sample_rows:
                        break
                    rows.append(row)

                # Count total rows
                total_rows = len(rows)
                for _ in reader:
                    total_rows += 1

            # Infer types if requested
            column_types = {}
            if action.infer_types and rows:
                column_types = self._get_column_types(rows, headers)

            # Build column info
            columns = []
            for i, header in enumerate(headers):
                col_info: dict[str, Any] = {"index": i, "name": header}
                if action.infer_types:
                    col_info["inferred_type"] = column_types.get(header, "string")
                columns.append(col_info)

            logger.info(
                f"Analyzed CSV: {path.name}, {len(headers)} columns, {total_rows} rows"
            )

            return AnalyzeCSVObservation(
                success=True,
                file_path=str(path),
                file_name=path.name,
                columns=columns,
                column_count=len(headers),
                row_count=total_rows,
                sample_data=rows,
                headers=headers,
            )

        except Exception as e:
            logger.error(f"CSV analysis failed: {e}")
            return AnalyzeCSVObservation(success=False, error=str(e))


class AnalyzeCSVTool(ToolDefinition[AnalyzeCSVAction, AnalyzeCSVObservation]):
    """Tool definition for CSV analysis."""

    name = "analyze_csv"

    @classmethod
    def create(cls, conv_state: Any = None, **kwargs: Any) -> list[ToolDefinition]:
        """Create the tool instance."""
        return [
            cls(
                action_type=AnalyzeCSVAction,
                observation_type=AnalyzeCSVObservation,
                description="Analyze a CSV file to get its structure, columns, data types, and sample data",
                executor=AnalyzeCSVExecutor(),
            )
        ]


# =============================================================================
# CSV Stats Tool
# =============================================================================


class CSVStatsAction(Action):
    """Schema for CSV statistics action."""

    file_path: str = Field(description="Path to the CSV file")
    columns: list[str] | None = Field(
        default=None, description="Specific columns to analyze (all if not specified)"
    )


class CSVStatsObservation(Observation):
    """Schema for CSV statistics result."""

    success: bool = Field(default=True)
    file_path: str = Field(default="")
    row_count: int = Field(default=0)
    column_stats: dict[str, dict[str, Any]] = Field(default_factory=dict)
    error: str | None = Field(default=None)


class CSVStatsExecutor(ToolExecutor[CSVStatsAction, CSVStatsObservation]):
    """Executor for CSV statistics."""

    def __call__(
        self, action: CSVStatsAction, conversation: Any = None
    ) -> CSVStatsObservation:
        """Execute CSV statistics computation."""
        try:
            path = Path(action.file_path)
            if not path.exists():
                return CSVStatsObservation(
                    success=False, error=f"File not found: {action.file_path}"
                )

            with open(path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                headers = reader.fieldnames or []

                # Filter columns if specified
                analyze_cols = action.columns if action.columns else headers

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
                    "null_percentage": (
                        round(col_stats["null_count"] / row_count * 100, 2)
                        if row_count > 0
                        else 0
                    ),
                    "unique_count": len(col_stats["unique_values"]),
                    "unique_limited": len(col_stats["unique_values"]) >= 1000,
                }

            logger.info(f"CSV stats computed for {path.name}")

            return CSVStatsObservation(
                success=True,
                file_path=str(path),
                row_count=row_count,
                column_stats=result_stats,
            )

        except Exception as e:
            logger.error(f"CSV stats failed: {e}")
            return CSVStatsObservation(success=False, error=str(e))


class CSVStatsTool(ToolDefinition[CSVStatsAction, CSVStatsObservation]):
    """Tool definition for CSV statistics."""

    name = "csv_stats"

    @classmethod
    def create(cls, conv_state: Any = None, **kwargs: Any) -> list[ToolDefinition]:
        """Create the tool instance."""
        return [
            cls(
                action_type=CSVStatsAction,
                observation_type=CSVStatsObservation,
                description="Get statistics about a CSV file: row count, null counts, unique values",
                executor=CSVStatsExecutor(),
            )
        ]


# =============================================================================
# CSV Sample Tool
# =============================================================================


class CSVSampleAction(Action):
    """Schema for CSV sample action."""

    file_path: str = Field(description="Path to the CSV file")
    num_rows: int = Field(default=10, description="Number of rows to sample")
    columns: list[str] | None = Field(
        default=None, description="Specific columns to include"
    )


class CSVSampleObservation(Observation):
    """Schema for CSV sample result."""

    success: bool = Field(default=True)
    file_path: str = Field(default="")
    columns: list[str] = Field(default_factory=list)
    rows: list[dict[str, str]] = Field(default_factory=list)
    row_count: int = Field(default=0)
    error: str | None = Field(default=None)


class CSVSampleExecutor(ToolExecutor[CSVSampleAction, CSVSampleObservation]):
    """Executor for CSV sampling."""

    def __call__(
        self, action: CSVSampleAction, conversation: Any = None
    ) -> CSVSampleObservation:
        """Execute CSV sampling."""
        try:
            path = Path(action.file_path)
            if not path.exists():
                return CSVSampleObservation(
                    success=False, error=f"File not found: {action.file_path}"
                )

            with open(path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                headers = reader.fieldnames or []

                # Filter columns
                include_cols = action.columns if action.columns else list(headers)

                rows = []
                for i, row in enumerate(reader):
                    if i >= action.num_rows:
                        break
                    filtered_row = {
                        k: row.get(k, "") for k in include_cols if k in headers
                    }
                    rows.append(filtered_row)

            logger.info(f"Sampled {len(rows)} rows from {path.name}")

            return CSVSampleObservation(
                success=True,
                file_path=str(path),
                columns=include_cols,
                rows=rows,
                row_count=len(rows),
            )

        except Exception as e:
            logger.error(f"CSV sample failed: {e}")
            return CSVSampleObservation(success=False, error=str(e))


class CSVSampleTool(ToolDefinition[CSVSampleAction, CSVSampleObservation]):
    """Tool definition for CSV sampling."""

    name = "csv_sample"

    @classmethod
    def create(cls, conv_state: Any = None, **kwargs: Any) -> list[ToolDefinition]:
        """Create the tool instance."""
        return [
            cls(
                action_type=CSVSampleAction,
                observation_type=CSVSampleObservation,
                description="Get sample rows from a CSV file",
                executor=CSVSampleExecutor(),
            )
        ]


# =============================================================================
# Register Tools with SDK
# =============================================================================


def _register_csv_tools() -> None:
    """Register all CSV tools with the OpenHands SDK registry."""
    register_tool("analyze_csv", AnalyzeCSVTool)
    register_tool("csv_stats", CSVStatsTool)
    register_tool("csv_sample", CSVSampleTool)
    logger.info("CSV tools registered with OpenHands SDK")


# Auto-register on import
_register_csv_tools()


__all__ = [
    "AnalyzeCSVAction",
    "AnalyzeCSVObservation",
    "AnalyzeCSVTool",
    "CSVStatsAction",
    "CSVStatsObservation",
    "CSVStatsTool",
    "CSVSampleAction",
    "CSVSampleObservation",
    "CSVSampleTool",
]
