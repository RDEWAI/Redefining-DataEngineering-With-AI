---
name: generate-config-template
description: >
  Extracts configuration parameters from LLD Section 7 (Configuration Schema)
  and generates environment-specific YAML configuration templates. Produces
  one config-template.yaml with DEV, STAGING, and PROD environment blocks.
  Also known as: config generation, environment config, YAML config export,
  configuration template, deployment config.
  Input formats: LLD Markdown (.md) file with Section 7 parameter table.
  Output format: YAML config-template.yaml in outputs/lld/v{N}/config/.
  Use when the user asks to:
  - Generate configuration templates from an LLD
  - Create environment-specific config YAML
  - Export config parameters from the LLD
  - Produce deployment configuration files
  - "Create the config template from the LLD"
argument-hint: "[path-to-lld-file]"
allowed-tools: Read, Write, Edit, Grep, Glob, Bash, AskUserQuestion
context: fork
hooks:
  before:
    - matcher: Bash
      script: "${CLAUDE_PLUGIN_ROOT}/scripts/enforce-readonly-queries.py"
  after:
    - matcher: "Write|Edit"
      script: "${CLAUDE_PLUGIN_ROOT}/scripts/validate-lld-hook.py"
---

# Generate Configuration Template from LLD

> **Skill Inheritance**: This skill inherits behavioral rules from
> `technical-lead-agent.md`. The session memory requirements apply during skill
> execution.

You are a senior Technical Lead with deep knowledge of environment-specific
configuration management. Your job is to extract configuration parameters from
an LLD's Section 7 (Configuration Schema) and produce a structured YAML
configuration template with environment-specific overrides.

## Step 1: Read the LLD

If the user specifies an LLD path via `$ARGUMENTS`, read that file. Otherwise,
discover the latest LLD:

```bash
LATEST_LLD_DIR=$(ls -d outputs/lld/v* | sort -V | tail -1)
ls -t "$LATEST_LLD_DIR"/LLD-*.md | head -1
```

Read the LLD and focus on:
- **Section 7 (Configuration Schema)**: parameter inventory table
- **Section 4 (DAG Specification)**: scheduling parameters
- **Section 6 (Performance & Optimization)**: resource allocation parameters
- **Section 8 (Error Handling)**: retry and alerting parameters
- **Section 9 (Deployment)**: environment definitions

## Step 2: Extract Parameters from Section 7

Parse the Configuration Schema parameter table. Expected columns:
- Parameter (name)
- Type (string, int, boolean, etc.)
- Default (base value)
- Description
- Per-Environment (whether it varies by env)

Group parameters by category:
- **scheduling**: cron expressions, timeouts, concurrency
- **compute**: executors, cores, memory, parallelism
- **storage**: paths, formats, compression, retention
- **retry**: max attempts, backoff, dead letter settings
- **alerting**: channels, thresholds, severity routing

## Step 3: Group Parameters by Category

Build a mapping of `{category}` → list of parameter entries.

For each parameter:
1. Extract name, type, default value, description
2. Determine category from context
3. Map to environment-specific values:
   - DEV: minimal resources, verbose logging, relaxed thresholds
   - STAGING: moderate resources, standard logging, production-like thresholds
   - PROD: full resources, structured logging, strict thresholds

If a parameter's environment values are ambiguous, use `AskUserQuestion`
to clarify:

```json
{
  "questions": [
    {
      "question": "What should the Spark executor memory be for each environment?",
      "header": "Memory",
      "multiSelect": false,
      "options": [
        { "label": "2G/4G/8G", "description": "DEV: 2GB, STAGING: 4GB, PROD: 8GB" },
        { "label": "4G/8G/16G", "description": "DEV: 4GB, STAGING: 8GB, PROD: 16GB" },
        { "label": "Custom", "description": "I'll specify exact values" }
      ]
    }
  ]
}
```

## Step 4: Generate YAML Config Template

Produce a YAML file with this structure:

```yaml
# Configuration Template for {pipeline_name}
# Generated from: {lld_filename}
# Generated: {today}
#
# Usage: Copy to your deployment config and adjust values per environment.
# See LLD Section 7 for parameter descriptions and rationale.

environments:
  DEV:
    scheduling:
      cron: "0 6 * * *"
      timezone: "UTC"
      concurrency: 1
      timeout_minutes: 30
    compute:
      spark_executor_memory: "2g"
      spark_executor_cores: 2
      spark_num_executors: 2
      parallelism: 4
    storage:
      base_path: "/data/dev/patient-360"
      format: "delta"
      compression: "snappy"
      retention_days: 7
    retry:
      max_attempts: 2
      backoff_seconds: 30
      dead_letter_path: "/data/dev/dead-letter"
    alerting:
      channel: "#dev-alerts"
      severity_threshold: "CRITICAL"
      pagerduty_enabled: false

  STAGING:
    # ... moderate values ...

  PROD:
    # ... production values ...
```

## Step 5: Use the script for bulk generation

For LLDs with well-structured Section 7 tables, use the Python script:

```bash
uv run python technical-lead-plugin/skills/generate-config-template/scripts/generate_config_template.py \
  {lld_path} \
  -o outputs/lld/{version}/config/
```

The script parses the LLD markdown, extracts parameters from Section 7,
and writes the config-template.yaml.

## Step 6: Validate generated YAML

After generating the YAML file, perform inline validation:

1. **YAML validity**: Does the file parse without errors?
2. **Environment check**: Are DEV, STAGING, and PROD all present?
3. **Category check**: Are scheduling, compute, storage, retry, alerting represented?
4. **Value check**: Are DEV values smaller/simpler than PROD values?
5. **Consistency**: Do parameter names match the LLD Section 7 table?

If any check fails, fix it before saving. Report issues to the user.

## Step 7: Save config template file

Save generated YAML to:
```bash
outputs/lld/{version}/config/config-template.yaml
```

Create the `config/` subdirectory if it does not exist.

## Step 8: Session memory

**Always write session notes.** Write to
`memory/lld/session-{YYYY-MM-DD}.md`:

- LLD file processed
- Parameters extracted (count per category)
- Config template file generated
- Validation results
- Any parameter issues found and fixed

### Correction Capture (MANDATORY)

After EVERY user correction — whether they edit the artifact, ask you to change
something, or reject a section — you MUST append a learning entry BEFORE continuing:

```bash
echo '{"skill": "generate-config-template", "date": "{YYYY-MM-DD}", "correction": "{what the user said or changed}", "pattern": "{generalized rule}", "status": "pending"}' >> memory/lld/learnings-queue.jsonl
```

**What counts as a correction:** user says "no, change X to Y", edits artifact
directly, rejects a proposed decision, or provides a specific value replacing
a vague one you generated. When in doubt, append it — false positives are filtered
during apply-learnings.

## Learnings & Corrections

> **Meta-rules for adding learnings:**
> 1. Each learning MUST be an absolute directive ("Always X", "Never Y")
> 2. Lead with the problem, then the fix: "When X happens, do Y"
> 3. Include a concrete command or example, not just prose
> 4. One learning per bullet — no compound rules
> 5. Delete learnings that contradict each other; keep the newer one
> 6. Maximum 20 learnings per skill — if at capacity, merge related items

### Active Learnings

_No learnings recorded yet. Learnings are added when corrections occur during skill execution._

<!-- Example format:
- **L-001** (2026-03-20): Always include units in parameter names — use `timeout_minutes` not `timeout`.
- **L-002** (2026-03-21): Never generate placeholder values for PROD alerting — ask the user for specific PagerDuty routing keys.
-->
