# DQ Engineer Plugin

The DQ Engineer plugin produces Data Quality Specifications (DQS) and
Spark-Expectations YAML rule files. It sits downstream of the Mapping
Analyst (STM) in the multi-agent artifact chain.

**Artifact chain position**: STM → **DQS** → LLD → Stories

---

## Skills

| Skill | Description | Output |
|-------|-------------|--------|
| `create-dqs` | Generate a new DQS from upstream STM, DMS, and DRD; auto-generates SE YAML files after validation | DQS markdown + SE YAML files |
| `update-dqs` | Update an existing DQS with new rules or thresholds | Updated DQS markdown |
| `validate-dqs` | Validate a DQS for completeness and quality | Validation report |
| `generate-se-rules` | Convert DQS rules to Spark-Expectations YAML per table | SE YAML files |

---

## Dual Output Format

The DQ Engineer plugin produces two types of output:

1. **DQS Markdown** (`outputs/dqs/v{N}/DQS-{YYYY-MM-DD}-{name}.md`)
   Human-readable specification with all 9 required sections.

2. **SE YAML Files** (`outputs/dqs/v{N}/se-rules/se-rules-{table-name}.yaml`)
   Machine-readable Spark-Expectations rule files — one per target table,
   compatible with spark-expectations >= 2.6.0. Uses SE-native fields:
   `enable_error_drop_alert` (not `enable_error_drop_analysis`), `priority`,
   and `table_name` per environment (not `schema_prefix`). The `create-dqs`
   skill generates these automatically after DQS validation passes.

---

## Directory Layout

```
dq-engineer-plugin/
├── .claude-plugin/
│   └── plugin.json             # Plugin manifest
├── agents/
│   └── dq-engineer-agent.md    # Agent definition
├── hooks/
│   └── hooks.json              # PostToolUse hooks config
├── memory/
│   └── .gitkeep                # Session memory (gitignored)
├── scripts/
│   ├── enforce-readonly-queries.py  # DB safety hook
│   └── validate-dqs-hook.py         # Auto-validate on Write/Edit
└── skills/
    ├── create-dqs/
    │   ├── SKILL.md
    │   ├── DQS_template.j2
    │   └── examples/
    │       └── sample-dqs.md
    ├── update-dqs/
    │   └── SKILL.md
    ├── validate-dqs/
    │   ├── SKILL.md
    │   └── scripts/
    │       └── validate_dqs.py
    └── generate-se-rules/
        ├── SKILL.md
        ├── scripts/
        │   └── generate_se_rules.py
        └── examples/
            └── sample-se-rules/
                ├── se-rules-dim-patient.yaml
                └── se-rules-fact-encounter.yaml
```

---

## Inputs

The plugin reads from three upstream artifact paths plus dedicated DQ inputs:

| Input | Path | Content |
|-------|------|---------|
| STM (from Mapping Analyst) | `outputs/stm/v{N}/` | Source-to-target mapping workbook |
| DMS (from Data Modeler) | `outputs/dms/v{N}/` | Table schemas, FK definitions |
| DRD (from BA Agent) | `outputs/drd/v{N}/` | DQ expectations, SLAs, compliance |
| DQ Standards | `inputs/dqs/v{N}/dq-standards.md` | Severity definitions, thresholds |
| SLA Definitions | `inputs/dqs/v{N}/sla-definitions.md` | Consumer freshness requirements |
| SE Config Template | `inputs/dqs/v{N}/se-config-template.yaml` | Spark-Expectations env config |

---

## Outputs

| Artifact | Path | Format |
|----------|------|--------|
| DQS Document | `outputs/dqs/v{N}/DQS-{date}-{name}.md` | Markdown |
| SE Rules (per table) | `outputs/dqs/v{N}/se-rules/se-rules-{table}.yaml` | YAML |

---

## Four DQS Responsibilities

Every DQS produced by this plugin covers:

1. **Field-Level Validations** — NOT NULL, FORMAT, RANGE, ENUM per column,
   across bronze, silver, AND gold layers (never gold-only)
2. **Referential Integrity** — FK checks with orphan actions
3. **Statistical Distribution** — Row count baselines, null rates, thresholds
4. **Reconciliation** — Source-to-target count and sum comparisons

---

## Installing the Plugin

From the chapter-4 directory:

```bash
/plugin install dq-engineer-plugin@rdewai-plugins
```

Or via the marketplace:

```bash
/plugin marketplace add ./chapter-4
/plugin install dq-engineer-plugin@rdewai-plugins
```

---

## Running Tests

```bash
cd chapter-4 && uv run pytest tests/test_dq_engineer_agent_definition.py -v
cd chapter-4 && uv run pytest tests/test_validate_dqs.py -v
cd chapter-4 && uv run pytest tests/test_validate_dqs_hook.py -v
cd chapter-4 && uv run pytest tests/test_generate_se_rules.py -v
```

Or run all chapter-4 tests:

```bash
cd chapter-4 && uv run pytest tests/ -v
```
