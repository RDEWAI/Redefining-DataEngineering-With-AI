---
name: approve-hld
description: >
  Approves a High-Level Design (HLD) document by setting its status to Approved.
  Reads the latest HLD, verifies it is not already approved, updates the Status
  field and adds a version history entry. This is the gate that enables downstream
  artifact creation (DMS, STM, DQS, LLD, Stories).
  Use when the user asks to:
  - Approve an HLD
  - Sign off on an HLD
  - Mark an HLD as approved or ready for handoff
argument-hint: "[hld-file-path]"
allowed-tools: Read, Edit, Glob, Bash
context: fork
---

# Approve High-Level Design Document

You are a senior Data Architect. Your task is to formally approve an HLD,
changing its status to `Approved` so that downstream artifact creation (DMS,
STM, DQS, LLD, Stories) can proceed.

---

## Step 1: Locate the Latest HLD

If the user specifies an HLD path via `$ARGUMENTS`, use that file. Otherwise:

```bash
LATEST_HLD_DIR=$(ls -d outputs/hld/v* | sort -V | tail -1)
LATEST_FILE=$(ls -t "$LATEST_HLD_DIR"/HLD-*.md 2>/dev/null | grep -v '\.bak$' | head -1)
echo "Latest HLD: $LATEST_FILE"
```

Read the file and extract the metadata table (Status and Version fields).

## Step 2: Pre-Checks

### 2a. Already Approved
If Status is already `Approved`:
- Inform the user: "This HLD is already approved (version X.Y). No action needed."
- STOP. No changes.

### 2b. Draft Status Warning
If Status is `Draft`:
- Warn the user: "This HLD has Status: Draft — it has never been through a review cycle. Consider running update-hld or validate-hld first."
- Present the warning and wait for confirmation:
  - If user confirms they want to approve anyway, proceed
  - If user wants to review first, STOP

### 2c. Validation Recommendation
If the HLD has not been validated recently (check `memory/hld/` for recent validation session notes), recommend running `/architect-plugin:validate-hld` first. This is a recommendation, not a gate.

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
| {current-version} | {today's date} | Architect Agent | Status changed to Approved |
```

## Step 4: Confirm to User

Report:
- Which file was approved
- The version number
- Reminder: downstream artifacts (DMS, STM, DQS, LLD, Stories) can now be created against this HLD

## Step 5: Session Memory

Write a session note:

```bash
cat << 'SESSION_EOF' > memory/hld/session-$(date +%Y-%m-%d).md
## HLD Approval Session — $(date +%Y-%m-%d)

- **Action**: Approved HLD
- **File**: {filename}
- **Version**: {version}
- **Previous Status**: {old-status}
- **New Status**: Approved
SESSION_EOF
```
