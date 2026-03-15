# Chapter 4: Data Modeling Agent (continuation of Chapter 3)

A Claude Code plugin that acts as a Business Analyst Agent, generating, updating, and validating **Data Requirements Documents (DRDs)** from business inputs.

The use case is **Patient 360** — a unified patient search experience across Synthea healthcare data.

## Prerequisites

- [Claude Code](https://code.claude.com) CLI installed
- Python 3.10–3.12
- [UV](https://docs.astral.sh/uv/) package manager

## Quick Start

### 1. Install dependencies

```bash
cd chapter-4
make dev-setup
```

### 2. Add the marketplace

From the repo root, open Claude Code and add the local marketplace:

```
/plugin marketplace add ./chapter-4
```

### 3. Install the plugin

```
/plugin install ba-plugin@rdewai-plugins
```

You can verify the install by running `/plugin` — you should see:

```
ba-plugin (v1.0.0)
  Skills: create-drd, update-drd, validate-drd
  Agents: ba-agent
  Hooks: PreToolUse, PostToolUse
  Status: Enabled
```

### 4. Use the BA Agent

The recommended way to use this plugin is through the **BA Agent** — a sub-agent that orchestrates all three skills with an interactive Q&A workflow:

```
@ba-agent Create a DRD from the inputs in chapter-4/inputs/drd/v1
```

The agent will:
1. Read all input documents
2. Assess gaps in each DRD section
3. Ask you clarifying questions (using structured Q&A) until all sections have specific requirements
4. Explore the source database with read-only queries
5. Generate the DRD following the template
6. Validate automatically and fix any critical issues

Other agent invocations:

```
@ba-agent Update the Patient 360 DRD with new billing team requirements
@ba-agent Validate the DRD at chapter-4/outputs/drd/DRD-2026-02-10-patient-360-v1.md
```

### 5. Use the skills directly (alternative)

You can also invoke skills directly without the agent wrapper. Make sure you have `data/duckdb/raw.db` already created.

```
/create-drd chapter-4/inputs/drd/v1
```

or as natural language:

```
create a drd for the requirements under chapter-4/inputs/drd/v1
```

This reads the input documents and generates a DRD in `chapter-4/outputs/drd/`.

Other skills:

```
/update-drd chapter-4/outputs/drd/DRD-2026-02-10-patient-360-v1.md
/validate-drd chapter-4/outputs/drd/DRD-2026-02-10-patient-360-v1.md
```

## How the Plugin Works

### BA Agent

The `ba-agent` sub-agent (`ba-plugin/agents/ba-agent.md`) is the primary interface. It embodies the Business/Data Analyst role with:

- **Requirements Elicitation Protocol** — asks structured questions section-by-section using `AskUserQuestion`, iterating until all DRD sections have specific, measurable requirements
- **Source Exploration** — runs read-only DuckDB queries to verify table existence, row counts, column types, and null rates against what input documents claim
- **Pitfall Prevention** — rejects vague requirements ("all data", "real-time", "fast"), never skips source exploration, prevents gold-plating
- **Session Memory** — writes notes to `ba-plugin/memory/` after each engagement, tracking decisions, open questions, and DRD iteration history

### Skills

| Skill | What it does |
|-------|-------------|
| `create-drd` | Reads input documents, generates a complete DRD following a Jinja2 template |
| `update-drd` | Merges new information into an existing DRD, preserving unchanged content |
| `validate-drd` | Runs 15 validation checks (CRITICAL / WARNING / INFO) on a DRD |

### Hooks

The plugin registers two hooks:

**PreToolUse — Read-Only Query Enforcement**

Fires before every `Bash` command. Blocks database write operations (INSERT, UPDATE, DELETE, DROP, etc.) and enforces the `-readonly` flag on DuckDB invocations. This prevents the BA agent from accidentally modifying the source database.

**PostToolUse — Automatic DRD Validation**

Fires after every `Write` or `Edit` operation. When Claude writes a file to `outputs/drd/`:

1. The hook script checks if the file is a DRD (`.md` in `outputs/drd/`)
2. Runs the Python validator against the file
3. **CRITICAL issues** → blocks Claude and feeds errors back for auto-fix
4. **Warnings** → passed as non-blocking context
5. **Pass** → no interruption

This means DRDs are validated automatically — no manual step needed.

### Input Documents

Sample inputs are in `inputs/drd/v1/`:

| File | Contents |
|------|----------|
| `business_request.md` | Patient 360 business request from the CMO |
| `stakeholder_notes.md` | Interview notes from 5 stakeholders (CMO, CIO, Clinical Ops, Revenue Cycle, Physician) |
| `source_system_docs.md` | Synthea database schema (18 tables with column definitions) |
| `data_catalog.md` | Table inventory with row counts and sample queries |

## Plugin Directory Structure

```
chapter-4/
├── .claude-plugin/
│   └── marketplace.json               # Local marketplace manifest
├── ba-plugin/                      # Plugin root
│   ├── .claude-plugin/
│   │   └── plugin.json                # Plugin manifest
│   ├── agents/
│   │   └── ba-agent.md                # BA Agent sub-agent definition
│   ├── skills/
│   │   ├── create-drd/
│   │   │   ├── SKILL.md               # Skill instructions
│   │   │   ├── DRD_template.j2        # Template for DRD structure
│   │   │   └── examples/
│   │   │       └── sample-drd.md      # Complete example DRD
│   │   ├── update-drd/
│   │   │   └── SKILL.md
│   │   └── validate-drd/
│   │       ├── SKILL.md
│   │       └── scripts/
│   │           └── validate_drd.py
│   ├── hooks/
│   │   └── hooks.json                 # PreToolUse + PostToolUse hook config
│   ├── memory/                        # Session notes (cross-session memory)
│   │   └── .gitkeep
│   └── scripts/
│       ├── validate-drd-hook.py       # PostToolUse: auto-validate DRDs
│       └── enforce-readonly-queries.py # PreToolUse: block DB write operations
├── inputs/drd/                        # Input documents
├── outputs/drd/                       # Generated DRDs
├── tests/                             # Unit tests
├── pyproject.toml
├── Makefile
└── README.md
```

## Testing

### Run all unit tests

```bash
cd chapter-4
make test
```

This runs 89 tests: 38 for the validator, 11 for the validation hook, 21 for the read-only query hook, and 19 for the agent definition.

### Run the validator directly

```bash
# Validate a specific DRD
cd chapter-4
uv run python ba-plugin/skills/validate-drd/scripts/validate_drd.py outputs/drd/DRD-2026-02-10-patient-360-v1.md

# Validate all DRDs in the output directory
make validate-drd

# JSON output for machine consumption
uv run python ba-plugin/skills/validate-drd/scripts/validate_drd.py --format json outputs/drd/DRD-2026-02-10-patient-360-v1.md
```

### Test the hook script manually

```bash
cd chapter-4

# Non-DRD file — should exit 0 (skipped)
echo '{"tool_input":{"file_path":"/some/file.py"}}' | python3 ba-plugin/scripts/validate-drd-hook.py
echo $?   # 0

# Invalid DRD — should exit 2 (CRITICAL issues)
echo '# Bad DRD' > /tmp/test-drd.md
echo '{"tool_input":{"file_path":"/project/outputs/drd/test.md"}}' | python3 ba-plugin/scripts/validate-drd-hook.py
echo $?   # 2
```

### Test the plugin end-to-end

1. Start Claude Code from the repo root (`claude`)
2. Add marketplace: `/plugin marketplace add ./chapter-4`
3. Install plugin: `/plugin install ba-plugin@rdewai-plugins`
4. Invoke the agent: `@ba-agent Create a DRD from chapter-4/inputs/drd/v1`
5. Answer the agent's clarifying questions until it confirms readiness
6. Verify a DRD was created in `chapter-4/outputs/drd/`
7. The PostToolUse hook should have auto-validated it
8. Session notes should appear in `ba-plugin/memory/`

### Debug plugin loading

```bash
claude --debug
```

This shows which plugins are loaded, which hooks are registered, and when they fire.

## Updating the Plugin

After making changes to plugin files, update the cached version:

1. Open `/plugin` in Claude Code
2. Select **ba-plugin**
3. Select **Update now**

Or uninstall and reinstall:

```
/plugin uninstall ba-plugin@rdewai-plugins
/plugin install ba-plugin@rdewai-plugins
```

## Makefile Targets

```bash
make help           # Show all commands
make dev-setup      # Install Python dependencies
make test           # Run all 89 tests
make validate-drd   # Validate all DRDs in outputs/
make lint           # Run ruff linter
make format         # Auto-format code
make clean          # Remove caches
```
