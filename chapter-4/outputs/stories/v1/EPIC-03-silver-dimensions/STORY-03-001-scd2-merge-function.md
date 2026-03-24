# STORY-03-001: Implement SCD2 Generic Merge Function

| Field | Value |
|-------|-------|
| **Epic** | EPIC-03: Silver Dimensions -- SCD Type 2 |
| **Priority** | P1 -- Critical Path |
| **Story Points** | 5 |
| **Sprint** | Sprint 5 |
| **Dependencies** | STORY-02-010 |
| **Status** | To Do |

## User Story

As a data engineer, I want a generic SCD Type 2 merge function using SHA-256 hash comparison and Delta MERGE INTO so that all four dimension tables can reuse the same change-detection logic.

## Description

Implement `src/transforms/scd2.py` with a generic SCD Type 2 merge function. The function accepts: incoming DataFrame, natural key column(s), hash columns list, target Delta table path, and effective date. It computes SHA-256 hash on tracked columns, compares against the existing target table, and executes Delta MERGE INTO with: (1) matched + hash changed: close existing row (set effective_to, is_current=FALSE), insert new row (effective_from=current_date, effective_to=NULL, is_current=TRUE); (2) not matched (new record): insert with effective_from=current_date, effective_to=NULL, is_current=TRUE; (3) matched + hash unchanged: no-op. The hash columns for each dimension table are defined in DMS SS6.

## Acceptance Criteria

- [ ] `scd2.py` implements generic merge with SHA-256 hash comparison [LLD §2.3, DMS SS6]
- [ ] Delta MERGE INTO used with matched/unmatched logic [LLD §5.2]
- [ ] Changed records: existing row closed (effective_to set, is_current=FALSE), new row inserted [DMS §6]
- [ ] New records: inserted with effective_from=current_date, effective_to=NULL, is_current=TRUE [DMS §6]
- [ ] Unchanged records: no-op (no update, no insert) [DMS §6]
- [ ] Version management: scd2_version column incremented for each new version [DMS §6]
- [ ] Unit tests cover: new record, unchanged record, changed record, multiple changes in same batch [LLD §2.4]

## Technical Notes

- **Upstream references**: LLD SS2.3 (scd2.py contract), LLD SS5.2 (Silver task details), DMS SS6 (SCD2 Strategy)
- **Implementation hints**: Use Delta Lake's `DeltaTable.forPath()` and `.merge()` API. SHA-256 hash via `pyspark.sql.functions.sha2(concat_ws('|', *hash_cols), 256)`. The hash column list varies per dimension -- pass as parameter. SCD2 dimensions are NOT partitioned (small tables, max 5,767 rows).

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | SS2.3, SS5.2, SS4.5 |
| DMS | SS6 (SCD2 Strategy, hash columns per table) |
| STM | Tab:Bronze-to-Silver (dimension transforms) |
| DQS | -- |
