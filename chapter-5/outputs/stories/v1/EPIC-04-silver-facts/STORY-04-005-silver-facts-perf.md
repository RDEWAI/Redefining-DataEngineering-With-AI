# STORY-04-005: Silver-facts perf — observations partitioning + sort-merge tuning

| Field | Value |
|-------|-------|
| **Epic** | EPIC-04: Silver Facts Layer |
| **Story Type** | performance-optimization |
| **Priority** | P2 |
| **Story Points** | 2 |
| **Sprint** | 4 |
| **Dependencies** | STORY-04-004 |
| **Status** | To Do |

## User Story

As a Data Engineer, I want the largest Silver fact (observations, ~4.3M rows) tuned for 8 partitions ~75 MB each and the encounters↔facts joins using sort-merge, so that the Silver layer hits its critical-path target.

## Description

Tune `clinical_observations` to write 8 partitions of ~75 MB each per LLD §6.5. Verify sort-merge join is the planner choice for encounters↔observations (340K × 4.3M) per §6.2. Add a benchmark recording p95 < 8 min for `transform_observations_silver` on DEV.

## Acceptance Criteria

- [ ] `clinical_observations` write produces 8 partition files of ~75 MB each [LLD §6.5]
- [ ] EXPLAIN on encounters↔observations join shows SortMergeJoin [LLD §6.2]
- [ ] Benchmark `tests/silver/test_silver_facts_perf.py` records p95 < 8 min for observations transform on DEV [LLD §4.4]

## Technical Notes

- **Upstream references**: LLD §4.4, §6.2 (sort-merge for fact-to-fact), §6.5 (partition tuning observations=8)
- **Implementation hints**: Use `df.repartition(8, 'patient_id')` for observations before write; check planner output via `df.explain(extended=True)`.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | §4.4, §6.2, §6.5 |
| DMS | — |
| STM | — |
| DQS | — |

## Testing

| Coverage | What | How |
|----------|------|-----|
| Benchmark | observations p95 < 8 min on DEV | `pytest -m benchmark patient_360/tests/silver/test_silver_facts_perf.py` |

## Verification

```yaml
AC1:
  - manual: "ls warehouse/dev/silver/clinical_observations/ds=*/ shows 8 part files ~75MB each"
AC2:
  - manual: "df.explain on encounters↔observations join reports SortMergeJoin"
AC3:
  - pytest: {node: "patient_360/tests/silver/test_silver_facts_perf.py", marker: "benchmark"}
```

## How to Test (User)

### Prerequisites

- STORY-04-004 complete

### Steps

1. `cd patient_360 && uv run pytest -m benchmark tests/silver/test_silver_facts_perf.py -v`
2. `ls -la patient_360/warehouse/dev/silver/clinical_observations/ds=*/`

### Expected outcome

- Step 1: observations benchmark p95 < 480s
- Step 2: 8 part-files ~75 MB each in latest ds partition

## Documentation Updates

- [ ] N/A — perf tuning, internal
