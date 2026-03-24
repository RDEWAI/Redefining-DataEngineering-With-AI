# STORY-08-004: Load Testing and Performance Baseline

| Field | Value |
|-------|-------|
| **Epic** | EPIC-08: Hardening + Performance |
| **Priority** | P2 -- Important |
| **Story Points** | 3 |
| **Sprint** | Sprint 10 |
| **Dependencies** | STORY-08-001, STORY-08-002 |
| **Status** | To Do |

## User Story

As a data engineer, I want load test results establishing performance baselines so that we can detect regressions and verify the pipeline completes within the 45-minute SLA.

## Description

Run the full pipeline under normal load (7.9M Phase 1 rows) in the STAGING environment. Measure and record: total pipeline runtime, per-task runtime, memory utilization, shuffle data volume, DQ check overhead. Verify total runtime < 45 minutes. Establish baselines in Grafana for ongoing monitoring.

## Acceptance Criteria

- [ ] Full pipeline completes within 45 min under normal load [DRD §4.3]
- [ ] Per-task runtimes recorded and match critical path estimates [LLD §4.4]
- [ ] Memory utilization within allocated limits (no OOM) [LLD §6.1]
- [ ] Performance baselines established in Grafana [LLD §10.2]
- [ ] Results documented with bottleneck analysis [LLD §6.5]

## Technical Notes

- **Upstream references**: DRD SS4.3 (45 min SLA), LLD SS4.4 (Critical Path ~30 min), LLD SS6
- **Implementation hints**: Run `make run-pipeline` in STAGING with full dataset. Use Spark UI history server for detailed task analysis. Record baselines as Grafana annotations.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | SS4.4, SS6.1, SS6.5 |
| DMS | -- |
| STM | -- |
| DQS | -- |
