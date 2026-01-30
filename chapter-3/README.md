# Chapter 3: Business Analyst Agent — DRD Plugin

A Claude Code plugin that acts as a Business Analyst Agent, generating, updating, and validating **Data Requirements Documents (DRDs)** from business inputs.

The use case is **Patient 360** — a unified patient search experience across Synthea healthcare data.

## Prerequisites

- [Claude Code](https://code.claude.com) CLI installed
- Python 3.10–3.12
- [UV](https://docs.astral.sh/uv/) package manager

## Quick Start

### 1. Install dependencies

```bash
cd chapter-3
make dev-setup
```

### 2. Add the marketplace

From the repo root, open Claude Code and add the local marketplace:

```
/plugin marketplace add ./chapter-3
```

### 3. Install the plugin

```
/plugin install ba-agent-drd@rdewai-plugins
```

You can verify the install by running `/plugin` — you should see:

```
ba-agent-drd (v1.0.0)
  Skills: create-drd, update-drd, validate-drd
  Hooks: PostToolUse
  Status: Enabled
```

### 4. Use the skills

```
/create-drd chapter-3/inputs/drd/samples
```

This reads the sample input documents (business request, stakeholder notes, source system docs, data catalog) and generates a DRD in `chapter-3/outputs/drd/`.

Other skills:

```
/update-drd chapter-3/outputs/drd/DRD-2026-01-29-patient-360.md
/validate-drd chapter-3/outputs/drd/DRD-2026-01-29-patient-360.md
```

## How the Plugin Works

### Skills

| Skill | What it does |
|-------|-------------|
| `create-drd` | Reads input documents, generates a complete DRD following a Jinja2 template |
| `update-drd` | Merges new information into an existing DRD, preserving unchanged content |
| `validate-drd` | Runs 14 validation checks (CRITICAL / WARNING / INFO) on a DRD |

### Automatic Validation Hook

The plugin registers a **PostToolUse** hook that fires after every `Write` or `Edit` operation. When Claude writes a file to `outputs/drd/`:

1. The hook script checks if the file is a DRD (`.md` in `outputs/drd/`)
2. Runs the Python validator against the file
3. **CRITICAL issues** → blocks Claude and feeds errors back for auto-fix
4. **Warnings** → passed as non-blocking context
5. **Pass** → no interruption

This means DRDs are validated automatically — no manual step needed.

### Input Documents

Sample inputs are in `inputs/drd/samples/`:

| File | Contents |
|------|----------|
| `business_request.md` | Patient 360 business request from the CMO |
| `stakeholder_notes.md` | Interview notes from 5 stakeholders (CMO, CIO, Clinical Ops, Revenue Cycle, Physician) |
| `source_system_docs.md` | Synthea database schema (18 tables with column definitions) |
| `data_catalog.md` | Table inventory with row counts and sample queries |

## Plugin Directory Structure

```
chapter-3/
├── .claude-plugin/
│   └── marketplace.json          # Local marketplace manifest
├── ba-agent-drd/                 # Plugin root
│   ├── .claude-plugin/
│   │   └── plugin.json           # Plugin manifest
│   ├── skills/
│   │   ├── create-drd/
│   │   │   ├── SKILL.md          # Skill instructions
│   │   │   ├── DRD_template.j2   # Template for DRD structure
│   │   │   └── examples/
│   │   │       └── sample-drd.md # Complete example DRD
│   │   ├── update-drd/
│   │   │   └── SKILL.md
│   │   └── validate-drd/
│   │       ├── SKILL.md
│   │       └── scripts/
│   │           └── validate_drd.py
│   ├── hooks/
│   │   └── hooks.json            # PostToolUse hook config
│   └── scripts/
│       └── validate-drd-hook.py  # Hook script
├── inputs/drd/                   # Input documents
├── outputs/drd/                  # Generated DRDs
├── tests/                        # Unit tests
├── pyproject.toml
├── Makefile
└── README.md
```

## Testing

### Run all unit tests

```bash
cd chapter-3
make test
```

This runs 47 tests: 36 for the validator and 11 for the hook script.

### Run the validator directly

```bash
# Validate a specific DRD
cd chapter-3
uv run python ba-agent-drd/skills/validate-drd/scripts/validate_drd.py outputs/drd/DRD-2026-01-29-patient-360.md

# Validate all DRDs in the output directory
make validate-drd

# JSON output for machine consumption
uv run python ba-agent-drd/skills/validate-drd/scripts/validate_drd.py --format json outputs/drd/DRD-2026-01-29-patient-360.md
```

### Test the hook script manually

```bash
cd chapter-3

# Non-DRD file — should exit 0 (skipped)
echo '{"tool_input":{"file_path":"/some/file.py"}}' | python3 ba-agent-drd/scripts/validate-drd-hook.py
echo $?   # 0

# Invalid DRD — should exit 2 (CRITICAL issues)
echo '# Bad DRD' > /tmp/test-drd.md
echo '{"tool_input":{"file_path":"/project/outputs/drd/test.md"}}' | python3 ba-agent-drd/scripts/validate-drd-hook.py
echo $?   # 2
```

### Test the plugin end-to-end

1. Start Claude Code from the repo root (`claude`)
2. Add marketplace: `/plugin marketplace add ./chapter-3`
3. Install plugin: `/plugin install ba-agent-drd@rdewai-plugins`
4. Run the skill: `/create-drd chapter-3/inputs/drd/samples`
5. Verify a DRD was created in `chapter-3/outputs/drd/`
6. The PostToolUse hook should have auto-validated it

### Debug plugin loading

```bash
claude --debug
```

This shows which plugins are loaded, which hooks are registered, and when they fire.

## Updating the Plugin

After making changes to plugin files, update the cached version:

1. Open `/plugin` in Claude Code
2. Select **ba-agent-drd**
3. Select **Update now**

Or uninstall and reinstall:

```
/plugin uninstall ba-agent-drd@rdewai-plugins
/plugin install ba-agent-drd@rdewai-plugins
```

## Makefile Targets

```bash
make help           # Show all commands
make dev-setup      # Install Python dependencies
make test           # Run all 47 tests
make validate-drd   # Validate all DRDs in outputs/
make lint           # Run ruff linter
make format         # Auto-format code
make clean          # Remove caches
```
