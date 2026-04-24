---
name: approve-dqs
description: >
  Approves a Data Quality Specification (DQS) document by setting its status to Approved.
  Reads the latest DQS, verifies it is not already approved, updates the Status
  field and adds a version history entry. This is the gate that enables downstream
  artifact creation (LLD, Stories).
  Use when the user asks to:
  - Approve a DQS
  - Sign off on a DQS
  - Mark a DQS as approved or ready for handoff
argument-hint: "[dqs-file-path]"
allowed-tools: Read, Edit, Glob, Bash
context: fork
---

# Approve Data Quality Specification

You are a senior DQ Engineer. Your task is to formally approve a DQS,
changing its status to `Approved` so that downstream artifact creation (LLD,
Stories) can proceed.

---

## Step 1: Locate the Latest DQS

If the user specifies a DQS path via `$ARGUMENTS`, use that file. Otherwise:

```bash
LATEST_DQS_DIR=$(ls -d outputs/dqs/v* | sort -V | tail -1)
LATEST_FILE=$(ls -t "$LATEST_DQS_DIR"/DQS-*.md 2>/dev/null | grep -v '\.bak$' | head -1)
echo "Latest DQS: $LATEST_FILE"
```

Read the file and extract the metadata table (Status and Version fields).

## Step 2: Pre-Checks

### 2a. Already Approved
If Status is already `Approved`:
- Inform the user: "This DQS is already approved (version X.Y). No action needed."
- STOP. No changes.

### 2b. Draft Status Warning
If Status is `Draft`:
- Warn the user: "This DQS has Status: Draft — it has never been through a review cycle. Consider running update-dqs or validate-dqs first."
- Present the warning and wait for confirmation:
  - If user confirms they want to approve anyway, proceed
  - If user wants to review first, STOP

### 2c. Validation Recommendation
Recommend running `/dq-engineer-plugin:validate-dqs` first if not recently validated.

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
| {current-version} | {today's date} | DQ Engineer Agent | Status changed to Approved |
```

## Step 4: Confirm to User

Report:
- Which file was approved
- The version number
- Reminder: downstream artifacts (LLD, Stories) can now be created against this DQS

## Step 5: Session Memory

Write a session note:

```bash
cat << 'SESSION_EOF' > memory/dqs/session-$(date +%Y-%m-%d).md
## DQS Approval Session — $(date +%Y-%m-%d)

- **Action**: Approved DQS
- **File**: {filename}
- **Version**: {version}
- **Previous Status**: {old-status}
- **New Status**: Approved
SESSION_EOF
```
