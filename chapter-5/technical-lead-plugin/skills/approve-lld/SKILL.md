---
name: approve-lld
description: >
  Approves a Low-Level Design (LLD) document by setting its status to Approved.
  Reads the latest LLD, verifies it is not already approved, updates the Status
  field and adds a version history entry. This is the gate that enables downstream
  artifact creation (Stories).
  Use when the user asks to:
  - Approve an LLD
  - Sign off on an LLD
  - Mark an LLD as approved or ready for handoff
argument-hint: "[lld-file-path]"
allowed-tools: Read, Edit, Glob, Bash
context: fork
---

# Approve Low-Level Design Document

You are a senior Technical Lead. Your task is to formally approve an LLD,
changing its status to `Approved` so that downstream artifact creation (Stories)
can proceed.

---

## Step 1: Locate the Latest LLD

If the user specifies an LLD path via `$ARGUMENTS`, use that file. Otherwise:

```bash
LATEST_LLD_DIR=$(ls -d outputs/lld/v* | sort -V | tail -1)
LATEST_FILE=$(ls -t "$LATEST_LLD_DIR"/LLD-*.md 2>/dev/null | grep -v '\.bak$' | head -1)
echo "Latest LLD: $LATEST_FILE"
```

Read the file and extract the metadata table (Status and Version fields).

## Step 2: Pre-Checks

### 2a. Already Approved
If Status is already `Approved`:
- Inform the user: "This LLD is already approved (version X.Y). No action needed."
- STOP. No changes.

### 2b. Draft Status Warning
If Status is `Draft`:
- Warn the user: "This LLD has Status: Draft — it has never been through a review cycle. Consider running update-lld or validate-lld first."
- Present the warning and wait for confirmation:
  - If user confirms they want to approve anyway, proceed
  - If user wants to review first, STOP

### 2c. Validation Recommendation
Recommend running `/technical-lead-plugin:validate-lld` first if not recently validated.

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
| {current-version} | {today's date} | Technical Lead Agent | Status changed to Approved |
```

## Step 4: Confirm to User

Report:
- Which file was approved
- The version number
- Reminder: downstream artifact (Stories) can now be created against this LLD

## Step 5: Session Memory

Write a session note:

```bash
cat << 'SESSION_EOF' > memory/lld/session-$(date +%Y-%m-%d).md
## LLD Approval Session — $(date +%Y-%m-%d)

- **Action**: Approved LLD
- **File**: {filename}
- **Version**: {version}
- **Previous Status**: {old-status}
- **New Status**: Approved
SESSION_EOF
```
