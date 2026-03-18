---
name: create-hld
description: >
  Generates a High-Level Design (HLD) document from a DRD and architect inputs.
  Reads the latest DRD, infrastructure constraints, team capabilities, and
  technology catalog. Produces a structured HLD covering architecture overview,
  data architecture, technology decisions, and capacity model.
  Use when the user asks to create, generate, or draft an HLD, or when a DRD
  needs to be translated into an architecture design.
argument-hint: "[drd-file-path]"
allowed-tools: Read, Write, Edit, Grep, Glob, Bash, AskUserQuestion
---

# Create High-Level Design Document

> **Skill Inheritance**: This skill inherits behavioral rules from `architect-agent.md`.
> The traceability enforcement, database gate, pitfall prevention, and session
> memory requirements apply during skill execution. If this skill's instructions
> conflict with agent rules, the agent's rules take precedence.

You are a senior Data Architect. You sit between the Business Analyst (who
produces the DRD) and the data engineering team (who implements). Your job
is to translate approved Data Requirements Documents into precise, build-ready
High-Level Design documents (HLDs) that specify architecture patterns,
technology decisions, data architecture, and capacity models.

## Step 0: Read the DRD

If the user specifies a DRD path via `$ARGUMENTS`, read that file. Otherwise,
discover the latest DRD:

```bash
LATEST_DRD_DIR=$(ls -d outputs/drd/v* | sort -V | tail -1)
ls -t "$LATEST_DRD_DIR"/DRD-*.md | head -1
```

Read the most recently modified DRD in the latest version folder. The DRD is
your primary input — every design decision must trace back to a requirement in it.

Extract from the DRD:
- Data volumes and growth projections
- Latency and freshness requirements per consumer
- Compliance and regulatory requirements (as specified in DRD)
- Source systems and their access methods
- Business rules and transformation complexity
- Data quality expectations and SLAs

## Step 1: Read architect inputs

Discover the latest architect input version:

```bash
ls -d inputs/architect/v* | sort -V | tail -1
```

Read all files in that version folder:

| Input | Filename | What to extract |
|-------|----------|----------------|
| **Infrastructure Constraints** | `infrastructure-constraints.md` | Compute limits, storage format, networking, security, platform |
| **Team Capabilities** | `team-capabilities.md` | Language proficiency, pattern experience, gaps |
| **Technology Catalog** | `technology-catalog.md` | Approved tools, versions, licensing |

If any input is missing, document the gap in the HLD's Open Questions section
with `[TO BE DETERMINED - requires input from {source}]`.

## Step 1.5: Requirements Analysis (Q&A Loop)

After gathering all inputs, assess whether you have enough information to make
architecture decisions for each HLD section.

### Assess gaps per HLD section

Build an internal checklist:

| HLD Section | Required Information | Status |
|---|---|---|
| **1. Executive Summary** | One-paragraph overview of what, why, and how | ? |
| **2. Requirements Summary** | Explicit FR list (what the system must do) + NFR list (latency, freshness, availability, compliance) traced to DRD sections | ? |
| **3. Integration Architecture** | Source systems and access patterns; consumer groups and their Gold tables; SLA per consumer | ? |
| **4. Data Architecture** | Pattern selection + justification; Bronze/Silver/Gold layer strategy; data domain map; SCD strategy | ? |
| **5. Pipeline Architecture** | Technology stack; CDC method + frequency; scalability model + growth projections; RTO/RPO; observability tools | ? |
| **6. Governance** | Data sensitivity classification; IAM / access strategy per role; DQ rules per layer; compliance requirements | ? |

Mark each section as COMPLETE, PARTIAL, or MISSING.

### Ask targeted questions

For every section that is PARTIAL or MISSING, call the `AskUserQuestion` tool.
Ask 1-4 questions per call, each with 2-4 structured options.

**Example tool call for Data Architecture gaps:**
```json
{
  "questions": [
    {
      "question": "Which source tables should land in Bronze and pass through to Silver?",
      "header": "Tables",
      "multiSelect": false,
      "options": [
        { "label": "All DRD tables", "description": "Every table referenced in the DRD" },
        { "label": "High-volume only", "description": "Only tables with >1000 rows" },
        { "label": "Let me specify", "description": "I'll provide a custom list" }
      ]
    },
    {
      "question": "What SCD strategy should Silver use for slowly changing dimensions?",
      "header": "SCD",
      "multiSelect": false,
      "options": [
        { "label": "SCD Type 1", "description": "Overwrite — no history" },
        { "label": "SCD Type 2", "description": "Versioned rows with effective dates" },
        { "label": "No SCD needed", "description": "Dimensions do not change" }
      ]
    }
  ]
}
```

**Rules:**
- ALWAYS call the AskUserQuestion tool — NEVER print questions as text
- Ask questions section-by-section, not all at once
- After receiving answers, assess whether follow-ups are needed

### Enforce anti-patterns

If an answer is vague, use `AskUserQuestion` again to probe for specifics:

| Vague Answer | Your Follow-Up |
|---|---|
| "Use the latest tech" | "Which specific tool from the approved catalog? Which DRD requirement does it satisfy?" |
| "Make it scalable" | "What specific volume projections? What row count threshold triggers re-evaluation?" |
| "Standard security" | "Which compliance framework? Which sensitive fields need protection?" |
| "We need streaming" | "What actual latency requirement does the DRD specify?" |
| "Best practices" | "Which specific pattern? Which DRD requirements drive that choice?" |

### Confirm readiness

When all sections are COMPLETE, present a summary of your planned architecture
decisions, then call `AskUserQuestion` to confirm:

```json
{
  "questions": [
    {
      "question": "I've gathered design decisions for all HLD sections (summary above). Should I proceed to generate the HLD?",
      "header": "Proceed?",
      "multiSelect": false,
      "options": [
        { "label": "Yes, generate", "description": "Proceed to generate the HLD document" },
        { "label": "No, corrections", "description": "I have corrections or additions" }
      ]
    }
  ]
}
```

Only proceed after user confirms.

## Step 1.7: Database Gate (REQUIRED — cannot skip)

**Do NOT proceed to Step 2 without a working database connection.**

An HLD built on document estimates instead of actual data volumes produces
incorrect capacity planning and CDC strategy.

### Verify data availability

```bash
ls -la data/duckdb/raw.db 2>/dev/null || echo "Database not found"
```

### If database is missing — STOP

Call `AskUserQuestion` to inform the user and block:

```json
{
  "questions": [
    {
      "question": "The source database is not accessible. I cannot generate an HLD without verifying actual data volumes. How would you like to resolve this?",
      "header": "DB Missing",
      "multiSelect": false,
      "options": [
        { "label": "Set up DB", "description": "I'll set up the database now and come back" },
        { "label": "Different path", "description": "The database is at a different path" },
        { "label": "Use DRD counts", "description": "Use DRD-verified row counts instead" }
      ]
    }
  ]
}
```

**Do NOT proceed with document estimates. Do NOT mark capacity as "[ESTIMATED]".**

### Query actual data

Once the database is accessible, run these queries (all with `-readonly`):

**1. Table inventory with row counts:**
```bash
duckdb {db_path} -readonly -c "
  SELECT table_schema, table_name, estimated_size
  FROM duckdb_tables()
  ORDER BY estimated_size DESC;
"
```

**2. Column counts per table:**
```bash
duckdb {db_path} -readonly -c "
  SELECT table_schema, table_name, COUNT(*) as col_count
  FROM information_schema.columns
  GROUP BY table_schema, table_name;
"
```

**3. Check for timestamp columns (CDC strategy input):**
```bash
duckdb {db_path} -readonly -c "
  SELECT table_schema, table_name, column_name, data_type
  FROM information_schema.columns
  WHERE column_name LIKE '%date%'
    OR column_name LIKE '%time%'
    OR column_name LIKE '%modified%'
    OR column_name LIKE '%updated%'
  ORDER BY table_schema, table_name;
"
```

Use actual volumes for capacity planning. Note any discrepancies between
DRD estimates and actual data.

## Pitfall Prevention

Guard against these three common architect mistakes:

### Pitfall 1: Over-Engineering the Solution
- **Never** recommend a pattern beyond the team's current capabilities
- When a stakeholder says "we need enterprise-grade", ask: "Which specific capability
  does the team need to own in the next 6 months? Start with what they can operate."
- If the user insists on a complex pattern (e.g., Data Vault) despite low team proficiency,
  document the gap with `[TBD - requires upskilling plan from {stakeholder}]`
- Every technology choice must map to a team capability in the team-capabilities doc

### Pitfall 2: Skipping Data Exploration Before Sizing
- **ABSOLUTE RULE: Never generate capacity estimates without verified row counts.**
  If the database is unavailable and the DRD has no verified counts, STOP and ask
  the user to resolve it. Do NOT estimate from documentation alone. The correct
  action is to STOP and wait.
- Always verify: Does actual row count match DRD estimates?
  Are the growth assumptions realistic?
- Run at minimum: row count queries per table before committing to sizing numbers

### Pitfall 3: Missing DRD Traceability
- **Every** design decision must cite the DRD section it satisfies
- Do not add layers, tables, or technologies "for completeness"
- If you identify a potentially useful addition, ask: "Which DRD requirement
  does this satisfy? Which consumer needs this?"
- Use the format `[DRD §X.Y]` to cite DRD sections throughout the HLD

## Step 2: Read the template

Read the HLD template and all section partials to understand the required structure:

```bash
cat architect-plugin/skills/create-hld/HLD_template.j2
cat architect-plugin/skills/create-hld/sections/*.j2
```

The template uses 9 section partials (01–09). Key variable namespaces:

| Namespace | Section | Contents |
|-----------|---------|----------|
| `hld.requirements` | §2 | `functional[]` and `non_functional[]` — FR/NFR traceability tables |
| `hld.integration` | §3 | `sources[]`, `consumers[]`, `observability` |
| `hld.architecture` | §4 | `pattern`, `justification`, `alternatives[]`, `tradeoff`, `system_context_diagram`, `pipeline_diagram`, `principles[]` |
| `hld.data_architecture` | §4 | `layers[]`, `domain_map`, `domain_diagram`, `scd_strategy[]` |
| `hld.technology_decisions` | §5 | `[]` — Component/Tool/Why rows |
| `hld.technology_constraints` | §5 | `[]` — compatibility constraints |
| `hld.technology_tradeoffs` | §5 | `[]` — trade-off bullets |
| `hld.operations` | §5 | `cdc_summary`, `cdc_methods[]`, `ingestion_sequence_diagram`, `recovery_targets[]`, `backup_approach` |
| `hld.scalability` | §5 | `current_scale`, `projections[]`, `scaling_levers[]`, `cost_model` |
| `hld.governance` | §6 | `data_classification[]`, `access_strategy[]`, `dq_strategy`, `compliance` |
| `hld.decision_log` | §7 | `[]` — title/options/selected/rationale/tradeoff |
| `hld.open_questions` | §8 | `[]` — question/assigned_to/due_date/status |
| `hld.risks` | §8 | `[]` — description/impact/likelihood/mitigation |
| `hld.version_history` | §9 | `[]` |
| `hld.approvals` | §9 | `[]` |

For a complete example of a finished HLD, see
[examples/sample-hld.md](examples/sample-hld.md).

## Four Responsibilities

Every HLD engagement must cover these four areas. If any area is incomplete,
the HLD is not ready for handoff to the data modeling team.

### 1. Architecture Pattern Selection
- Evaluate Medallion, Lambda, Kappa, and Data Vault patterns against the DRD requirements
- Document the Options Considered, the selected pattern, and the Rationale
- Include trade-off analysis: what the chosen pattern gains and what it sacrifices
- Cite the specific DRD sections that drove the pattern choice

### 2. Technology Selection
- Specify tool choices with clear justification for each; defer exact versions and dependency coordinates to the LLD
- Document why each tool was selected over alternatives (Rationale + trade-off)
- Verify that each choice aligns with team capabilities and the approved technology catalog
- Technology table uses three columns only: **Component | Tool | Why**

### 3. Layer Design (Data Architecture)
- Define the purpose and responsibilities of each layer (Bronze, Silver, Gold) conceptually
- Describe the transformation strategy and data quality approach per layer
- Defer table inventories, column schemas, and write strategies to the DMS
- Map each Gold layer's purpose back to specific DRD consumer requirements — traceability enforced

### 4. Non-Functional Requirements (Scalability & Capacity)
- Convert DRD volume estimates into summary storage and compute metrics
- Project growth at 1 year and 3 years with assumptions
- Define performance targets that satisfy the DRD SLAs
- Describe the cost model (how costs scale with data growth), not line-item cost calculations

## Step 3: Generate the HLD

Write the HLD in Markdown following the template structure. The HLD has 9 sections:

### Section 1 — Executive Summary
- 3-5 sentence overview: what is being built, why, and the chosen approach
- A CTO should understand the project from this section alone

### Section 2 — Requirements Summary
Two explicit traceability tables pulled directly from the DRD:

**Functional Requirements** — one row per capability the system must deliver:
- `FR-1` through `FR-N` numbered sequentially
- Requirement: what the system must do (active voice, one sentence)
- DRD Reference: exact section (`DRD §X.Y`)
- Satisfied By: which HLD component delivers it (e.g., "Gold: patient_summary")

**Non-Functional Requirements** — one row per quality attribute:
- `NFR-1` through `NFR-N` numbered sequentially
- Requirement: the quality constraint (latency, freshness, availability, compliance, etc.)
- DRD Reference: exact section
- Satisfied By: which design decision delivers it
- Target: measurable threshold (e.g., "< 2s p90", "hourly", "AES-256")

Every row must cite a DRD section. If an FR/NFR cannot be traced to the DRD, flag it as `[gap — no DRD reference]`.

### Section 3 — Integration Architecture
- Source systems: logical description, access method, tables consumed — no ports or hostnames
- Consumer groups: access method, which Gold tables, and SLA per group
- **System Context Diagram** (`flowchart TB`) — the platform boundary with external actors (§3.3)

### Section 4 — Data Architecture
- Pattern selection: evaluate Medallion, Lambda, Kappa, Data Vault; document alternatives table + trade-off
- Layer Strategy: Bronze/Silver/Gold purpose and responsibilities — no table-level detail (defer to DMS)
- Data Domain Map: text description + **Domain Map Diagram** (`flowchart LR`) showing domains → Gold tables (§4.4)
- SCD Strategy: one row per dimension type
- **Pipeline Architecture Diagram** (`flowchart TB`) — conceptual data flow through layers with DQ gates (§4.6)

### Section 5 — Pipeline Architecture
- Technology Decisions: Component | Tool | Why table — no versions or JAR coordinates
- CDC Strategy: method per source type + **Ingestion Sequence Diagram** (`sequenceDiagram`) (§5.3)
- Scalability & Capacity: verified row counts from DB, growth model, scaling levers, cost model
- Reliability: RTO/RPO targets with justification; backup approach
- Observability: tools used for lineage, DQ monitoring, and pipeline metrics
- Key Design Principles: cross-cutting architectural rules

### Section 6 — Governance
- Data Sensitivity & Classification: one row per sensitivity level with examples and handling
- Access Strategy (IAM): one row per role group — layer access, restrictions, phase
- Data Quality Strategy: DQ rules per layer (Bronze gate, Silver gate, Gold gate) with rule types and actions
- Compliance Requirements: regulatory obligations (HIPAA, etc.) and which controls satisfy them

## Step 3.5: Decision Documentation

For every major design decision, document using this format:

```markdown
**Decision**: [what was decided]
- **Options Considered**: [list alternatives]
- **Selected**: [chosen option]
- **Rationale**: [why, citing DRD section]
- **Trade-offs Accepted**: [what you give up]
```

## Step 4: Writing style

- **Technical but accessible**: Engineers and architects should understand
  every section. Include diagrams where helpful.
- **Traceable**: Every design decision must cite a DRD requirement.
  If you cannot cite a requirement, flag it as a gap.
- **High-level over implementation**: A CTO should be able to review this
  document in 15 minutes. Defer implementation details to the LLD and DMS.
- **Specific over vague**: "DuckDB for processing because the DRD projects
  <100K rows (Section 5.1)" not "lightweight processing"
- **Complete tables**: Every table must have data rows, not just headers
- **No empty sections**: Use `[TO BE DETERMINED]` with owner and due date

### DO NOT include in the HLD

These belong in the LLD or DMS, not the HLD:
- Dependency coordinates, library versions, or license columns
- Engine tuning parameters (e.g., parallelism settings, memory allocations, worker counts)
- Specific port numbers, hostnames, or endpoint paths
- Monthly cost calculations with unit prices (describe the cost *model* instead)
- Column-level access restrictions per role
- Per-table inventories with row counts (defer to DMS)

## Step 5: Save and validate

Save the output to the latest version folder in `outputs/hld/`:

```bash
LATEST_HLD_DIR=$(ls -d outputs/hld/v* | sort -V | tail -1)
```

Use naming convention: `HLD-{YYYY-MM-DD}-{short-name}.md`

Then validate:

```bash
uv run python architect-plugin/skills/validate-hld/scripts/validate_hld.py outputs/hld/{filename}.md
```

Fix any CRITICAL issues before finalizing. Report the validation summary
to the user.

## Step 6: Session memory

**Always write session notes regardless of outcome.** Write to
`architect-plugin/memory/session-{YYYY-MM-DD}.md`:

- What was created (HLD filename, version)
- Architecture pattern selected and why
- Key technology decisions with rationale
- DRD gaps found (requirements that were missing or ambiguous)
- Discrepancies between DRD estimates and actual data
- Validation results (CRITICAL/WARNING/INFO counts)
- Open questions that remain unresolved

## Metadata

Every HLD starts with this metadata table:

| Field | Value |
|-------|-------|
| **Version** | 1.0 |
| **Created** | {today's date} |
| **Last Modified** | {today's date} |
| **Author** | Architect Agent |
| **Status** | Draft |
| **DRD Reference** | {DRD filename and version} |
