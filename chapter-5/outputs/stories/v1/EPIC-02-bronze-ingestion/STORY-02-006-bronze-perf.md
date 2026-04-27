# STORY-02-006: Bronze perf — replaceWhere partition pruning + shuffle tuning

| Field | Value |
|-------|-------|
| **Epic** | EPIC-02: Bronze Ingestion Layer |
| **Story Type** | performance-optimization |
| **Priority** | P2 |
| **Story Points** | 3 |
| **Sprint** | 2 |
| **Dependencies** | STORY-02-005 |
| **Status** | To Do |

## User Story

As a Data Engineer, I want Bronze writes tuned for partition pruning and right-sized shuffle so that the layer hits the LLD §4.4 critical-path target (≤ 5 min on DEV).

## Description

Tune `spark.sql.shuffle.partitions` to 8 (DEV) / 16 (STAGING) / 32 (PROD) and verify `replaceWhere ds = '<ds>'` partition pruning is actually exercised on the largest tables (observations 4.4M, procedures 946K) per LLD §6.3 + §6.5. Add a benchmark test capturing wall-clock per table.

## Acceptance Criteria

- [ ] `spark.sql.shuffle.partitions` set per-env in `_infra/cd/config/{env}.yaml` (8/16/32) [LLD §6.3]
- [ ] `synthea_observations` writes 8 target partitions of ~100 MB each [LLD §6.5]
- [ ] `replaceWhere` partition pruning measured (only target ds partition rewritten) [LLD §4.5, §6.5]
- [ ] Benchmark `tests/bronze/test_bronze_perf.py` records p95 wall-clock under 5 min for full Bronze TaskGroup on DEV [LLD §4.4]

## Technical Notes

- **Upstream references**: LLD §4.4 (critical path), §4.5 (replaceWhere idempotency), §6.3 (parallelism), §6.5 (partition tuning)
- **Implementation hints**: Use `EXPLAIN` on the Delta write plan to confirm the data file scan is partition-pruned. Pin `spark.databricks.delta.optimize.repartition.enabled=true` if file-size targets aren't hit.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | §4.4, §4.5, §6.3, §6.5 |
| DMS | — |
| STM | — |
| DQS | — |

## Testing

| Coverage | What | How |
|----------|------|-----|
| Benchmark | Bronze layer p95 < 5 min on DEV | `pytest -m benchmark patient_360/tests/bronze/test_bronze_perf.py` |

## Verification

```yaml
AC1:
  - grep: {file: "patient_360/_infra/cd/config/dev.yaml", pattern: 'shuffle_partitions:\s*8'}
  - grep: {file: "patient_360/_infra/cd/config/prod.yaml", pattern: 'shuffle_partitions:\s*32'}
AC2:
  - manual: "verify observations write produces 8 partition files of ~100MB each"
AC3:
  - manual: "EXPLAIN shows partition pruning on replaceWhere"
AC4:
  - pytest: {node: "patient_360/tests/bronze/test_bronze_perf.py", marker: "benchmark"}
```

## How to Test (User)

### Prerequisites

- STORY-02-005 complete; full Bronze runnable end-to-end

### Steps

1. `cd patient_360 && uv run pytest -m benchmark tests/bronze/test_bronze_perf.py -v`
2. `cd patient_360 && ls -la warehouse/dev/bronze/synthea_observations/ds=*/`

### Expected outcome

- Step 1: benchmark passes; p95 < 300s
- Step 2: 8 part-files of roughly equal size in the latest ds partition

## Documentation Updates

- [ ] N/A — perf tuning, internal; benchmarks linked from `_infra/cd/config/README.md` § "Spark tuning"
