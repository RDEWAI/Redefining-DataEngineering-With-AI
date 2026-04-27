# STORY-05-004: Gold perf — cache patients/encounters, partition tuning

| Field | Value |
|-------|-------|
| **Epic** | EPIC-05: Gold Consumer Layer |
| **Story Type** | performance-optimization |
| **Priority** | P2 |
| **Story Points** | 3 |
| **Sprint** | 4 |
| **Dependencies** | STORY-05-003 |
| **Status** | To Do |

## User Story

As a Data Engineer, I want Gold builds tuned with cached patient + encounters dim, broadcast small dims, and right-sized partitions so that the Gold layer hits the LLD §4.4 critical-path target (~3 min per Gold table).

## Description

Apply LLD §6.4 caching strategy — cache `clinical_patients` (current, ~2 MB) and `clinical_encounters` (~50 MB) once and reuse across all 3 Gold builders. Tune `patient_summary` to write 1 partition (~5 MB). Add a benchmark recording p95 < 3 min per Gold table on DEV.

## Acceptance Criteria

- [ ] Gold builders use `cache()` on `clinical_patients` and `clinical_encounters` per §6.4 [LLD §6.4]
- [ ] `patient_summary` writes 1 partition file (~5 MB) per LLD §6.5 [LLD §6.5]
- [ ] Benchmark `tests/gold/test_gold_perf.py` records p95 < 3 min per Gold table on DEV [LLD §4.4]
- [ ] Cached DataFrames freed (`unpersist()`) after Gold layer completes [LLD §6.4]

## Technical Notes

- **Upstream references**: LLD §4.4 critical path, §6.4 caching, §6.5 partition tuning
- **Implementation hints**: Cache once in a Gold orchestration helper invoked before the 3 builders run.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | §4.4, §6.4, §6.5 |
| DMS | — |
| STM | — |
| DQS | — |

## Testing

| Coverage | What | How |
|----------|------|-----|
| Benchmark | Each Gold table p95 < 3 min on DEV | `pytest -m benchmark patient_360/tests/gold/test_gold_perf.py` |

## Verification

```yaml
AC1:
  - grep_count: {glob: "patient_360/src/patient_360/gold/build_*.py", pattern: '\.cache\(\)|persist\(', equals: 3}
AC2:
  - manual: "ls warehouse/dev/gold/patient_summary/ shows 1 part file ~5MB"
AC3:
  - pytest: {node: "patient_360/tests/gold/test_gold_perf.py", marker: "benchmark"}
AC4:
  - grep_count: {glob: "patient_360/src/patient_360/gold/build_*.py", pattern: 'unpersist|uncache', equals: 3}
```

## How to Test (User)

### Prerequisites

- STORY-05-003 complete

### Steps

1. `cd patient_360 && uv run pytest -m benchmark tests/gold/test_gold_perf.py -v`

### Expected outcome

- Each Gold benchmark p95 < 180s

## Documentation Updates

- [ ] N/A — perf tuning, internal
