# STORY-03-003: Silver-dims perf — broadcast small dims + shuffle tuning

| Field | Value |
|-------|-------|
| **Epic** | EPIC-03: Silver Dimensions Layer (SCD Type 2) |
| **Story Type** | performance-optimization |
| **Priority** | P2 |
| **Story Points** | 3 |
| **Sprint** | 3 |
| **Dependencies** | STORY-03-002 |
| **Status** | To Do |

## User Story

As a Data Engineer, I want Silver dimension transforms tuned for broadcast joins and right-sized shuffle so that the SCD2 MERGE INTO completes in well under 5 minutes per dim on DEV.

## Description

Set `spark.sql.autoBroadcastJoinThreshold=50m` and apply `broadcast()` hint when joining small dims to Bronze for change detection per LLD §6.2. Verify shuffle.partitions matches per-env values (8/16/32). Add a benchmark test asserting p95 wall-clock < 4 min per dim transform on DEV.

## Acceptance Criteria

- [ ] `spark.sql.autoBroadcastJoinThreshold` set to 50m in DEV/STAGING/PROD configs [LLD §6.2]
- [ ] All 4 dim transforms use `broadcast()` hint where applicable per §6.2 [LLD §6.2]
- [ ] Benchmark `tests/silver/test_silver_dims_perf.py` records p95 < 4 min per dim on DEV [LLD §4.4]
- [ ] EXPLAIN plan shows BroadcastHashJoin for small dim joins [LLD §6.2]

## Technical Notes

- **Upstream references**: LLD §6.2 Join Strategy, §6.3 Parallelism, §6.4 Caching
- **Implementation hints**: `df_dim = broadcast(spark.table('unity.silver.reference_payers').filter('is_current = true'))` for joins.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | §4.4, §6.2, §6.3, §6.4 |
| DMS | — |
| STM | — |
| DQS | — |

## Testing

| Coverage | What | How |
|----------|------|-----|
| Benchmark | Each Silver dim p95 < 4 min on DEV | `pytest -m benchmark patient_360/tests/silver/test_silver_dims_perf.py` |

## Verification

```yaml
AC1:
  - grep: {file: "patient_360/_infra/cd/config/dev.yaml", pattern: 'autoBroadcastJoinThreshold|broadcast_threshold'}
AC2:
  - grep_count: {glob: "patient_360/src/patient_360/silver/transform_*.py", pattern: 'broadcast\(', equals: 4}
AC3:
  - pytest: {node: "patient_360/tests/silver/test_silver_dims_perf.py", marker: "benchmark"}
AC4:
  - manual: "EXPLAIN on a representative join shows BroadcastHashJoin"
```

## How to Test (User)

### Prerequisites

- STORY-03-002 complete

### Steps

1. `cd patient_360 && uv run pytest -m benchmark tests/silver/test_silver_dims_perf.py -v`

### Expected outcome

- All 4 dim benchmarks p95 < 240s

## Documentation Updates

- [ ] N/A — perf tuning, internal
