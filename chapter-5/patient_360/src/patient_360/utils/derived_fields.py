"""Derived field expressions for Bronze→Silver transformations.

Per STM Bronze→Silver mapping. These helpers wrap pyspark column
expressions so transform modules stay declarative.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    pass


def age_at(birthdate_col: str, reference_col: str = "current_date()") -> str:
    """Spark SQL expression: age in whole years between two dates."""
    return f"floor(months_between({reference_col}, {birthdate_col}) / 12)"


def coalesce_first(*column_exprs: str) -> str:
    """Spark SQL ``coalesce`` over the first non-null column expression."""
    if not column_exprs:
        raise ValueError("at least one column expression is required")
    return f"coalesce({', '.join(column_exprs)})"


def normalize_zip(zip_col: str) -> str:
    """Pad/truncate a US ZIP to 5 digits, stripping non-numerics."""
    return f"lpad(regexp_replace({zip_col}, '[^0-9]', ''), 5, '0')"


def trim_upper(col: str) -> str:
    """Trim whitespace and uppercase a string column."""
    return f"upper(trim({col}))"
