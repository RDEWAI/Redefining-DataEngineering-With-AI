# Session 2026-06-20 — Reconcile STORY-01-010 AC7 + STORY-02-001 AC9 with MANAGED-FQN SE contract

## Trigger
v2.8 (STORY-02-010) corrected the SE audit-table contract to per-table MANAGED
UC tables by 3-part FQN (`unity.<schema>.<table>_stats` / `_error`, SE-created
via `saveAsTable` on UC 0.5.0), withdrawing the path-based design and the
"UCSingleCatalog rejects RTAS/CTAS" misdiagnosis. The v2.8 history row explicitly
flagged STORY-01-010 AC7 and STORY-02-001 AC9 as still carrying the old
PATH-BASED contract — to be reconciled in a follow-up. This session is that
follow-up.

## Changes (backlog v2.8 → v2.9, Scenario C in-place)
- **STORY-01-010 AC7** (owns `se_runner.py`): flipped from PATH-BASED
  (`.option("path", ...)`, never `saveAsTable`) → MANAGED UC tables by 3-part FQN
  (`format("delta")`, no `.option("path")`, SE creates via `saveAsTable`).
  - AC7 Verification flipped: required-grep `.option("path")`/`SE_STATS_TABLE` →
    `stats_table=...{target_table}_stats` + `unity.<schema>` + `_stats`/`_error`;
    forbidden-grep `saveAsTable`/`CREATE TABLE USING DELTA`/`tableExists` →
    `bronze_se_stats`/`_se/<table>`/`.option("path")`.
  - Description + Technical Notes re-worded; tags → `(v1.20)` / §13 Decision 12
    corrected 2026-06-20.
- **STORY-02-001 AC9** (bronze runner, cross-references -01-010): text flipped
  path-based → MANAGED-FQN. The runner-scoped `forbidden_grep: saveAsTable` is
  RETAINED — the runner itself still never creates tables; only `se_runner`
  does. Reason string + cross-ref corrected.

## Root cause captured in ACs
Empty-namespace `fullTableNameForApi` defect on BARE names (AIOOBE on length-0
namespace under spark-submit), fixed by passing the FQN `target_table` + UC 0.5.0
namespace handling — NOT an RTAS refusal.

## Scope discipline
No story added/removed; no point/sprint/dependency changes (56 stories / 219 pts).
Did not touch STORY-02-010 (already correct) or any other story.

## Validation
`validate_stories.py --all outputs/stories/v1` → All checks passed, no issues.

## Status
Backlog Status reset to `Updated - Pending Review`. Re-approval to follow.
