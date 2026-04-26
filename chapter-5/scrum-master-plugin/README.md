# Scrum Master Plugin

Scrum Master Agent for generating, updating, and validating Sprint Backlog (Epics and Stories) documents.

## Skills

| Skill | Command | Description |
|-------|---------|-------------|
| create-stories | `/scrum-master-plugin:create-stories` | Generate a new backlog with epics and stories from LLD |
| update-stories | `/scrum-master-plugin:update-stories` | Update existing epics/stories with changes |
| validate-stories | `/scrum-master-plugin:validate-stories` | Validate backlog for completeness |
| apply-learnings | `/scrum-master-plugin:apply-learnings` | Apply pending corrections to improve skills |

## Usage

```
/scrum-master-plugin:create-stories
```

Or invoke the agent directly:
```
@scrum-master-plugin:scrum-master-agent Create stories from the latest LLD
```

## Directory Layout

```
scrum-master-plugin/
├── .claude-plugin/plugin.json
├── agents/scrum-master-agent.md
├── skills/
│   ├── create-stories/
│   │   ├── SKILL.md
│   │   ├── BACKLOG_template.j2
│   │   ├── EPIC_template.j2
│   │   ├── STORY_template.j2
│   │   ├── evals/eval-cases.yaml
│   │   └── examples/sample-stories.md
│   ├── update-stories/
│   │   ├── SKILL.md
│   │   └── evals/eval-cases.yaml
│   ├── validate-stories/
│   │   ├── SKILL.md
│   │   ├── evals/eval-cases.yaml
│   │   └── scripts/validate_stories.py
│   └── apply-learnings/SKILL.md
├── hooks/hooks.json
└── scripts/
    ├── validate-stories-hook.py
    ├── check-learnings-queue.py
    └── enforce-readonly-queries.py

# Top-level directories (outside plugin):
memory/stories/
├── .gitkeep
└── learnings-queue.jsonl
```

## Inputs

- Upstream (primary): `outputs/lld/v{N}/`
- Upstream (all): `outputs/drd/v{N}/`, `outputs/hld/v{N}/`, `outputs/dms/v{N}/`, `outputs/stm/v{N}/`, `outputs/dqs/v{N}/`
- Role-specific: `inputs/stories/v{N}/` (team capacity, story standards)

## Outputs

```
outputs/stories/v{N}/
├── BACKLOG-{YYYY-MM-DD}-{name}.md        # Main index document
├── EPIC-01-{slug}/
│   ├── EPIC-01.md                         # Epic description
│   ├── STORY-01-001-{slug}.md            # Individual stories
│   └── STORY-01-002-{slug}.md
├── EPIC-02-{slug}/
│   ├── EPIC-02.md
│   └── ...
```
