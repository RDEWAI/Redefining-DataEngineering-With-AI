# Chapter 4: Planning with Context — Multi-Agent Artifact Chain

Six Claude Code plugins that act as a **Business Analyst Agent**, **Data Architect Agent**, **Data Modeler Agent**, **Mapping Analyst Agent**, **DQ Engineer Agent**, and **Technical Lead Agent**, producing structured artifacts that feed the next role in the chain.

**Artifact chain**: DRD → **HLD** → **DMS** → **STM** → DQS → LLD

> **Story generation and downstream code implementation live in chapter-5.**
> The Scrum Master + Developer plugins (plus working copies of all six
> planning plugins) ship there; see `chapter-5/README.md`.

The use case is **Patient 360** — a unified patient search experience across Synthea healthcare data.

## Prerequisites

- [Claude Code](https://code.claude.com) CLI installed
- Python 3.10–3.12
- [UV](https://docs.astral.sh/uv/) package manager
- **openpyxl** — installed automatically via `make dev-setup` (required for STM Excel workbook generation)
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
/plugin install mapping-analyst-plugin@rdewai-plugins
/plugin install dq-engineer-plugin@rdewai-plugins
/plugin install technical-lead-plugin@rdewai-plugins
```

You can verify the install by running `/plugin` — you should see:

```
ba-plugin (v1.0.0)
  Skills: create-drd, update-drd, validate-drd, approve-drd
  Agents: ba-agent
  Hooks: PreToolUse, PostToolUse
  Status: Enabled

architect-plugin (v1.0.0)
  Skills: create-hld, update-hld, validate-hld, approve-hld
  Agents: architect-agent
  Hooks: PreToolUse, PostToolUse
  Status: Enabled

data-modeler-plugin (v1.0.0)
  Skills: create-dms, update-dms, validate-dms, approve-dms
  Agents: data-modeler-agent
  Hooks: PreToolUse, PostToolUse
  Status: Enabled

mapping-analyst-plugin (v1.0.0)
  Skills: create-stm, update-stm, validate-stm, approve-stm
  Agents: mapping-analyst-agent
  Hooks: PreToolUse, PostToolUse
  Status: Enabled

dq-engineer-plugin (v1.0.0)
  Skills: create-dqs, update-dqs, validate-dqs, generate-se-rules, approve-dqs
  Agents: dq-engineer-agent
  Hooks: PreToolUse, PostToolUse
  Status: Enabled

technical-lead-plugin (v1.0.0)
  Skills: create-lld, update-lld, validate-lld, generate-config-template, apply-learnings, approve-lld
  Agents: technical-lead-agent
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

### 7. Use the Mapping Analyst Agent

The Mapping Analyst Agent translates DMS schema definitions into column-level transformation specifications as an Excel workbook:

```
@mapping-analyst-plugin:mapping-analyst-agent Create the STM from the latest DMS
```

The agent will:
1. Discover the latest DMS, HLD, and mapping analyst input version folders automatically
2. Read DMS schemas, HLD layer specs, transformation standards, and code system mappings
3. Assess gaps across 8 STM sheets (Source-to-Bronze, Bronze-to-Silver, Silver-to-Gold, Code Systems, Null Handling, Edge Cases, Lineage)
4. Ask you transformation decisions via structured `AskUserQuestion` UI — one mapping layer at a time
5. Verify source table structures with read-only database queries (DESCRIBE, sample data, null rates)
6. Generate the STM as an **.xlsx Excel workbook** with 8 formatted sheets (bold headers, frozen panes, auto-filter, color-coded columns)
7. Validate automatically and fix any critical issues

**Note**: The STM output is `.xlsx` (Excel), not markdown. It uses **openpyxl** for generation and validation.

Other agent invocations:

```
@mapping-analyst-plugin:mapping-analyst-agent Update the STM with revised null handling rules
@mapping-analyst-plugin:mapping-analyst-agent Validate the STM at outputs/stm/v1/STM-2026-03-16-patient-360.xlsx
```

### 8. Use the DQ Engineer Agent

The DQ Engineer Agent translates STM transformation specifications into data quality rules and Spark-Expectations YAML files:

```
@dq-engineer-plugin:dq-engineer-agent Create the DQS from the latest STM
```

The agent will:
1. Discover the latest STM, DMS, DRD, and DQ engineer input version folders automatically
2. Read STM mappings, DMS schemas, DRD quality expectations, DQ standards, and SLA definitions
3. Assess gaps across 9 DQS sections (Field-Level Validations, Referential Integrity, Statistical Distribution, Reconciliation, etc.)
4. Ask you data quality decisions via structured `AskUserQuestion` UI — one rule category at a time
5. Verify source table structures with read-only database queries
6. Generate the DQS as markdown with embedded YAML rule blocks
7. Auto-generate per-table **Spark-Expectations YAML** files in `outputs/dqs/v{N}/se-rules/`
8. Validate automatically and fix any critical issues

**Note**: The DQS produces **dual output** — a markdown specification plus machine-readable SE YAML rule files (one per target table), compatible with spark-expectations >= 2.6.0.

Other agent invocations:

```
@dq-engineer-plugin:dq-engineer-agent Update the DQS with revised null rate thresholds
@dq-engineer-plugin:dq-engineer-agent Validate the DQS at outputs/dqs/v1/DQS-2026-03-20-patient-360.md
```

### 9. Use the Technical Lead Agent

The Technical Lead Agent translates all upstream artifacts into a Low-Level Design with config templates, DAG definitions, and implementation sequence:

```
@technical-lead-plugin:technical-lead-agent Create the LLD for the project
```

The agent will:
1. Discover all 5 upstream artifacts (DRD, HLD, DMS, STM, DQS) and technical lead input version folders automatically
2. Read development standards, infrastructure specs, and orchestration patterns
3. Assess gaps across 12 LLD sections (Module Design, DAG Orchestration, Config Management, Error Handling, etc.)
4. Ask you implementation decisions via structured `AskUserQuestion` UI — one section at a time
5. Generate the LLD as a **hub document** that references upstream artifacts by section number
6. Auto-generate 3 derived artifacts: **config template** (from §7), **DAG definition YAML + Mermaid diagram** (from §4), and **implementation sequence** (from §2/§4/§9/§12)
7. Validate automatically and fix any critical issues

**Note**: The LLD is a hub document — it references upstream artifacts instead of duplicating content. The `create-lld` workflow auto-generates config, DAG, and implementation sequence as separate files.

Other agent invocations:

```
@technical-lead-plugin:technical-lead-agent Update the LLD with revised error handling strategy
@technical-lead-plugin:technical-lead-agent Validate the LLD at outputs/lld/v1/LLD-2026-03-22-patient-360.md
```

### 10. Use skills directly (alternative)

You can also invoke skills directly without the agent wrapper. Make sure you have `data/duckdb/raw.db` already created.

```
/create-drd inputs/drd/v1
/create-hld outputs/drd/v1/DRD-2026-02-11-patient-360.md
```

Other skills:

```
/update-drd outputs/drd/v1/DRD-2026-02-10-patient-360.md
/validate-drd outputs/drd/v1/DRD-2026-02-10-patient-360.md
/approve-drd outputs/drd/v1/DRD-2026-02-10-patient-360.md
/update-hld outputs/hld/v1/HLD-2026-03-15-pipeline.md
/validate-hld outputs/hld/v1/HLD-2026-03-15-pipeline.md
/architect-plugin:approve-hld outputs/hld/v1/HLD-2026-03-15-pipeline.md
/data-modeler-plugin:create-dms
/data-modeler-plugin:update-dms outputs/dms/v1/DMS-2026-03-16-patient-360.md
/data-modeler-plugin:validate-dms outputs/dms/v1/DMS-2026-03-16-patient-360.md
/data-modeler-plugin:approve-dms outputs/dms/v1/DMS-2026-03-16-patient-360.md
/mapping-analyst-plugin:create-stm
/mapping-analyst-plugin:update-stm outputs/stm/v1/STM-2026-03-16-patient-360.xlsx
/mapping-analyst-plugin:validate-stm outputs/stm/v1/STM-2026-03-16-patient-360.xlsx
/mapping-analyst-plugin:approve-stm outputs/stm/v1/STM-2026-03-16-patient-360.xlsx
/dq-engineer-plugin:create-dqs
/dq-engineer-plugin:update-dqs outputs/dqs/v1/DQS-2026-03-20-patient-360.md
/dq-engineer-plugin:validate-dqs outputs/dqs/v1/DQS-2026-03-20-patient-360.md
/dq-engineer-plugin:generate-se-rules outputs/dqs/v1/DQS-2026-03-20-patient-360.md
/dq-engineer-plugin:approve-dqs outputs/dqs/v1/DQS-2026-03-20-patient-360.md
/technical-lead-plugin:create-lld
/technical-lead-plugin:update-lld outputs/lld/v1/LLD-2026-03-22-patient-360.md
/technical-lead-plugin:validate-lld outputs/lld/v1/LLD-2026-03-22-patient-360.md
/technical-lead-plugin:generate-config-template outputs/lld/v1/LLD-2026-03-22-patient-360.md
/technical-lead-plugin:approve-lld outputs/lld/v1/LLD-2026-03-22-patient-360.md
```

## How the Plugins Work

### BA Agent

The `ba-agent` sub-agent (`ba-plugin/agents/ba-agent.md`) embodies the Business/Data Analyst role with:

- **Requirements Elicitation Protocol** — asks structured questions section-by-section using `AskUserQuestion`, iterating until all DRD sections have specific, measurable requirements
- **Source Exploration** — runs read-only DuckDB queries to verify table existence, row counts, column types, and null rates against what input documents claim
- **Pitfall Prevention** — rejects vague requirements ("all data", "real-time", "fast"), never skips source exploration, prevents gold-plating
- **Session Memory** — writes notes to `memory/drd/` after each engagement

### Architect Agent

The `architect-agent` sub-agent (`architect-plugin/agents/architect-agent.md`) embodies the Data Architect role with:

- **Architecture Elicitation Protocol** — asks design decisions section-by-section using `AskUserQuestion`, covering pattern selection, technology choices, layer design, and capacity planning
- **Database Gate** — verifies actual data volumes with read-only queries before generating capacity plans; blocks HLD generation if the database is inaccessible
- **Decision Documentation** — every pattern choice, technology selection, and layer design requires Options Considered, Rationale, and Trade-off analysis
- **DRD Traceability** — every design decision must cite the DRD section it satisfies
- **Session Memory** — writes notes to `memory/hld/` after each engagement

### Data Modeler Agent

The `data-modeler-agent` sub-agent (`data-modeler-plugin/agents/data-modeler-agent.md`) embodies the Data Modeler role with:

- **Schema Elicitation Protocol** — asks schema design decisions section-by-section using `AskUserQuestion`, covering bronze/silver/gold schemas, SCD strategies, naming conventions, and physical design
- **Database Gate** — queries actual source table structures (DESCRIBE, sample data, null rates) before designing schemas; blocks DMS generation if the database is inaccessible
- **Dual-Format Output** — generates markdown narrative with embedded YAML schema blocks that downstream agents (Mapping Engineer, DQ Engineer) can parse programmatically
- **Enterprise Standards** — applies naming conventions, governance policies, and data dictionary from `inputs/dms/v1/` (PHI handling, approved types, enumeration standards)
- **HLD Traceability** — every schema decision must cite the HLD layer specification it implements
- **Session Memory** — writes notes to `memory/dms/` after each engagement

### Mapping Analyst Agent

The `mapping-analyst-agent` sub-agent (`mapping-analyst-plugin/agents/mapping-analyst-agent.md`) embodies the Mapping Analyst role with:

- **Mapping Elicitation Protocol** — asks transformation decisions layer-by-layer using `AskUserQuestion`, covering source-to-bronze pass-through, bronze-to-silver cleansing, silver-to-gold aggregations, and edge cases
- **Database Gate** — queries actual source table structures (DESCRIBE, sample data, null rates) before specifying transformations; blocks STM generation if the database is inaccessible
- **Excel Output** — generates `.xlsx` workbooks using **openpyxl** with 8 sheets (Summary, Source-to-Bronze, Bronze-to-Silver, Silver-to-Gold, Code Systems, Null Handling, Edge Cases, Lineage), formatted with bold headers, frozen panes, auto-filter, and color-coded columns
- **DMS Traceability** — every transformation must cite the DMS schema section it implements
- **Session Memory** — writes notes to `memory/stm/` after each engagement

### DQ Engineer Agent

The `dq-engineer-agent` sub-agent (`dq-engineer-plugin/agents/dq-engineer-agent.md`) embodies the DQ Engineer role with:

- **Quality Rule Elicitation Protocol** — asks data quality decisions category-by-category using `AskUserQuestion`, covering field-level validations, referential integrity, statistical distribution, and reconciliation rules
- **Database Gate** — queries actual source table structures before specifying quality thresholds; blocks DQS generation if the database is inaccessible
- **Dual Output** — generates markdown DQS specification plus per-table **Spark-Expectations YAML** files compatible with spark-expectations >= 2.6.0
- **Four DQS Responsibilities** — every DQS covers field-level validations (NOT NULL, FORMAT, RANGE, ENUM), referential integrity (FK checks), statistical distribution (baselines, null rates), and reconciliation (source-to-target comparisons)
- **STM/DMS Traceability** — every quality rule must cite the STM transformation or DMS schema it validates
- **Session Memory** — writes notes to `memory/dqs/` after each engagement

### Technical Lead Agent

The `technical-lead-agent` sub-agent (`technical-lead-plugin/agents/technical-lead-agent.md`) embodies the Technical Lead role with:

- **Implementation Elicitation Protocol** — asks implementation decisions section-by-section using `AskUserQuestion`, covering module design, DAG orchestration, config management, error handling, testing strategy, and deployment
- **Hub Document Pattern** — generates the LLD as a reference hub that cites upstream artifacts (DRD, HLD, DMS, STM, DQS) by section number instead of duplicating content
- **Derived Artifact Generation** — auto-generates 3 additional artifacts from the LLD: config template YAML (from §7), DAG definition YAML + Mermaid diagram (from §4), and implementation sequence (from §2/§4/§9/§12)
- **All-Upstream Traceability** — every design decision must cite the upstream artifact section it implements
- **Session Memory** — writes notes to `memory/lld/` after each engagement

### Skills

| Plugin | Skill | What it does |
|--------|-------|-------------|
| ba-plugin | `create-drd` | Reads input documents, generates a complete DRD following a Jinja2 template |
| ba-plugin | `update-drd` | Copies existing DRD, applies incremental edits (Edit-only, no Write) |
| ba-plugin | `validate-drd` | Runs 15 validation checks (CRITICAL / WARNING / INFO) on a DRD |
| ba-plugin | `approve-drd` | Sets DRD status to Approved — gate for downstream creation |
| architect-plugin | `create-hld` | Reads DRD + architect inputs, generates a complete HLD (requires DRD approved) |
| architect-plugin | `update-hld` | Copies existing HLD, applies incremental edits (Edit-only) |
| architect-plugin | `validate-hld` | Runs validation checks on an HLD (sections, traceability, tech table, CDC, capacity) |
| architect-plugin | `approve-hld` | Sets HLD status to Approved |
| data-modeler-plugin | `create-dms` | Reads HLD + DRD + enterprise standards, generates a complete DMS (requires DRD+HLD approved) |
| data-modeler-plugin | `update-dms` | Copies existing DMS, applies incremental edits (Edit-only) |
| data-modeler-plugin | `validate-dms` | Runs validation checks on a DMS (sections, YAML syntax, SCD types, traceability) |
| data-modeler-plugin | `approve-dms` | Sets DMS status to Approved |
| mapping-analyst-plugin | `create-stm` | Reads DMS + HLD + transformation standards, generates STM .xlsx (requires DRD+HLD+DMS approved) |
| mapping-analyst-plugin | `update-stm` | Copies existing STM, applies changes via openpyxl |
| mapping-analyst-plugin | `validate-stm` | Runs 15 validation checks on an STM .xlsx (sheets, headers, traceability, formatting) |
| mapping-analyst-plugin | `approve-stm` | Sets STM status to Approved |
| dq-engineer-plugin | `create-dqs` | Reads STM + DMS + DRD + DQ standards, generates DQS + SE YAML (requires DRD+DMS+STM approved) |
| dq-engineer-plugin | `update-dqs` | Copies existing DQS, applies incremental edits (Edit-only) |
| dq-engineer-plugin | `validate-dqs` | Runs validation checks on a DQS (sections, YAML syntax, rule categories, traceability) |
| dq-engineer-plugin | `generate-se-rules` | Converts DQS rules to per-table Spark-Expectations YAML files |
| dq-engineer-plugin | `approve-dqs` | Sets DQS status to Approved |
| technical-lead-plugin | `create-lld` | Reads all 5 upstream artifacts + tech lead inputs, generates LLD + derived artifacts (requires all 5 approved) |
| technical-lead-plugin | `update-lld` | Copies existing LLD, applies incremental edits (Edit-only) |
| technical-lead-plugin | `validate-lld` | Runs validation checks on an LLD (sections, artifact references, DAG syntax) |
| technical-lead-plugin | `generate-config-template` | Generates environment config YAML from LLD §7 |
| technical-lead-plugin | `approve-lld` | Sets LLD status to Approved |

### Hooks

All six plugins register two hooks each:

**PreToolUse — Read-Only Query Enforcement**

Fires before every `Bash` command. Blocks database write operations (INSERT, UPDATE, DELETE, DROP, etc.) and enforces the `-readonly` flag on DuckDB invocations.

**PostToolUse — Automatic Validation**

Fires after every `Write` or `Edit` operation. When Claude writes a file to `outputs/drd/`, `outputs/hld/`, `outputs/dms/`, `outputs/stm/`, `outputs/dqs/`, or `outputs/lld/`:

1. The hook script checks if the file is a DRD/HLD/DMS/DQS/LLD (`.md`) or STM (`.xlsx`) in the outputs directory
2. Runs the Python validator against the file
3. **CRITICAL issues** → blocks Claude and feeds errors back for auto-fix
4. **Warnings** → passed as non-blocking context
5. **Pass** → no interruption

### Versioning & Approval Workflow

All inputs and outputs use **folder-based versioning** (`v1/`, `v2/`, etc.). The latest version folder is the source of truth for that component. Agents auto-discover the latest version via:

```bash
ls -d {path}/v* | sort -V | tail -1
```

#### Update Versioning (3 Scenarios)

When any `update-*` skill is invoked:

| Scenario | Trigger | Action |
|----------|---------|--------|
| **A. Cross-version** | `inputs/{role}/v{N+1}/` exists or user says "new version" | Copy to `v{N+1}/` with today's date, `.bak` old, set version `{N+1}.0` |
| **B. Same version, new date** | Artifact date ≠ today | Copy with today's date, `.bak` old, bump minor version |
| **C. Same version, same date** | Artifact date = today (re-run) | Edit in-place, bump minor version |

Updates use the **Edit** tool only (never Write) for incremental changes. One active artifact file per version folder — old files become `.bak`.

#### Status Lifecycle

```
Draft  →  Updated - Pending Review  →  Approved
```

Each plugin has an `approve-{artifact}` skill that sets Status to `Approved`.

#### Upstream Approval Gate

Before creating a downstream artifact, ALL required upstream artifacts MUST have `Status: Approved`:

| create-* Skill | Required Approved Upstream |
|---|---|
| create-drd | None (first in chain) |
| create-hld | DRD |
| create-dms | DRD, HLD |
| create-stm | DRD, HLD, DMS |
| create-dqs | DRD, DMS, STM |
| create-lld | DRD, HLD, DMS, STM, DQS |

If any upstream artifact is not `Approved`, the create skill stops and informs the user which artifacts need approval. This gate has no override.

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

**Mapping Analyst Agent inputs** — `inputs/stm/v1/`:

| File | Contents |
|------|----------|
| `transformation-standards.md` | Idempotency rules, type casting, null handling conventions, dedup rules, string standardization, date/time standards, surrogate key generation, SCD merge patterns |
| `code-system-mappings.md` | SNOMED-CT, RxNorm, LOINC codes for Patient 360, encounter/gender enumerations, CASE expression templates |

**DQ Engineer Agent inputs** — `inputs/dqs/v1/`:

| File | Contents |
|------|----------|
| `dq-standards.md` | Severity definitions, threshold defaults, rule naming conventions |
| `sla-definitions.md` | Consumer freshness requirements, availability targets |
| `se-config-template.yaml` | Spark-Expectations environment configuration template |

**Technical Lead Agent inputs** — `inputs/lld/v1/`:

| File | Contents |
|------|----------|
| `development-standards.md` | Coding standards, branching strategy, PR conventions |
| `infrastructure-specs.md` | Compute specs, storage layout, networking, monitoring |
| `orchestration-patterns.md` | DAG design patterns, retry policies, alerting conventions |

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
├── mapping-analyst-plugin/                # Mapping Analyst Agent plugin
│   ├── .claude-plugin/
│   │   └── plugin.json
│   ├── agents/
│   │   └── mapping-analyst-agent.md
│   ├── skills/
│   │   ├── create-stm/
│   │   │   ├── SKILL.md
│   │   │   └── examples/
│   │   │       ├── sample-stm.py         # Generates sample-stm.xlsx
│   │   │       └── sample-stm.xlsx
│   │   ├── update-stm/
│   │   │   └── SKILL.md
│   │   └── validate-stm/
│   │       ├── SKILL.md
│   │       └── scripts/
│   │           └── validate_stm.py
│   ├── hooks/
│   │   └── hooks.json
│   ├── memory/
│   └── scripts/
│       ├── validate-stm-hook.py
│       └── enforce-readonly-queries.py
├── dq-engineer-plugin/                    # DQ Engineer Agent plugin
│   ├── .claude-plugin/
│   │   └── plugin.json
│   ├── agents/
│   │   └── dq-engineer-agent.md
│   ├── skills/
│   │   ├── create-dqs/
│   │   │   ├── SKILL.md
│   │   │   ├── DQS_template.j2
│   │   │   └── examples/
│   │   │       └── sample-dqs.md
│   │   ├── update-dqs/
│   │   │   └── SKILL.md
│   │   ├── validate-dqs/
│   │   │   ├── SKILL.md
│   │   │   └── scripts/
│   │   │       └── validate_dqs.py
│   │   └── generate-se-rules/
│   │       ├── SKILL.md
│   │       ├── scripts/
│   │       │   └── generate_se_rules.py
│   │       └── examples/
│   │           └── sample-se-rules/
│   ├── hooks/
│   │   └── hooks.json
│   └── scripts/
│       ├── validate-dqs-hook.py
│       └── enforce-readonly-queries.py
├── technical-lead-plugin/                 # Technical Lead Agent plugin
│   ├── .claude-plugin/
│   │   └── plugin.json
│   ├── agents/
│   │   └── technical-lead-agent.md
│   ├── skills/
│   │   ├── create-lld/
│   │   │   ├── SKILL.md
│   │   │   ├── LLD_template.j2
│   │   │   ├── scripts/
│   │   │   │   ├── generate_dag_definition.py
│   │   │   │   └── generate_impl_sequence.py
│   │   │   └── examples/
│   │   │       ├── sample-lld.md
│   │   │       ├── sample-dag-definition.yaml
│   │   │       ├── sample-dag-pipeline.mmd
│   │   │       └── sample-impl-sequence.md
│   │   ├── update-lld/
│   │   │   └── SKILL.md
│   │   ├── validate-lld/
│   │   │   ├── SKILL.md
│   │   │   └── scripts/
│   │   │       └── validate_lld.py
│   │   ├── generate-config-template/
│   │   │   ├── SKILL.md
│   │   │   ├── scripts/
│   │   │   │   └── generate_config_template.py
│   │   │   └── examples/
│   │   │       └── sample-config-template.yaml
│   │   └── apply-learnings/
│   │       └── SKILL.md
│   ├── hooks/
│   │   └── hooks.json
│   └── scripts/
│       ├── validate-lld-hook.py
│       └── enforce-readonly-queries.py
├── inputs/
│   ├── drd/v1/                         # BA Agent inputs (versioned)
│   ├── architect/v1/                   # Architect Agent inputs (versioned)
│   ├── dms/v1/                         # Data Modeler inputs (versioned)
│   ├── stm/v1/                         # Mapping Analyst inputs (versioned)
│   ├── dqs/v1/                         # DQ Engineer inputs (versioned)
│   └── lld/v1/                         # Technical Lead inputs (versioned)
├── outputs/
│   ├── drd/v1/                         # Generated DRDs (versioned)
│   ├── hld/v1/                         # Generated HLDs (versioned)
│   ├── dms/v1/                         # Generated DMSs (versioned)
│   ├── stm/v1/                         # Generated STM Excel workbooks (versioned)
│   ├── dqs/v1/                         # Generated DQS + SE YAML rules (versioned)
│   └── lld/v1/                         # Generated LLD + config + DAG + impl sequence (versioned)
├── memory/                             # Session memory (cross-session persistence)
│   ├── drd/                            # BA Agent session notes + learnings
│   ├── hld/                            # Architect session notes + learnings
│   ├── dms/                            # Data Modeler session notes + learnings
│   ├── stm/                            # Mapping Analyst session notes + learnings
│   ├── dqs/                            # DQ Engineer session notes + learnings
│   └── lld/                            # Technical Lead session notes + learnings
├── tests/                              # Unit tests
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

This runs all tests covering all six plugins: validators, validation hooks, read-only query enforcement, agent definition structure, and derived artifact generators.

### Run validators directly

```bash
cd chapter-4

# Validate a specific DRD
uv run python ba-plugin/skills/validate-drd/scripts/validate_drd.py outputs/drd/v1/DRD-2026-02-10-patient-360.md

# Validate a specific HLD
uv run python architect-plugin/skills/validate-hld/scripts/validate_hld.py outputs/hld/v1/HLD-2026-03-15-pipeline.md

# Validate a specific DMS
uv run python data-modeler-plugin/skills/validate-dms/scripts/validate_dms.py outputs/dms/v1/DMS-2026-03-16-patient-360.md

# Validate a specific STM (.xlsx)
uv run python mapping-analyst-plugin/skills/validate-stm/scripts/validate_stm.py outputs/stm/v1/STM-2026-03-16-patient-360.xlsx

# Validate a specific DQS
uv run python dq-engineer-plugin/skills/validate-dqs/scripts/validate_dqs.py outputs/dqs/v1/DQS-2026-03-20-patient-360.md

# Validate a specific LLD
uv run python technical-lead-plugin/skills/validate-lld/scripts/validate_lld.py outputs/lld/v1/LLD-2026-03-22-patient-360.md

# Validate all artifacts
make validate-drd
make validate-hld
make validate-dms
make validate-stm
make validate-dqs
make validate-lld
```

### Test the plugin end-to-end

1. Start Claude Code from the repo root (`claude`)
2. Add marketplace: `/plugin marketplace add ./chapter-4`
3. Install plugins: `/plugin install ba-plugin@rdewai-plugins`, `/plugin install architect-plugin@rdewai-plugins`, `/plugin install data-modeler-plugin@rdewai-plugins`, `/plugin install mapping-analyst-plugin@rdewai-plugins`, `/plugin install dq-engineer-plugin@rdewai-plugins`, `/plugin install technical-lead-plugin@rdewai-plugins`
4. Invoke the BA agent: `@ba-agent Create a DRD from inputs/drd/v1`
5. Answer the agent's clarifying questions until it confirms readiness
6. Verify a DRD was created in `outputs/drd/v1/`
7. Invoke the Architect agent: `@architect-plugin:architect-agent Create the HLD for the project`
8. Answer design decisions until the agent confirms readiness
9. Verify an HLD was created in `outputs/hld/v1/`
10. Invoke the Data Modeler agent: `@data-modeler-plugin:data-modeler-agent Create the DMS from the latest HLD`
11. Answer schema design questions until the agent confirms readiness
12. Verify a DMS was created in `outputs/dms/v1/`
13. Invoke the Mapping Analyst agent: `@mapping-analyst-plugin:mapping-analyst-agent Create the STM from the latest DMS`
14. Answer transformation mapping questions until the agent confirms readiness
15. Verify an STM `.xlsx` workbook was created in `outputs/stm/v1/`
16. Invoke the DQ Engineer agent: `@dq-engineer-plugin:dq-engineer-agent Create the DQS from the latest STM`
17. Answer data quality rule questions until the agent confirms readiness
18. Verify a DQS was created in `outputs/dqs/v1/` and SE YAML files in `outputs/dqs/v1/se-rules/`
19. Invoke the Technical Lead agent: `@technical-lead-plugin:technical-lead-agent Create the LLD for the project`
20. Answer implementation design questions until the agent confirms readiness
21. Verify an LLD was created in `outputs/lld/v1/` with config, DAG, and impl-sequence files

For sprint-backlog generation + code implementation, continue in
`chapter-5/` — it ships a self-contained workspace with the Scrum Master
and Developer plugins that consume the approved artifacts from here.

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

/plugin uninstall mapping-analyst-plugin@rdewai-plugins
/plugin install mapping-analyst-plugin@rdewai-plugins

/plugin uninstall dq-engineer-plugin@rdewai-plugins
/plugin install dq-engineer-plugin@rdewai-plugins

/plugin uninstall technical-lead-plugin@rdewai-plugins
/plugin install technical-lead-plugin@rdewai-plugins
```

## Makefile Targets

```bash
make help           # Show all commands
make dev-setup      # Install Python dependencies
make test           # Run all tests
make validate-drd   # Validate all DRDs in outputs/drd/
make validate-hld   # Validate all HLDs in outputs/hld/
make validate-dms   # Validate all DMSs in outputs/dms/
make validate-stm   # Validate all STMs (.xlsx) in outputs/stm/
make validate-dqs   # Validate all DQSs in outputs/dqs/
make validate-lld       # Validate all LLDs in outputs/lld/
make lint               # Run ruff linter
make format             # Auto-format code
make clean              # Remove caches
```
