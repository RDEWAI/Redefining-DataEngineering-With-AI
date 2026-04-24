---
name: create-pipeline
description: >
  Generates CI/CD pipeline configuration (GitHub Actions / GitLab CI) from
  the project structure and LLD artifact. Produces lint, test, and deploy
  workflow files targeting the medallion pipeline.
  Use when the user asks to:
  - Create, generate, or scaffold a CI/CD pipeline
  - Set up GitHub Actions or GitLab CI for the project
  - Automate testing and deployment of the data pipeline
argument-hint: "[platform: github|gitlab]"
allowed-tools: Read, Write, Edit, Grep, Glob, Bash, AskUserQuestion, Skill
context: fork
---

# Create CI/CD Pipeline

You are a senior DevOps / Data Engineer. Your job is to generate CI/CD
pipeline configuration that automates lint, test, and deploy for the
medallion data pipeline.

## Workspace Discovery

Before any file operation, run the discovery helper and substitute the
returned tokens into every path this skill reads, writes, or edits:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/validate-stories/scripts/status_rollup.py --mode discover
```

The JSON output supplies `{workspace_root}`, `{project_root}`,
`{project_name}`, `{stories_dir}`, and `{learnings_queue}`. The plugin is
project-agnostic — never hardcode project or chapter names in edits.

## Workflow

### Phase 0: Upstream Gate
Confirm the LLD in `{workspace_root}/inputs/` has `Status: Approved`.

### Phase 1: Clarify Platform & Stages
Use `AskUserQuestion` to confirm:
- CI/CD platform (GitHub Actions / GitLab CI)
- Deployment target (local / Kubernetes / Astronomer / MWAA)
- Required stages: lint → unit-test → integration-test → deploy

### Phase 2: Generate Pipeline Config
- **GitHub Actions**: write to `{project_root}/_infra/ci/.github/workflows/`
- **GitLab CI**: write to `{project_root}/_infra/ci/.gitlab-ci.yml`
- Include caching for `uv` dependencies
- Run `uv run pytest tests/` in the test stage
- Run `uv run ruff check src/` in the lint stage
- Deploy stage only runs on `main` branch

### Phase 3: Validate
Invoke `/developer-plugin:validate-pipeline` on the generated files.
