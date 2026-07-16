# Technical Lead Plugin

Technical Lead Agent for generating, updating, and validating Low-Level Design (LLD) documents.

## Skills

| Skill | Command | Description |
|-------|---------|-------------|
| create-lld | `/technical-lead-plugin:create-lld` | Generate a new LLD from upstream artifacts |
| update-lld | `/technical-lead-plugin:update-lld` | Update an existing LLD with changes |
| validate-lld | `/technical-lead-plugin:validate-lld` | Validate an LLD for completeness |
| generate-config-template | `/technical-lead-plugin:generate-config-template` | Generate environment config YAML from LLD §7 |
| apply-learnings | `/technical-lead-plugin:apply-learnings` | Apply pending corrections to improve skills |

## Usage

```
/technical-lead-plugin:create-lld
```

Or invoke the agent directly:
```
@technical-lead-plugin:technical-lead-agent Create the LLD for the project
```

## Directory Layout

```
technical-lead-plugin/
├── .claude-plugin/plugin.json
├── agents/technical-lead-agent.md
├── skills/
│   ├── create-lld/
│   │   ├── SKILL.md
│   │   ├── LLD_template.j2
│   │   ├── evals/eval-cases.yaml
│   │   ├── scripts/
│   │   │   ├── generate_dag_definition.py
│   │   │   └── generate_impl_sequence.py
│   │   └── examples/
│   │       ├── sample-lld.md
│   │       ├── sample-dag-definition.yaml
│   │       ├── sample-dag-pipeline.mmd
│   │       └── sample-impl-sequence.md
│   ├── update-lld/
│   │   ├── SKILL.md
│   │   └── evals/eval-cases.yaml
│   ├── validate-lld/
│   │   ├── SKILL.md
│   │   ├── evals/eval-cases.yaml
│   │   └── scripts/validate_lld.py
│   ├── generate-config-template/
│   │   ├── SKILL.md
│   │   ├── scripts/generate_config_template.py
│   │   ├── evals/eval-cases.yaml
│   │   └── examples/sample-config-template.yaml
│   └── apply-learnings/SKILL.md
├── hooks/hooks.json
└── scripts/
    ├── validate-lld-hook.py
    └── enforce-readonly-queries.py

# Top-level memory directory (outside plugin):
memory/lld/
├── .gitkeep
└── learnings-queue.jsonl
```

## Inputs

- Upstream: ALL 5 artifacts — `outputs/drd/v{N}/`, `outputs/hld/v{N}/`, `outputs/dms/v{N}/`, `outputs/stm/v{N}/`, `outputs/dqs/v{N}/`
- Role-specific: `inputs/lld/v{N}/`

## Outputs

- Primary: `outputs/lld/v{N}/LLD-{YYYY-MM-DD}-{name}.md`
- Config template: `outputs/lld/v{N}/config/config-template.yaml`
- DAG definition: `outputs/lld/v{N}/dag/dag-definition.yaml`
- DAG diagram: `outputs/lld/v{N}/dag/dag-pipeline.mmd`
- Implementation sequence: `outputs/lld/v{N}/impl-sequence.md`
