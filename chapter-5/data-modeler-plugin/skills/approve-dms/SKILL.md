---
name: approve-dms
description: >
  Approves a Data Model Specification (DMS) document by setting its status to Approved.
  Reads the latest DMS, verifies it is not already approved, updates the Status
  field and adds a version history entry. This is the gate that enables downstream
  artifact creation (STM, DQS, LLD, Stories).
  Use when the user asks to:
  - Approve a DMS
  - Sign off on a DMS
  - Mark a DMS as approved or ready for handoff
argument-hint: "[dms-file-path]"
allowed-tools: Read, Edit, Glob, Bash
context: fork
---

# Approve Data Model Specification

You are a senior Data Modeler. Your task is to formally approve a DMS,
changing its status to `Approved` so that downstream artifact creation (STM,
DQS, LLD, Stories) can proceed.

---

## Step 1: Locate the Latest DMS

If the user specifies a DMS path via `$ARGUMENTS`, use that file. Otherwise:

```bash
LATEST_DMS_DIR=$(ls -d outputs/dms/v* | sort -V | tail -1)
LATEST_FILE=$(ls -t "$LATEST_DMS_DIR"/DMS-*.md 2>/dev/null | grep -v '\.bak$' | head -1)
echo "Latest DMS: $LATEST_FILE"
```

Read the file and extract the metadata table (Status and Version fields).

## Step 2: Pre-Checks

### 2a. Already Approved
If Status is already `Approved`:
- Inform the user: "This DMS is already approved (version X.Y). No action needed."
- STOP. No changes.

### 2b. Draft Status Warning
If Status is `Draft`:
- Warn the user: "This DMS has Status: Draft — it has never been through a review cycle. Consider running update-dms or validate-dms first."
- Present the warning and wait for confirmation:
  - If user confirms they want to approve anyway, proceed
  - If user wants to review first, STOP

### 2c. Validation Recommendation
If the DMS has not been validated recently (check `memory/dms/` for recent validation session notes), recommend running `/data-modeler-plugin:validate-dms` first. This is a recommendation, not a gate.

## Step 3: Apply Approval

Use the `Edit` tool for each change — never `Write`:

### 3a. Update Status
Find the Status row in the metadata table and change it to `Approved`:

```
Edit: | **Status** | {current-status} |  →  | **Status** | Approved |
```

### 3b. Update Last Modified
```
Edit: | **Last Modified** | {old-date} |  →  | **Last Modified** | {today's date} |
```

### 3c. Add Version History Entry
Add a new row to the Version History table:

```markdown
| {current-version} | {today's date} | Data Modeler Agent | Status changed to Approved |
```

## Step 4: Confirm to User

Report:
- Which file was approved
- The version number
- Reminder: downstream artifacts (STM, DQS, LLD, Stories) can now be created against this DMS

## Step 5: Session Memory

Write a session note:

```bash
cat << 'SESSION_EOF' > memory/dms/session-$(date +%Y-%m-%d).md
## DMS Approval Session — $(date +%Y-%m-%d)

- **Action**: Approved DMS
- **File**: {filename}
- **Version**: {version}
- **Previous Status**: {old-status}
- **New Status**: Approved
SESSION_EOF
```
