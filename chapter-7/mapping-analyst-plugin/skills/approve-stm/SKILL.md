---
name: approve-stm
description: >
  Approves a Source-to-Target Mapping (STM) workbook by setting its status to Approved.
  Reads the latest STM Excel file, verifies it is not already approved, updates the
  Status cell in the Summary sheet and adds a version history entry. This is the gate
  that enables downstream artifact creation (DQS, LLD, Stories).
  Use when the user asks to:
  - Approve an STM
  - Sign off on an STM
  - Mark an STM as approved or ready for handoff
argument-hint: "[stm-file-path]"
allowed-tools: Read, Edit, Glob, Bash
context: fork
---

# Approve Source-to-Target Mapping

You are a senior Mapping Analyst. Your task is to formally approve an STM
workbook, changing its status to `Approved` so that downstream artifact
creation (DQS, LLD, Stories) can proceed.

**Note**: STM is an Excel workbook (.xlsx), not markdown. Use Python/openpyxl
via Bash to read and update the Status field.

---

## Step 1: Locate the Latest STM

If the user specifies an STM path via `$ARGUMENTS`, use that file. Otherwise:

```bash
LATEST_STM_DIR=$(ls -d outputs/stm/v* | sort -V | tail -1)
LATEST_FILE=$(ls -t "$LATEST_STM_DIR"/STM-*.xlsx 2>/dev/null | grep -v '\.bak$' | head -1)
echo "Latest STM: $LATEST_FILE"
```

Read the Status from the Summary sheet:

```bash
uv run python -c "
import openpyxl
wb = openpyxl.load_workbook('$LATEST_FILE', read_only=True)
ws = wb['Summary']
for row in ws.iter_rows(min_row=1, max_col=2, values_only=True):
    if row[0] and str(row[0]).strip() == 'Status':
        print(f'Status: {row[1]}')
    if row[0] and str(row[0]).strip() == 'Version':
        print(f'Version: {row[1]}')
wb.close()
"
```

## Step 2: Pre-Checks

### 2a. Already Approved
If Status is already `Approved`:
- Inform the user: "This STM is already approved (version X.Y). No action needed."
- STOP. No changes.

### 2b. Draft Status Warning
If Status is `Draft`:
- Warn the user: "This STM has Status: Draft — it has never been through a review cycle. Consider running update-stm or validate-stm first."
- Present the warning and wait for confirmation:
  - If user confirms they want to approve anyway, proceed
  - If user wants to review first, STOP

### 2c. Validation Recommendation
Recommend running `/mapping-analyst-plugin:validate-stm` first if not recently validated.

## Step 3: Apply Approval

Use a Python script via Bash to update the Excel workbook:

```bash
uv run python -c "
import openpyxl
from datetime import date

wb = openpyxl.load_workbook('$LATEST_FILE')
ws = wb['Summary']

# Update Status cell
for row in ws.iter_rows(min_row=1, max_col=2):
    if row[0].value and str(row[0].value).strip() == 'Status':
        row[1].value = 'Approved'
    if row[0].value and str(row[0].value).strip() == 'Last Modified':
        row[1].value = str(date.today())

wb.save('$LATEST_FILE')
wb.close()
print('Status updated to Approved')
"
```

## Step 4: Confirm to User

Report:
- Which file was approved
- The version number
- Reminder: downstream artifacts (DQS, LLD, Stories) can now be created against this STM

## Step 5: Session Memory

Write a session note:

```bash
cat << 'SESSION_EOF' > memory/stm/session-$(date +%Y-%m-%d).md
## STM Approval Session — $(date +%Y-%m-%d)

- **Action**: Approved STM
- **File**: {filename}
- **Version**: {version}
- **Previous Status**: {old-status}
- **New Status**: Approved
SESSION_EOF
```
