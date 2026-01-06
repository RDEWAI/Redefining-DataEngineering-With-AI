"""CSV viewer component with table display and gridlines.

This module provides a NiceGUI component that renders CSV content
as a proper table with sorting, filtering, and pagination.
"""

from __future__ import annotations

import csv
import io
from typing import Any

from nicegui import ui


class CSVViewer:
    """A CSV viewer component with table display and gridlines.

    This component:
    - Parses CSV content and displays as a proper table
    - Supports sorting and pagination
    - Shows gridlines for better readability
    - Handles large datasets efficiently
    """

    def __init__(
        self,
        content: str,
        max_height: str = "500px",
        rows_per_page: int = 25,
    ) -> None:
        """Initialize the CSV viewer.

        Args:
            content: CSV content string to display.
            max_height: Maximum height of the viewer (CSS value).
            rows_per_page: Number of rows to show per page.
        """
        self.content = content
        self.max_height = max_height
        self.rows_per_page = rows_per_page
        self._container: ui.element | None = None

    def _parse_csv(self) -> tuple[list[str], list[dict[str, str]]]:
        """Parse CSV content into headers and rows.

        Returns:
            Tuple of (headers list, rows as list of dicts).
        """
        reader = csv.reader(io.StringIO(self.content))
        rows_list = list(reader)

        if not rows_list:
            return [], []

        headers = rows_list[0]
        data_rows = []

        for row in rows_list[1:]:
            if row:  # Skip empty rows
                row_dict = {}
                for i, header in enumerate(headers):
                    row_dict[header] = row[i] if i < len(row) else ""
                data_rows.append(row_dict)

        return headers, data_rows

    def render(self) -> ui.element:
        """Render the CSV viewer component.

        Returns:
            The container element.
        """
        headers, rows = self._parse_csv()

        with ui.column().classes("w-full") as container:
            self._container = container

            if not headers:
                ui.label("No data to display").classes("text-grey")
                return container

            # Stats row
            with ui.row().classes("w-full items-center gap-4 mb-2"):
                ui.label(f"{len(rows)} rows x {len(headers)} columns").classes(
                    "text-grey text-sm"
                )

            # Build columns for table
            columns: list[dict[str, Any]] = []
            for header in headers:
                col: dict[str, Any] = {
                    "name": header,
                    "label": header,
                    "field": header,
                    "sortable": True,
                    "align": "left",
                }
                columns.append(col)

            # Create table with styling - use virtual scroll for sticky header
            table = ui.table(
                columns=columns,
                rows=rows,
                row_key=headers[0] if headers else "id",
                pagination={"rowsPerPage": self.rows_per_page},
            ).classes("w-full csv-table sticky-header-table")

            # Add custom styling for gridlines and sticky header
            # Use height for calc() values to fill space
            height_style = (
                f"height: {self.max_height};"
                if "calc" in self.max_height or "vh" in self.max_height
                else f"max-height: {self.max_height};"
            )
            table.style(f"{height_style} overflow: auto;")

            # Add CSS for better table appearance with sticky header
            ui.add_head_html("""
            <style>
                .csv-table .q-table__container {
                    max-height: inherit;
                }
                .csv-table .q-table__middle {
                    max-height: inherit;
                    overflow: auto;
                }
                .csv-table table {
                    border-collapse: collapse;
                }
                /* Sticky header styles */
                .sticky-header-table thead tr th {
                    position: sticky;
                    top: 0;
                    z-index: 1;
                    background-color: #f5f5f5 !important;
                }
                .csv-table th {
                    background-color: #f5f5f5 !important;
                    font-weight: 600 !important;
                    border: 1px solid #e0e0e0 !important;
                    white-space: nowrap;
                    padding: 10px 12px !important;
                }
                .csv-table td {
                    border: 1px solid #e0e0e0 !important;
                    font-family: monospace;
                    font-size: 12px;
                    max-width: 300px;
                    overflow: hidden;
                    text-overflow: ellipsis;
                    white-space: nowrap;
                    padding: 8px 12px !important;
                }
                .csv-table tr:nth-child(even) td {
                    background-color: #fafafa;
                }
                .csv-table tbody tr:hover td {
                    background-color: #e3f2fd !important;
                }
            </style>
            """)

        return container

    def update_content(self, content: str) -> None:
        """Update the displayed content.

        Args:
            content: New CSV content.
        """
        self.content = content
        if self._container is not None:
            self._container.clear()
            with self._container:
                self.render()


def csv_table(
    content: str,
    max_height: str = "500px",
    rows_per_page: int = 25,
) -> CSVViewer:
    """Create and render a CSV table viewer.

    Args:
        content: CSV content to display.
        max_height: Maximum height of the viewer.
        rows_per_page: Rows per page for pagination.

    Returns:
        The CSVViewer instance.
    """
    viewer = CSVViewer(
        content=content,
        max_height=max_height,
        rows_per_page=rows_per_page,
    )
    viewer.render()
    return viewer
