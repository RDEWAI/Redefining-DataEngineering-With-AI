# Excel (xlsx) Skill

This skill enables Claude Code to create, read, and modify Excel workbooks using the `openpyxl` Python library.

## Key Patterns

### Creating a Workbook
```python
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

wb = openpyxl.Workbook()
ws = wb.active
ws.title = "Sheet1"

# Add headers with formatting
headers = ["Column A", "Column B", "Column C"]
header_font = Font(bold=True)
header_fill = PatternFill(start_color="D6EAF8", end_color="D6EAF8", fill_type="solid")

for col, header in enumerate(headers, 1):
    cell = ws.cell(row=1, column=col, value=header)
    cell.font = header_font
    cell.fill = header_fill

# Freeze top row
ws.freeze_panes = "A2"

# Auto-filter
ws.auto_filter.ref = ws.dimensions

# Column widths
for col in range(1, len(headers) + 1):
    ws.column_dimensions[get_column_letter(col)].width = 20

wb.save("output.xlsx")
```

### Reading a Workbook
```python
wb = openpyxl.load_workbook("input.xlsx")
ws = wb["Sheet1"]
for row in ws.iter_rows(min_row=2, values_only=True):
    print(row)
```

### Modifying a Workbook
```python
wb = openpyxl.load_workbook("input.xlsx")
ws = wb["Sheet1"]
ws.cell(row=2, column=3, value="new value")
wb.save("output.xlsx")
```

## Best Practices

- Always use `openpyxl` (not xlsxwriter) for read/write compatibility
- Freeze the header row for usability
- Enable auto-filter on data sheets
- Use PatternFill for header backgrounds
- Set reasonable column widths (15-30 characters)
- Use Font(bold=True) for headers
- Save with `.xlsx` extension
