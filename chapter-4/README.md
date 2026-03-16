# Chapter 4: Planning with Context — Multi-Agent Artifact Chain

Two Claude Code plugins that act as a **Business Analyst Agent** and a **Data Architect Agent**, producing structured artifacts that feed the next role in the chain.

**Artifact chain**: DRD → **HLD** → Data Model → DMD → DQS → LLD → Stories

The use case is **Patient 360** — a unified patient search experience across Synthea healthcare data.

## Prerequisites

- [Claude Code](https://code.claude.com) CLI installed
- Python 3.10–3.12
- [UV](https://docs.astral.sh/uv/) package manager
- **Max output tokens** — Some agents (e.g., Data Modeler) generate large artifacts that exceed the default 32k token limit. Add this to your `~/.zshrc`:
  ```bash
  export CLAUDE_CODE_MAX_OUTPUT_TOKENS=128000
  ```

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

### 3. Install the plugins

```
/plugin install ba-plugin@rdewai-plugins
/plugin install architect-plugin@rdewai-plugins
/plugin install data-modeler-plugin@rdewai-plugins
```

You can verify the install by running `/plugin` — you should see:

```
ba-plugin (v1.0.0)
  Skills: create-drd, update-drd, validate-drd
  Agents: ba-agent
  Hooks: PreToolUse, PostToolUse
  Status: Enabled

architect-plugin (v1.0.0)
  Skills: create-hld, update-hld, validate-hld
  Agents: architect-agent
  Hooks: PreToolUse, PostToolUse
  Status: Enabled

data-modeler-plugin (v1.0.0)
  Skills: create-dms, update-dms, validate-dms
  Agents: data-modeler-agent
  Hooks: PreToolUse, PostToolUse
  Status: Enabled
```

### 4. Use the BA Agent

The BA Agent orchestrates DRD creation with an interactive Q&A workflow:

```
@ba-agent Create a DRD from the inputs in inputs/drd/v1
```

The agent will:
1. Discover the latest input version folder automatically
2. Read all input documents
3. Assess gaps in each DRD section
4. Ask you clarifying questions (using structured `AskUserQuestion` UI) until all sections have specific requirements
5. Explore the source database with read-only queries
6. Generate the DRD following the template
7. Validate automatically and fix any critical issues

Other agent invocations:

```
@ba-agent Update the Patient 360 DRD with new billing team requirements
@ba-agent Validate the DRD at outputs/drd/v1/DRD-2026-02-10-patient-360.md
```

### 5. Use the Architect Agent

The Architect Agent translates an approved DRD into a High-Level Design document:

```
@architect-plugin:architect-agent Create the HLD for the project we are working on
```

The agent will:
1. Discover the latest DRD and architect input version folders automatically
2. Read DRD, infrastructure constraints, team capabilities, and technology catalog
3. Assess gaps across 8 HLD sections (Design Overview, Layer Specs, Technology Stack, etc.)
4. Ask you design decisions via structured `AskUserQuestion` UI — one section at a time
5. Verify source data volumes with read-only database queries
6. Generate the HLD with full decision documentation and DRD traceability
7. Validate automatically and fix any critical issues

Other agent invocations:

```
@architect-plugin:architect-agent Update the existing HLD with new cloud migration constraints
@architect-plugin:architect-agent Validate the HLD at outputs/hld/v1/HLD-2026-03-15-pipeline.md
```

### 6. Use the Data Modeler Agent

The Data Modeler Agent translates HLD layer specifications into concrete schema definitions:

```
@data-modeler-plugin:data-modeler-agent Create the DMS from the latest HLD
```

The agent will:
1. Discover the latest HLD, DRD, and modeler input version folders automatically
2. Read HLD layer specs, DRD business rules, enterprise naming standards, governance policies, and data dictionary
3. Assess gaps across 9 DMS sections (Design Overview, Bronze/Silver/Gold Schemas, Naming Conventions, SCD Strategy, etc.)
4. Ask you schema design decisions via structured `AskUserQuestion` UI — one section at a time
5. Verify source table structures with read-only database queries (DESCRIBE, sample data, null rates)
6. Generate the DMS with embedded YAML schema blocks, SCD type decisions, and HLD traceability
7. Validate automatically and fix any critical issues

Other agent invocations:

```
@data-modeler-plugin:data-modeler-agent Update the DMS to add SCD Type 2 tracking for provider specialty
@data-modeler-plugin:data-modeler-agent Validate the DMS at outputs/dms/v1/DMS-2026-03-16-patient-360.md
```

### 7. Use skills directly (alternative)

You can also invoke skills directly without the agent wrapper. Make sure you have `data/duckdb/raw.db` already created.

```
/create-drd inputs/drd/v1
/create-hld outputs/drd/v1/DRD-2026-02-11-patient-360.md
```

Other skills:

```
/update-drd outputs/drd/v1/DRD-2026-02-10-patient-360.md
/validate-drd outputs/drd/v1/DRD-2026-02-10-patient-360.md
/update-hld outputs/hld/v1/HLD-2026-03-15-pipeline.md
/validate-hld outputs/hld/v1/HLD-2026-03-15-pipeline.md
/data-modeler-plugin:create-dms
/data-modeler-plugin:update-dms outputs/dms/v1/DMS-2026-03-16-patient-360.md
/data-modeler-plugin:validate-dms outputs/dms/v1/DMS-2026-03-16-patient-360.md
```

## How the Plugins Work

### BA Agent

The `ba-agent` sub-agent (`ba-plugin/agents/ba-agent.md`) embodies the Business/Data Analyst role with:

- **Requirements Elicitation Protocol** — asks structured questions section-by-section using `AskUserQuestion`, iterating until all DRD sections have specific, measurable requirements
- **Source Exploration** — runs read-only DuckDB queries to verify table existence, row counts, column types, and null rates against what input documents claim
- **Pitfall Prevention** — rejects vague requirements ("all data", "real-time", "fast"), never skips source exploration, prevents gold-plating
- **Session Memory** — writes notes to `ba-plugin/memory/` after each engagement

### Architect Agent

The `architect-agent` sub-agent (`architect-plugin/agents/architect-agent.md`) embodies the Data Architect role with:

- **Architecture Elicitation Protocol** — asks design decisions section-by-section using `AskUserQuestion`, covering pattern selection, technology choices, layer design, and capacity planning
- **Database Gate** — verifies actual data volumes with read-only queries before generating capacity plans; blocks HLD generation if the database is inaccessible
- **Decision Documentation** — every pattern choice, technology selection, and layer design requires Options Considered, Rationale, and Trade-off analysis
- **DRD Traceability** — every design decision must cite the DRD section it satisfies
- **Session Memory** — writes notes to `architect-plugin/memory/` after each engagement

### Data Modeler Agent

The `data-modeler-agent` sub-agent (`data-modeler-plugin/agents/data-modeler-agent.md`) embodies the Data Modeler role with:

- **Schema Elicitation Protocol** — asks schema design decisions section-by-section using `AskUserQuestion`, covering bronze/silver/gold schemas, SCD strategies, naming conventions, and physical design
- **Database Gate** — queries actual source table structures (DESCRIBE, sample data, null rates) before designing schemas; blocks DMS generation if the database is inaccessible
- **Dual-Format Output** — generates markdown narrative with embedded YAML schema blocks that downstream agents (Mapping Engineer, DQ Engineer) can parse programmatically
- **Enterprise Standards** — applies naming conventions, governance policies, and data dictionary from `inputs/dms/v1/` (PHI handling, approved types, enumeration standards)
- **HLD Traceability** — every schema decision must cite the HLD layer specification it implements
- **Session Memory** — writes notes to `data-modeler-plugin/memory/` after each engagement

### Skills

| Plugin | Skill | What it does |
|--------|-------|-------------|
| ba-plugin | `create-drd` | Reads input documents, generates a complete DRD following a Jinja2 template |
| ba-plugin | `update-drd` | Merges new information into an existing DRD, preserving unchanged content |
| ba-plugin | `validate-drd` | Runs 15 validation checks (CRITICAL / WARNING / INFO) on a DRD |
| architect-plugin | `create-hld` | Reads DRD + architect inputs, generates a complete HLD following a Jinja2 template |
| architect-plugin | `update-hld` | Merges changes into an existing HLD, verifying cross-section consistency |
| architect-plugin | `validate-hld` | Runs validation checks on an HLD (sections, traceability, tech table, CDC, capacity) |
| data-modeler-plugin | `create-dms` | Reads HLD + DRD + enterprise standards, generates a complete DMS with YAML schema blocks |
| data-modeler-plugin | `update-dms` | Merges schema changes into an existing DMS, preserving unchanged content |
| data-modeler-plugin | `validate-dms` | Runs validation checks on a DMS (sections, YAML syntax, SCD types, traceability) |

### Hooks

All three plugins register two hooks each:

**PreToolUse — Read-Only Query Enforcement**

Fires before every `Bash` command. Blocks database write operations (INSERT, UPDATE, DELETE, DROP, etc.) and enforces the `-readonly` flag on DuckDB invocations.

**PostToolUse — Automatic Validation**

Fires after every `Write` or `Edit` operation. When Claude writes a file to `outputs/drd/`, `outputs/hld/`, or `outputs/dms/`:

1. The hook script checks if the file is a DRD/HLD/DMS (`.md` in the outputs directory)
2. Runs the Python validator against the file
3. **CRITICAL issues** → blocks Claude and feeds errors back for auto-fix
4. **Warnings** → passed as non-blocking context
5. **Pass** → no interruption

### Versioning Convention

All inputs and outputs use **folder-based versioning** (`v1/`, `v2/`, etc.). The latest version folder is the source of truth for that component. Agents auto-discover the latest version via:

```bash
ls -d {path}/v* | sort -V | tail -1
```

### Input Documents

**BA Agent inputs** — `inputs/drd/v1/`:

| File | Contents |
|------|----------|
| `business_request.md` | Patient 360 business request from the CMO |
| `stakeholder_notes.md` | Interview notes from 5 stakeholders (CMO, CIO, Clinical Ops, Revenue Cycle, Physician) |
| `source_system_docs.md` | Synthea database schema (18 tables with column definitions) |
| `data_catalog.md` | Table inventory with row counts and sample queries |

**Architect Agent inputs** — `inputs/architect/v1/`:

| File | Contents |
|------|----------|
| `infrastructure-constraints.md` | Compute limits, storage format, networking, security, platform |
| `team-capabilities.md` | Language proficiency, pattern experience, skill gaps |
| `technology-catalog.md` | Approved tools with versions, roles, and licensing |

**Data Modeler Agent inputs** — `inputs/dms/v1/`:

| File | Contents |
|------|----------|
| `enterprise-naming-standards.md` | Table/column naming rules, schema organization, metadata columns, approved abbreviations |
| `data-governance-policies.md` | Data classification (PHI/PII), PHI handling rules, retention policies, RBAC, SCD policy guidelines |
| `enterprise-data-dictionary.md` | Approved data types, business entity definitions, derived columns, code systems, enumerations, null handling |

## Plugin Directory Structure

```
chapter-4/
├── .claude-plugin/
│   └── marketplace.json               # Local marketplace manifest
├── ba-plugin/                          # BA Agent plugin
│   ├── .claude-plugin/
│   │   └── plugin.json
│   ├── agents/
│   │   └── ba-agent.md
│   ├── skills/
│   │   ├── create-drd/
│   │   │   ├── SKILL.md
│   │   │   ├── DRD_template.j2
│   │   │   └── examples/
│   │   │       └── sample-drd.md
│   │   ├── update-drd/
│   │   │   └── SKILL.md
│   │   └── validate-drd/
│   │       ├── SKILL.md
│   │       └── scripts/
│   │           └── validate_drd.py
│   ├── hooks/
│   │   └── hooks.json
│   ├── memory/
│   └── scripts/
│       ├── validate-drd-hook.py
│       └── enforce-readonly-queries.py
├── architect-plugin/                   # Architect Agent plugin
│   ├── .claude-plugin/
│   │   └── plugin.json
│   ├── agents/
│   │   └── architect-agent.md
│   ├── skills/
│   │   ├── create-hld/
│   │   │   ├── SKILL.md
│   │   │   ├── HLD_template.j2
│   │   │   └── examples/
│   │   │       └── sample-hld.md
│   │   ├── update-hld/
│   │   │   └── SKILL.md
│   │   └── validate-hld/
│   │       ├── SKILL.md
│   │       └── scripts/
│   │           └── validate_hld.py
│   ├── hooks/
│   │   └── hooks.json
│   ├── memory/
│   └── scripts/
│       ├── validate-hld-hook.py
│       └── enforce-readonly-queries.py
├── data-modeler-plugin/                # Data Modeler Agent plugin
│   ├── .claude-plugin/
│   │   └── plugin.json
│   ├── agents/
│   │   └── data-modeler-agent.md
│   ├── skills/
│   │   ├── create-dms/
│   │   │   ├── SKILL.md
│   │   │   ├── DMS_template.j2
│   │   │   └── examples/
│   │   │       └── sample-dms.md
│   │   ├── update-dms/
│   │   │   └── SKILL.md
│   │   └── validate-dms/
│   │       ├── SKILL.md
│   │       └── scripts/
│   │           └── validate_dms.py
│   ├── hooks/
│   │   └── hooks.json
│   ├── memory/
│   └── scripts/
│       ├── validate-dms-hook.py
│       └── enforce-readonly-queries.py
├── inputs/
│   ├── drd/v1/                         # BA Agent inputs (versioned)
│   ├── architect/v1/                   # Architect Agent inputs (versioned)
│   └── dms/v1/                         # Data Modeler inputs (versioned)
├── outputs/
│   ├── drd/v1/                         # Generated DRDs (versioned)
│   ├── hld/v1/                         # Generated HLDs (versioned)
│   └── dms/v1/                         # Generated DMSs (versioned)
├── tests/                              # Unit tests (223 tests)
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

This runs 223 tests covering all three plugins: validators, validation hooks, read-only query enforcement, and agent definition structure.

### Run validators directly

```bash
cd chapter-4

# Validate a specific DRD
uv run python ba-plugin/skills/validate-drd/scripts/validate_drd.py outputs/drd/v1/DRD-2026-02-10-patient-360.md

# Validate a specific HLD
uv run python architect-plugin/skills/validate-hld/scripts/validate_hld.py outputs/hld/v1/HLD-2026-03-15-pipeline.md

# Validate a specific DMS
uv run python data-modeler-plugin/skills/validate-dms/scripts/validate_dms.py outputs/dms/v1/DMS-2026-03-16-patient-360.md

# Validate all DRDs/HLDs/DMSs
make validate-drd
make validate-hld
make validate-dms
```

### Test the plugin end-to-end

1. Start Claude Code from the repo root (`claude`)
2. Add marketplace: `/plugin marketplace add ./chapter-4`
3. Install plugins: `/plugin install ba-plugin@rdewai-plugins`, `/plugin install architect-plugin@rdewai-plugins`, `/plugin install data-modeler-plugin@rdewai-plugins`
4. Invoke the BA agent: `@ba-agent Create a DRD from inputs/drd/v1`
5. Answer the agent's clarifying questions until it confirms readiness
6. Verify a DRD was created in `outputs/drd/v1/`
7. Invoke the Architect agent: `@architect-plugin:architect-agent Create the HLD for the project`
8. Answer design decisions until the agent confirms readiness
9. Verify an HLD was created in `outputs/hld/v1/`
10. Invoke the Data Modeler agent: `@data-modeler-plugin:data-modeler-agent Create the DMS from the latest HLD`
11. Answer schema design questions until the agent confirms readiness
12. Verify a DMS was created in `outputs/dms/v1/`

### Debug plugin loading

```bash
claude --debug
```

## Updating the Plugins

After making changes to plugin files, reload:

```
/reload-plugins
```

Or uninstall and reinstall:

```
/plugin uninstall ba-plugin@rdewai-plugins
/plugin install ba-plugin@rdewai-plugins

/plugin uninstall architect-plugin@rdewai-plugins
/plugin install architect-plugin@rdewai-plugins

/plugin uninstall data-modeler-plugin@rdewai-plugins
/plugin install data-modeler-plugin@rdewai-plugins
```

## Makefile Targets

```bash
make help           # Show all commands
make dev-setup      # Install Python dependencies
make test           # Run all 223 tests
make validate-drd   # Validate all DRDs in outputs/
make validate-hld   # Validate all HLDs in outputs/
make validate-dms   # Validate all DMSs in outputs/
make lint           # Run ruff linter
make format         # Auto-format code
make clean          # Remove caches
```
