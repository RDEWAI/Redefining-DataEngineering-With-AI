# Session 2026-06-22 — LLD v1.24 re-baseline: residual-drift fix (v3.1 → v3.2)

## Context
Continued the LLD v1.24 re-baseline. The v3.0/v3.1 sweeps left residual drift; the
user supplied six exact corrections to apply against LLD v1.24. Scope: `chapter-6/outputs/stories`
ONLY (chapter-5 untouched). Scenario C (same v1 folder, same date 2026-06-22), minor bump 3.1 → 3.2.
All edits surgical via Edit (no Write except this note); unchanged lines preserved.

## Corrections applied
1. **Liquibase sweep (missed by v3.0/v3.1).** Replaced every residual
   `Liquibase-pre-created` / `pre-created by Liquibase` / `NOT pre-created in Liquibase`
   with the beeline-applied `ddl/migrations/*.sql` mechanism (Decision 12, Liquibase retired):
   - EPIC-03 STORY-03-001/-002/-003/-004 (lines 32 + 51)
   - EPIC-04 STORY-04-001..009 (line 32)
   - EPIC-05 STORY-05-001/-002/-003 (line 32)
   - STORY-01-010 (line 49: "NOT pre-created in Liquibase" → "NOT pre-created by the `ddl/migrations/*.sql` migrations")
   - EPIC-07 (line 40: "only Bronze ... has Liquibase" → "... has a layer-scoped DDL deploy-validation story")
   Left intact: STORY-01-007 / STORY-02-004 / STORY-02-009 / EPIC-01 / EPIC-02 retirement
   prose ("Liquibase retired", "no liquibase container", forbidden_grep on liquibase) — correct.
2. **Spark version.** STORY-01-008 AC: "reports Spark 4.0.0" → "reports Spark 4.1.1".
3. **Marquez port.** STORY-01-006: host API port 5000 → 5001 (6 occurrences) to match
   LLD §9.1.1 / EPIC-06 STORY-06-001.
4. **SE stats name.** Shared `bronze_se_stats` → per-table MANAGED FQN
   `unity.bronze.synthea_<table>_stats`: STORY-01-008 (53/137), STORY-01-010 (47/49),
   STORY-02-008 (32). `meta_dq_run_id` matching logic preserved on the STORY-01 evidence AC.
   Left intact: STORY-01-010 forbidden_grep / "NOT a shared bronze_se_stats" prohibition prose
   (correctly forbids the shared name); STORY-02-008 lines 43/70 (use the LLD-mandated
   `meta_dq_run_date` evidence filter; outside the user's line-32 scope).
5. **Bronze metadata column.** Added 4th column `_source_file STRING` (LLD §2.3, prevents
   `DELTA_INSERT_COLUMN_ARITY_MISMATCH`) to the runner spec (STORY-02-001 Description + AC)
   and the DDL migration column list (STORY-02-004 Description).
6. **Service count.** BACKLOG Risks row "six-service stack" → "seven-service stack"
   (matches EPIC-01 line 92 / STORY-01-007).

## Metadata
- Version 3.1 → 3.2; Last Modified 2026-06-22; Status `Updated - Pending Review`.
- Added v3.2 Version-History row. Historical rows (v2.1, v3.0, v3.1, etc.) left untouched.
- No story added/removed; point totals unchanged (56 stories / 219 pts).

## Validation
- `validate_stories.py --all outputs/stories/v1` → All checks passed. No issues found.

## Notes
- Other working-tree modifications (STORY-01-001/-004/-005/-007, STORY-02-003/-009/-010,
  EPIC-01/EPIC-02, deleted BACKLOG-2026-06-20.bak) are pre-existing uncommitted v3.0/v3.1
  edits — not from this session.
- No new learnings queued: these corrections were drift the prior sweep missed, already
  covered by L-002 (reconcile write-method wording across all layers) and L-004 (use the
  exact LLD `ddl/migrations/*.sql` path everywhere).
