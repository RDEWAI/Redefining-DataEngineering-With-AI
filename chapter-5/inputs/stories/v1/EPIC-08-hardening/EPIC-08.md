# EPIC-08: Hardening + Performance

| Field | Value |
|-------|-------|
| **LLD Section** | Phase 8 (LLD impl-sequence) |
| **Stories** | 6 |
| **Total Points** | 17 |
| **Sprints** | Sprint 10 |
| **Status** | To Do |

## Objective

Optimize performance (observations tuning, broadcast joins, caching), schedule Delta maintenance, run load tests to establish baselines, perform security review for PHI compliance, and complete documentation and coverage audit for production readiness.

## Scope

### In Scope
- Observations table performance tuning
- Broadcast join and caching optimization for Gold
- Delta VACUUM and OPTIMIZE scheduling
- Load testing and performance baseline establishment
- Security review and PHI verification
- Documentation and coverage audit

### Out of Scope
- New feature development
- Capacity planning for future phases

## Stories

| ID | Title | Points | Sprint | Dependencies |
|----|-------|--------|--------|-------------|
| STORY-08-001 | Performance Tuning for Observations Table | 3 | Sprint 10 | STORY-07-003 |
| STORY-08-002 | Broadcast Join and Caching Optimization | 3 | Sprint 10 | STORY-07-003 |
| STORY-08-003 | Delta VACUUM and OPTIMIZE Scheduling | 2 | Sprint 10 | STORY-07-003 |
| STORY-08-004 | Load Testing and Performance Baseline | 3 | Sprint 10 | STORY-08-001, STORY-08-002 |
| STORY-08-005 | Security Review and PHI Verification | 3 | Sprint 10 | STORY-07-003 |
| STORY-08-006 | Documentation and Coverage Audit | 3 | Sprint 10 | STORY-08-004 |

## Acceptance Criteria (Epic-Level)

- [ ] Pipeline completes within 45 min under normal load [DRD §4.3]
- [ ] Observations processes within 8 min [LLD §4.4]
- [ ] Gold joins use broadcast (no shuffles) [LLD §6.2]
- [ ] SSN absent from all Silver and Gold tables [DRD §7]
- [ ] Unit test coverage >= 90%, CRITICAL DQ rules 100% [LLD §2.4]
- [ ] Performance baselines established in Grafana [LLD §10.2]

## Risks & Assumptions

- Performance regression under load -- mitigated by baseline metrics from Phase 6
- Assumption: STAGING environment available for load testing
- Go/no-go decision for production deployment at epic completion
