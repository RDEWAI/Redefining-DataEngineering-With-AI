---
name: approve-stories
description: >
  Approves a Sprint Backlog by setting its status to Approved.
  Reads the latest BACKLOG file, verifies it is not already approved, updates the
  Status field and adds a version history entry. Approval signifies the backlog
  is sprint-ready and stories can be picked up for implementation.
  Use when the user asks to:
  - Approve a backlog or stories
  - Sign off on sprint stories
  - Mark stories as approved or sprint-ready
argument-hint: "[backlog-file-path]"
allowed-tools: Read, Edit, Glob, Bash
context: fork
---

# Approve Sprint Backlog

You are a Scrum Master. Your task is to formally approve a Sprint Backlog,
changing its status to `Approved` to signify that stories are sprint-ready
and can be picked up for implementation.

---

## Step 1: Locate the Latest Backlog

If the user specifies a backlog path via `$ARGUMENTS`, use that file. Otherwise:

```bash
LATEST_STORIES_DIR=$(ls -d outputs/stories/v* | sort -V | tail -1)
LATEST_FILE=$(ls -t "$LATEST_STORIES_DIR"/BACKLOG-*.md 2>/dev/null | grep -v '\.bak$' | head -1)
echo "Latest Backlog: $LATEST_FILE"
```

Read the file and extract the metadata table (Status and Version fields).

## Step 2: Pre-Checks

### 2a. Already Approved
If Status is already `Approved`:
- Inform the user: "This Backlog is already approved (version X.Y). No action needed."
- STOP. No changes.

### 2b. Draft Status Warning
If Status is `Draft`:
- Warn the user: "This Backlog has Status: Draft — it has never been through a review cycle. Consider running update-stories or validate-stories first."
- Present the warning and wait for confirmation:
  - If user confirms they want to approve anyway, proceed
  - If user wants to review first, STOP

### 2c. Validation Recommendation
Recommend running `/scrum-master-plugin:validate-stories` first if not recently validated.

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
| {current-version} | {today's date} | Scrum Master Agent | Status changed to Approved |
```

## Step 4: Confirm to User

Report:
- Which file was approved
- The version number
- Note: This backlog is now sprint-ready — stories can be picked up for implementation

## Step 5: Session Memory

Write a session note:

```bash
cat << 'SESSION_EOF' > memory/stories/session-$(date +%Y-%m-%d).md
## Stories Approval Session — $(date +%Y-%m-%d)

- **Action**: Approved Sprint Backlog
- **File**: {filename}
- **Version**: {version}
- **Previous Status**: {old-status}
- **New Status**: Approved
SESSION_EOF
```
