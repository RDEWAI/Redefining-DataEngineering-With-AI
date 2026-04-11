# Mapping Analyst Plugin

Mapping Analyst Agent for generating, updating, and validating Source-to-Target Mapping (STM) Excel workbooks.

## Skills

| Skill | Command | Description |
|-------|---------|-------------|
| create-stm | `/mapping-analyst-plugin:create-stm` | Generate a new STM from upstream artifacts |
| update-stm | `/mapping-analyst-plugin:update-stm` | Update an existing STM with changes |
| validate-stm | `/mapping-analyst-plugin:validate-stm` | Validate an STM for completeness |

## Usage

```
/mapping-analyst-plugin:create-stm
```

Or invoke the agent directly:
```
@mapping-analyst-plugin:mapping-analyst-agent Create the STM for the project
```

## Output Format

**Excel Workbook (.xlsx)** with 8 sheets:
1. Summary — Metadata and traceability
2. Source-to-Bronze — Column pass-through mappings
3. Bronze-to-Silver — Cleansing and transformation rules
4. Silver-to-Gold — Aggregation and SCD logic
5. Code Systems — SNOMED, RxNorm, LOINC mappings
6. Null Handling — Per-field null strategies
7. Edge Cases — Error handling rules
8. Lineage — Full column-level lineage

## Directory Layout

```
mapping-analyst-plugin/
├── .claude-plugin/plugin.json
├── agents/mapping-analyst-agent.md
├── skills/
│   ├── create-stm/
│   │   ├── SKILL.md
│   │   └── examples/sample-stm.py
│   ├── update-stm/SKILL.md
│   └── validate-stm/
│       ├── SKILL.md
│       └── scripts/validate_stm.py
├── hooks/hooks.json
├── scripts/
│   ├── validate-stm-hook.py
│   └── enforce-readonly-queries.py
├── memory/
└── README.md
```

## Inputs

- Upstream (primary): `outputs/dms/v{N}/`
- Upstream (secondary): `outputs/hld/v{N}/`
- Role-specific: `inputs/stm/v{N}/`

## Outputs

- `outputs/stm/v{N}/STM-{YYYY-MM-DD}-{name}.xlsx`
