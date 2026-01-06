# PWI CLI Reference

Complete reference for all PWI command-line interface commands.

## Global Options

These options are available for all commands:

```bash
pwi [OPTIONS] COMMAND [ARGS]

Options:
  -v, --verbose     Enable verbose/debug output
  --json-logs       Output logs in JSON format (for machine parsing)
  --log-file PATH   Write logs to a file
  --help            Show help message
```

## Commands Overview

| Command | Description |
|---------|-------------|
| `pwi init` | Initialize a new PWI project |
| `pwi plan run` | Run planning workflow on a request |
| `pwi session` | Manage workflow sessions |
| `pwi review` | Review and approve artifacts |
| `pwi generate` | Generate specific artifacts |
| `pwi dashboard` | Start the web dashboard |
| `pwi version` | Show PWI version |

---

## pwi init

Initialize a new PWI project with configuration and directory structure.

```bash
pwi init [OPTIONS]
```

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--type` | `data_engineering` | Project type (data_engineering, analytics, ml_pipeline) |
| `--name` | Directory name | Project name |
| `--output-dir` | `./output` | Output directory for artifacts |

### Example

```bash
# Initialize with defaults
pwi init

# Initialize with specific type and name
pwi init --type analytics --name "Customer Analytics"
```

### Generated Files

- `pwi.yaml` - Main configuration file
- `requests/` - Directory for request files
- `output/` - Directory for generated artifacts
- `.pwi/sessions/` - Session storage directory

---

## pwi plan run

Run the full planning workflow on a business request.

```bash
pwi plan run [OPTIONS] REQUEST_FILE
```

### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `REQUEST_FILE` | Yes | Path to the request markdown file |

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--project-name` | Auto-generated | Name for the project/session |
| `--auto-approve`, `-y` | `false` | Auto-approve all review gates |
| `--skip-review` | `false` | Skip all review gates entirely |
| `--config`, `-c` | `pwi.yaml` | Path to configuration file |

### Example

```bash
# Basic run
pwi plan run requests/customer-360.md

# Run with auto-approve
pwi plan run requests/customer-360.md --auto-approve

# Run with custom project name
pwi plan run requests/customer-360.md --project-name "Q1 Analytics"

# Run with verbose output and JSON logs
pwi --verbose --json-logs plan run requests/customer-360.md
```

---

## pwi session

Manage workflow sessions.

### pwi session list

List all workflow sessions.

```bash
pwi session list [OPTIONS]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--limit`, `-n` | `10` | Maximum sessions to show |
| `--all`, `-a` | `false` | Show all sessions |
| `--state`, `-s` | None | Filter by state (running, paused, completed, failed) |

### pwi session status

Show detailed status of a session.

```bash
pwi session status SESSION_ID
```

Displays:
- Session metadata
- Current state
- Artifacts generated
- Token usage and costs
- Review history

### pwi session resume

Resume a paused workflow session.

```bash
pwi session resume [OPTIONS] SESSION_ID
```

| Option | Default | Description |
|--------|---------|-------------|
| `--auto-approve`, `-y` | `false` | Auto-approve remaining gates |
| `--skip-review` | `false` | Skip remaining review gates |

### pwi session delete

Delete a workflow session.

```bash
pwi session delete [OPTIONS] SESSION_ID
```

| Option | Default | Description |
|--------|---------|-------------|
| `--force`, `-f` | `false` | Skip confirmation prompt |

### pwi session export

Export session artifacts to files.

```bash
pwi session export [OPTIONS] SESSION_ID
```

| Option | Default | Description |
|--------|---------|-------------|
| `--output`, `-o` | `./<session-id>/` | Output directory |

### Examples

```bash
# List recent sessions
pwi session list

# List all completed sessions
pwi session list --all --state completed

# View session details
pwi session status abc123

# Resume a paused session
pwi session resume abc123

# Resume with auto-approve
pwi session resume abc123 --auto-approve

# Delete with confirmation
pwi session delete abc123

# Force delete
pwi session delete abc123 --force

# Export artifacts
pwi session export abc123 --output ./my-export/
```

---

## pwi review

Review and approve artifacts at review gates.

### pwi review show

Display the artifact pending review.

```bash
pwi review show SESSION_ID
```

Shows the full content of the artifact waiting for approval.

### pwi review approve

Approve the current artifact and continue workflow.

```bash
pwi review approve [OPTIONS] SESSION_ID
```

| Option | Default | Description |
|--------|---------|-------------|
| `--comment`, `-c` | None | Optional feedback comment |

### pwi review reject

Reject the current artifact.

```bash
pwi review reject [OPTIONS] SESSION_ID
```

| Option | Required | Description |
|--------|----------|-------------|
| `--reason`, `-r` | Yes | Reason for rejection |

### pwi review history

Show review history for a session.

```bash
pwi review history SESSION_ID
```

### Examples

```bash
# Show pending review
pwi review show abc123

# Approve with comment
pwi review approve abc123 --comment "Looks good!"

# Reject with reason
pwi review reject abc123 --reason "Missing data source definitions"

# View review history
pwi review history abc123
```

---

## pwi generate

Generate specific artifacts (standalone generation).

### pwi generate mapping

Generate a data mapping document for a specific entity.

```bash
pwi generate mapping [OPTIONS] ENTITY
```

| Option | Description |
|--------|-------------|
| `--session`, `-s` | Session ID to use as context |
| `--output`, `-o` | Output file path |

### pwi generate dq-spec

Generate a data quality specification for a pipeline.

```bash
pwi generate dq-spec [OPTIONS] PIPELINE
```

| Option | Description |
|--------|-------------|
| `--session`, `-s` | Session ID to use as context |
| `--output`, `-o` | Output file path |

### pwi generate stories

Generate epics and stories from session artifacts.

```bash
pwi generate stories [OPTIONS] SESSION_ID
```

| Option | Default | Description |
|--------|---------|-------------|
| `--output`, `-o` | None | Output directory |
| `--format`, `-f` | `markdown` | Output format (markdown, json) |

### pwi generate dag

Generate orchestration DAG code from a session.

```bash
pwi generate dag [OPTIONS] SESSION_ID
```

| Option | Default | Description |
|--------|---------|-------------|
| `--orchestrator`, `-r` | `airflow` | Framework (airflow, dagster, prefect) |
| `--output`, `-o` | None | Output file path |

---

## pwi dashboard

Start the NiceGUI web dashboard.

```bash
pwi dashboard [OPTIONS]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--port` | `8080` | Port to run dashboard on |
| `--host` | `127.0.0.1` | Host to bind to |

### Example

```bash
# Start on default port
pwi dashboard

# Start on custom port
pwi dashboard --port 3000

# Allow external access
pwi dashboard --host 0.0.0.0
```

---

## pwi version

Show PWI version information.

```bash
pwi version
```

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error or failure |
| 2 | Command-line usage error |

## Environment Variables

| Variable | Description |
|----------|-------------|
| `LLM_API_KEY` | API key for the LLM provider |
| `LLM_BASE_URL` | Base URL for the LLM API |
| `LLM_MODEL` | Default model to use |
| `PWI_CONFIG` | Path to configuration file |
| `PWI_SESSION_DIR` | Override session storage directory |
| `PWI_OUTPUT_DIR` | Override output directory |
