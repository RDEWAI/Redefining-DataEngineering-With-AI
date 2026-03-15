---
name: create-role-plugin
description: >
  Generates a complete role plugin for the chapter-4 multi-agent artifact chain.
  Creates agent definition, skills (create/update/validate), hooks, validator,
  tests, and updates marketplace.json and CLAUDE.md. Use when scaffolding a new
  role such as data-modeler, mapping-engineer, dq-engineer, technical-lead, or
  scrum-master.
argument-hint: "<role-name> <artifact-abbrev> \"<Artifact Full Name>\""
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, AskUserQuestion
---

# Create Role Plugin

Generate a complete Claude Code plugin for a new role in the chapter-4
multi-agent artifact chain (DRD → HLD → Data Model → DMD → DQS → LLD → Stories).

## Step 0: Parse Arguments

Extract from `$ARGUMENTS`:
- **arg 0** → `{role}` (e.g., `data-modeler`) — hyphenated, lowercase
- **arg 1** → `{artifact}` (e.g., `dmd`) — lowercase abbreviation
- **arg 2** → `{artifact_full}` (e.g., `Data Model Document`) — quoted full name

Derive these variables:
- `{role_underscore}` → replace hyphens with underscores (e.g., `data_modeler`)
- `{ROLE}` → title case display name (e.g., `Data Modeler`)
- `{ARTIFACT}` → uppercase abbreviation (e.g., `DMD`)
- `{plugin_name}` → `{role}-plugin` (e.g., `data-modeler-plugin`)
- `{agent_name}` → `{role}-agent` (e.g., `data-modeler-agent`)

If any argument is missing, call `AskUserQuestion` to request it.

## Step 1: Gather Role-Specific Details

Call `AskUserQuestion` — **Round 1** (3 questions):

```json
{
  "questions": [
    {
      "question": "What is the upstream artifact that the {ROLE} consumes as input?",
      "header": "Upstream",
      "multiSelect": false,
      "options": [
        { "label": "DRD", "description": "Data Requirements Document (from BA)" },
        { "label": "HLD", "description": "High-Level Design (from Architect)" },
        { "label": "Data Model", "description": "Data Model (from Data Modeler)" },
        { "label": "DMD", "description": "Data Mapping Document (from Mapping Engineer)" }
      ]
    },
    {
      "question": "What color should the {ROLE} agent use in the terminal UI?",
      "header": "Color",
      "multiSelect": false,
      "options": [
        { "label": "purple", "description": "Purple theme" },
        { "label": "orange", "description": "Orange theme" },
        { "label": "cyan", "description": "Cyan theme" },
        { "label": "red", "description": "Red theme" }
      ]
    },
    {
      "question": "Does this role need a database gate (must verify DB data before generating)?",
      "header": "DB Gate",
      "multiSelect": false,
      "options": [
        { "label": "Yes", "description": "Agent must verify data volumes before generating" },
        { "label": "No", "description": "Agent works from upstream artifacts only" }
      ]
    }
  ]
}
```

Call `AskUserQuestion` — **Round 2** (2 questions):

```json
{
  "questions": [
    {
      "question": "What sections does the {ARTIFACT} artifact contain?",
      "header": "Sections",
      "multiSelect": false,
      "options": [
        { "label": "Let me list", "description": "I'll provide specific section names" },
        { "label": "Standard 6", "description": "Overview, Specifications, Rules, Quality, Traceability, Version History" },
        { "label": "Mirror upstream", "description": "Same section structure as the upstream artifact" }
      ]
    },
    {
      "question": "What are the 4 key responsibilities for the {ROLE} role?",
      "header": "Duties",
      "multiSelect": false,
      "options": [
        { "label": "Auto-generate", "description": "Derive responsibilities from the artifact type" },
        { "label": "Let me specify", "description": "I'll describe the 4 responsibilities" }
      ]
    }
  ]
}
```

If user chooses "Let me list" or "Let me specify", call `AskUserQuestion` again
to collect the specific details in a follow-up round.

## Step 2: Read Canonical Templates

Read all of these files from the architect-plugin — they are the canonical
patterns for generating new plugins:

```
chapter-4/architect-plugin/.claude-plugin/plugin.json
chapter-4/architect-plugin/agents/architect-agent.md
chapter-4/architect-plugin/skills/create-hld/SKILL.md
chapter-4/architect-plugin/skills/create-hld/HLD_template.j2
chapter-4/architect-plugin/skills/update-hld/SKILL.md
chapter-4/architect-plugin/skills/validate-hld/SKILL.md
chapter-4/architect-plugin/skills/validate-hld/scripts/validate_hld.py
chapter-4/architect-plugin/hooks/hooks.json
chapter-4/architect-plugin/scripts/enforce-readonly-queries.py
chapter-4/architect-plugin/scripts/validate-hld-hook.py
chapter-4/tests/test_architect_agent_definition.py
chapter-4/tests/test_validate_hld.py
chapter-4/tests/test_validate_hld_hook.py
chapter-4/tests/conftest.py
chapter-4/.claude-plugin/marketplace.json
chapter-4/CLAUDE.md
chapter-4/Makefile
```

## Step 3: Generate All Plugin Files

Use the mapping table below. For each row, read the source file, apply the
substitutions, and write the target file. Adapt domain-specific content
(section names, responsibilities, examples, validation checks) based on the
AskUserQuestion answers from Step 1.

### File Mapping Table

| # | Source File (read) | Target File (write) | Key Substitutions |
|---|---|---|---|
| 1 | `architect-plugin/.claude-plugin/plugin.json` | `{plugin_name}/.claude-plugin/plugin.json` | name, description, keywords |
| 2 | — | `{plugin_name}/memory/.gitkeep` | empty file |
| 3 | — | `inputs/{artifact}/v1/.gitkeep` | empty file |
| 4 | — | `outputs/{artifact}/v1/.gitkeep` | empty file |
| 5 | `architect-plugin/agents/architect-agent.md` | `{plugin_name}/agents/{agent_name}.md` | name, color, role description, examples, sections, responsibilities, upstream refs, artifact names, skill paths |
| 6 | `architect-plugin/skills/create-hld/SKILL.md` | `{plugin_name}/skills/create-{artifact}/SKILL.md` | artifact paths, upstream refs, section checklist, template path |
| 7 | `architect-plugin/skills/create-hld/HLD_template.j2` | `{plugin_name}/skills/create-{artifact}/{ARTIFACT}_template.j2` | section headers adapted to new artifact |
| 8 | — | `{plugin_name}/skills/create-{artifact}/examples/sample-{artifact}.md` | placeholder: `# Sample {artifact_full}\n\nTODO: Add a complete example.` |
| 9 | `architect-plugin/skills/update-hld/SKILL.md` | `{plugin_name}/skills/update-{artifact}/SKILL.md` | artifact paths, upstream refs |
| 10 | `architect-plugin/skills/validate-hld/SKILL.md` | `{plugin_name}/skills/validate-{artifact}/SKILL.md` | artifact paths, validator script path |
| 11 | `architect-plugin/skills/validate-hld/scripts/validate_hld.py` | `{plugin_name}/skills/validate-{artifact}/scripts/validate_{artifact}.py` | function names, section names, check logic, artifact refs |
| 12 | `architect-plugin/hooks/hooks.json` | `{plugin_name}/hooks/hooks.json` | hook script path: `validate-{artifact}-hook.py` |
| 13 | `architect-plugin/scripts/enforce-readonly-queries.py` | `{plugin_name}/scripts/enforce-readonly-queries.py` | **copy verbatim** — no changes |
| 14 | `architect-plugin/scripts/validate-hld-hook.py` | `{plugin_name}/scripts/validate-{artifact}-hook.py` | output path pattern, validator import |
| 15 | `tests/test_architect_agent_definition.py` | `tests/test_{role_underscore}_agent_definition.py` | agent file path, name assertion, section assertions |
| 16 | `tests/test_validate_hld.py` | `tests/test_validate_{artifact}.py` | validator imports, fixture names, check function names |
| 17 | `tests/test_validate_hld_hook.py` | `tests/test_validate_{artifact}_hook.py` | hook script path, output path pattern, fixture names |

### Critical Rules for Generation

**Agent definition (file #5):**
- Keep the exact same structural sections: Elicitation Protocol (Steps 1-5),
  Four Responsibilities, Workflow (Phases 1-5), Pitfall Prevention (3 pitfalls),
  Writing Style, Sections Reference, File Conventions
- AskUserQuestion examples MUST use the correct Claude Code schema:
  `{questions: [{question, header (max 12 chars), multiSelect, options: [{label, description}]}]}`
- Version discovery: `ls -d chapter-4/{path}/v* | sort -V | tail -1`
- If DB gate is enabled, include Phase 3 database gate; if disabled, skip it
- Replace `[DRD §X.Y]` traceability format with `[{UPSTREAM_ARTIFACT} §X.Y]`

**Validator (file #11):**
- Keep `ValidationLevel`, `ValidationResult`, `ValidationReport` classes verbatim
- Replace HLD-specific check functions with ones matching the new artifact sections
- Keep the same CLI interface (`--all`, `--format json`, exit codes 0/1/2/3)
- CRITICAL checks: required sections present, metadata complete, section-specific
- WARNING checks: upstream traceability, quality checks
- INFO checks: placeholders with owners

**Tests (files #15-17):**
- Follow the exact same test class/method structure
- Adapt assertions to match new agent name, sections, skill paths

**conftest.py:**
- APPEND to the existing file — do not overwrite
- Add `VALID_{ARTIFACT}`, `MINIMAL_INVALID_{ARTIFACT}`, `EMPTY_SECTIONS_{ARTIFACT}`,
  `PLACEHOLDER_{ARTIFACT}` constants
- Add pytest fixtures: `valid_{artifact}_file`, `invalid_{artifact}_file`,
  `empty_{artifact}_sections_file`, `placeholder_{artifact}_file`

## Step 4: Update Existing Files

### marketplace.json
Add a new entry to the `plugins` array:
```json
{
  "name": "{plugin_name}",
  "source": "./{plugin_name}",
  "description": "{ROLE} Agent for generating, updating, and validating {artifact_full}s"
}
```

### CLAUDE.md
Add a new plugin section following the existing Architect Plugin pattern:
```markdown
### {ROLE} Plugin

The plugin lives in `{plugin_name}/` and is defined by
`{plugin_name}/.claude-plugin/plugin.json`.

- `{plugin_name}/skills/` - Skills: create-{artifact}, update-{artifact}, validate-{artifact}
- `{plugin_name}/hooks/` - PostToolUse hook for automatic {ARTIFACT} validation
- `{plugin_name}/scripts/` - Hook scripts

**Inputs**: Latest {UPSTREAM_ARTIFACT} from `outputs/{upstream}/v{N}/` + `inputs/{artifact}/v{N}/`

**Outputs**: {ARTIFACT} documents in `outputs/{artifact}/v{N}/`
```

Also update the Directory Layout section to include new input/output paths.

### Makefile
Add a `validate-{artifact}` target following the existing `validate-hld` pattern.

## Step 5: Verify

Run these commands and fix any issues:

```bash
cd chapter-4
uv run pytest tests/test_{role_underscore}_agent_definition.py tests/test_validate_{artifact}.py tests/test_validate_{artifact}_hook.py -v
uv run ruff check {plugin_name}/ tests/test_{role_underscore}_agent_definition.py tests/test_validate_{artifact}.py tests/test_validate_{artifact}_hook.py
uv run ruff format --check {plugin_name}/ tests/
```

Fix any failures, then run the full test suite:

```bash
uv run pytest tests/ -v
```

## Step 6: Report

After all files are generated and tests pass, report:

1. Summary of files created (count + list)
2. Test results
3. Instructions to install:
   ```
   /reload-plugins
   # or
   /plugin marketplace add ./chapter-4
   /plugin install {plugin_name}@rdewai-plugins
   ```
4. How to invoke the new agent:
   ```
   @{plugin_name}:{agent_name} Create the {ARTIFACT} for the project
   ```
