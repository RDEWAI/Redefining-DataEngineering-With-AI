# Claude Code Instructions

Add project-specific instructions for Claude Code here.

## Active Technologies
- Python 3.10-3.12 (aligned with existing project) (003-chapter2-ai-engineering)
- DuckDB at `chapter-2/data/duckdb/chapter2.db` with `library` schema (003-chapter2-ai-engineering)

- **Python 3.10-3.12** with UV package manager for environment management
- **DuckDB 1.1.3** for embedded analytics database
- **Apache Superset 4.1.1** for data visualization
- **SQLMesh** for SQL-based data transformations

## Data Architecture

- Raw CSV data: `data/raw/` (18 Synthea healthcare CSV files)
- DuckDB database: `data/duckdb/raw.db` with `synthea` schema
- Tables accessed as `synthea.patients`, `synthea.encounters`, etc.

## Key Commands

```bash
make dev-setup      # Set up development environment
make raw-data-copy  # Extract Synthea CSV data from Docker
make load-raw-data  # Load CSV files into DuckDB tables
make superset-init  # Initialize Superset with DuckDB connection
make superset-run   # Start Superset web server
make test           # Run all tests
```

## Chapter 3: Business Analyst Agent

- **Skills**: `.claude/skills/` under `chapter-3/` — `create-drd`, `update-drd`, `validate-drd`
- **Inputs**: `chapter-3/inputs/drd/` (business requests, stakeholder notes, source docs, catalogs)
- **Outputs**: `chapter-3/outputs/drd/` (generated DRD markdown files)
- **Validator**: `chapter-3/.claude/skills/validate-drd/scripts/validate_drd.py`
- **Tests**: `cd chapter-3 && uv run pytest tests/ -v`

## Chapter 4: Multi-Agent Artifact Chain (continuation of Chapter 3)

- **Plugins**: BA (DRD) → Architect (HLD) → Data Modeler (DMS) → Mapping Analyst (STM) → DQ Engineer (DQS) → Technical Lead (LLD) → Scrum Master (Stories)
- **Inputs**: `chapter-4/inputs/{role}/v{N}/` (folder-versioned per role)
- **Outputs**: `chapter-4/outputs/{artifact}/v{N}/` (DRD=markdown, HLD=markdown, DMS=markdown, STM=xlsx, DQS=markdown+YAML, LLD=markdown+config+DAG, Stories=markdown multi-file)
- **Dependencies**: jinja2, pyyaml, openpyxl (for STM Excel workbook generation)
- **Tests**: `cd chapter-4 && uv run pytest tests/ -v`

## Interactive Testing with TMUX

When testing interactive commands (assistants, REPLs, semantic search, etc.), use the tmux MCP tools
instead of running commands directly. This allows Claude Code to start, interact with, and verify
interactive applications.

**Workflow:**
1. Create a tmux session: `mcp__tmux__create-session` with a descriptive name (e.g., `ch2-test`)
2. Print the attach command so the user can watch in another terminal:
   ```
   tmux attach-session -t <session-name>
   ```
3. Use `mcp__tmux__execute-command` with `rawMode=true` to run interactive commands
4. Use `mcp__tmux__capture-pane` to read output and verify startup/results
5. Send quit/exit commands via `execute-command` with `rawMode=true`
6. Kill the session when done: `mcp__tmux__kill-session`

**Example — testing `make assistant`:**
```
# Create session
mcp__tmux__create-session name="ch2-test"
# Tell user: "Run `tmux attach-session -t ch2-test` in another terminal to watch"
# Launch interactive command
mcp__tmux__execute-command paneId="..." command="make assistant" rawMode=true
# Wait, then capture output
mcp__tmux__capture-pane paneId="..." lines=20
# Quit
mcp__tmux__execute-command paneId="..." command="/quit" rawMode=true
```

## Pre-commit Hooks

When adding a new chapter directory (e.g., `chapter-4/`), update `.pre-commit-config.yaml`:
1. Add the chapter to the ruff `files` regex: `^(chapter-2|chapter-3|chapter-4)/`
2. Add a new `pytest-unit-chN` hook scoped to the chapter with `files: ^chapter-N/`
3. If the chapter has typed Python source, consider adding a mypy entry for it

Pytest hooks are scoped per-chapter so pushes only run tests for chapters with changed files.

## Recent Changes
- Chapter 3: BA Agent with DRD skills (create-drd, update-drd, validate-drd) for Patient 360 use case
- 003-chapter2-ai-engineering: Added Python 3.10-3.12 (aligned with existing project)
- Feature 002: DuckDB CSV Data Loader - Load 18 Synthea CSV files into DuckDB tables under `synthea` schema

## Learnings

<!-- AUTO-LEARNINGS:START (managed by .claude/hooks/sync_learnings_to_claude_md.py — do not edit by hand) -->
- `create-drd` (2026-03-27): When inputs are thorough and a prior session exists, minimize Q&A rounds and proceed with defaults
- `create-silver` (2026-06-15): Before generating Silver modules, run a DMS§3-vs-STM column reconciliation gate. If they diverge on column name/type/PK/presence for any table, HALT and route to data-modeler:update-dms or mapping-analyst:update-stm rather than silently picking one artifact. Do not invent a merged schema.
- `create-silver` (2026-06-15): When a story AC's path/FQN convention conflicts with a Revoked LLD decision that LLD-DEVIATIONS.md has already superseded, follow the LLD+deviations (authoritative) and recommend scrum-master:update-stories to refresh the stale AC text — per IL-017 do not rename project code to match the stale AC.
- `create-silver` (2026-06-15): Generate Silver transform calls against the SHIPPED se_runner.run_dq signature (single-DF return, keyword-only) not the SKILL sketch. Also: DQS emits se-rules-<dashed>.yaml; these must be copied to dq_rules/{table}.yml (underscored, no se-rules- prefix) for run_dq's convention-based discovery.
- `implement-stories` (2026-06-14): When the content classifier maps a silver/* (or any non-Bronze layer) story to 'ingestion' purely via an epic-slug substring match, and the dispatched create-ingestion ROUTE-OUTs to a create-silver/create-gold skill that is NOT registered in the plugin, HALT the batch with an actionable error (missing owner skill). Do not re-dispatch into the route-out target (no thrash). Fix path: either add the create-silver/create-gold skills, or correct the classifier so silver/gold stories do not resolve to 'ingestion'. (L-008, L-011)
- `implement-stories` (2026-06-15): When a forked create-/update- skill leaves .skill-arg/.skill-paths un-consumed after dispatch, treat it as a scope-control failure: the sub-skill did not honor story scoping. Surface a CRITICAL (do not silently accept full-mode output) and confirm scope with the user before continuing the batch. Fix the sub-skills to read .skill-arg as the authoritative target when $ARGUMENTS is empty in fork context.
- `implement-stories` (2026-06-15): verify_acs.py pytest checks must run via 'uv run' from the project root (like validate_silver.py) so the editable package + dev extras resolve; a bare interpreter yields false-negative AC FAILs that orchestrator must not treat as halts
- `implement-stories` (2026-06-15): per L-001, when scoping files survive a sub-skill invocation but the deliverables match the story scope, treat it as a sub-skill consumption bug (not a routing failure): clean up the files and note it; fix create-/update- skills to delete .skill-arg/.skill-paths after reading
- `implement-stories` (2026-06-16): When an AC Verification grep targets a literal that a later-revoked LLD decision invalidated (e.g. a UC FQN replaced by a path-based read), the AC spec is stale, not the code. Do not patch code to satisfy a stale grep; surface to scrum-master:update-stories to re-sync AC text against the current LLD decision log, and treat the inline-FAIL as a backlog spec defect rather than an implementation defect.
- `implement-stories` (2026-06-16): When an AC Verification grep targets a string that the implementation produces dynamically (f-string / loop-generated task ids, config-driven names), a literal grep yields a false FAIL. Treat as a Verification-spec defect (L-004 sibling): recommend scrum-master:update-stories to replace the literal grep with the runtime pytest assertion (which already validates the generated ids), rather than forcing the generator to hardcode strings. Do not rewrite working code to satisfy a brittle grep.
- `update-ingestion` (2026-06-21): SE inline reconciliation rules (rule_type query_dq, tag reconciliation, DQ_REC_*) MUST stay is_active:false on this stack. Their expectation references the DuckDB SOURCE table (e.g. synthea.<t>) which se_runner does NOT register as a Spark view at SE-run time (it only registers unity.* + bare-name views), and the CASE...FROM...@-delimiter form does not parse as an SE query_dq. Activating one raises SparkExpectationsMiscException: PARSE_SYNTAX_ERROR at FROM and fails the task. Keep the rule PRESENT with action_if_failed:fail (satisfies test_ac3_critical_tables_have_fail_action) but is_active:false (matches every shipped DQ_REC_*). Cross-table reconciliation is done by the reconciliation_bronze/silver TASK (utils/reconciliation.py), not by inline SE query_dq.
- `update-ingestion` (2026-06-21): The SE-RUN-EVIDENCE gate in bronze/reconciliation.py (_count_se_stats_rows / assert_se_evidence) must NOT assume the SE stats meta_dq_run_date equals the data ds. The managed SE _stats table has no ds column; meta_dq_run_date/meta_dq_run_datetime are the wall-clock SE run time. The `WHERE meta_dq_run_date = '{ds}'` filter only works when the run happens on the same calendar day as ds (normal scheduled hourly run) and FALSE-FAILS on any backfill/replay of a past ds. Fix: either filter by meta_dq_run_date = current_date() (SE ran in this execution), or thread the DAG's meta_dq_run_id into se_runner so SE stamps the stats and the gate matches on meta_dq_run_id exactly. Do not gate anti-silent-skip on ds == run-date.
- `update-lld` (2026-05-12): When the LLD reverses a prior Decision N, the matching validator rule (here check_bronze_uc_wiring) must be patched to honor an explicit 'Revoked'/'Reverted' Status marker — otherwise the hook blocks every subsequent edit on the same file.
- `update-lld` (2026-05-12): Bronze layer column contracts must be sourced from the source system itself, not from the DMS. The DMS owns Silver/Gold contracts. Bronze is a permissive landing zone — schema-drift handling belongs in Silver.
- `update-lld` (2026-05-12): In any LLD targeting Airflow 3.x with embedded Spark, §4.2 must state explicitly that every Spark-touching task uses SparkSubmitOperator. PythonOperator + pyspark.sql.SparkSession.builder.getOrCreate() collides on classloaders inside the Airflow worker JVM.
- `update-lld` (2026-05-12): spark-expectations generates its own meta_dq_run_id internally and does NOT accept an override from Airflow ts_nodash. Any SE evidence/reconciliation query must key on meta_dq_run_date (the ds) only.
- `update-lld` (2026-05-12): For chapter-5's single-laptop educational deployment, DEV Spark driver and executor memory defaults are 1g/1g (not 2g/2g). The compose stack co-residency must be accounted for in §6.1 sizing.
- `update-lld` (2026-05-12): Every chapter-5 LLD must declare a single PROJECT_ROOT-style env var that anchors all runtime relative paths (configs, dq_rules, warehouse, dead-letter). Hardcoded /opt/airflow/* literals and bare relative paths must both be rejected.
- `update-lld` (2026-06-20): When a runtime tool is proven unusable on the open-source stack (no working JDBC/dialect path), remove it entirely rather than retaining it as a nominal source-of-truth — update §2.3/§3/§9/§13 and the cookiecutter scaffold path together, and update the validate-lld §9-directory allow-list to match the new path.
- `update-stories` (2026-05-11): Always cite the project CLAUDE.md / LLD §5.1 file-naming convention before encoding glob patterns in AC Verification blocks; per-table SE rule YAMLs use {table}.yml not synthea_{table}.yml
<!-- AUTO-LEARNINGS:END -->

## What Not To Do

<!-- AUTO-WHATNOT:START (managed by .claude/hooks/sync_learnings_to_claude_md.py — do not edit by hand) -->
_No new auto-captured learnings this session._
<!-- AUTO-WHATNOT:END -->
