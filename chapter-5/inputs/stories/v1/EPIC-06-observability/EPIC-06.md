# EPIC-06: Observability + Monitoring

| Field | Value |
|-------|-------|
| **LLD Section** | Phase 6 (LLD impl-sequence) |
| **Stories** | 6 |
| **Total Points** | 19 |
| **Sprints** | Sprint 8 |
| **Status** | To Do |

## Objective

Implement data lineage tracking via OpenLineage/Marquez, metrics emission via OpenTelemetry/Prometheus, Grafana dashboards (pipeline health, DQ scores, SLA tracking), and alerting rules with allergy-specific escalation path.

## Scope

### In Scope
- OpenLineage integration with Marquez
- OpenTelemetry metrics emission to Prometheus
- 3 Grafana dashboards (Pipeline Health, DQ Scores, SLA Tracking)
- Alerting rules: PagerDuty for CRITICAL, Slack for WARNING
- Allergy escalation path to Clinical Ops Director

### Out of Scope
- CI/CD pipeline (EPIC-07)
- Performance tuning (EPIC-08)

## Stories

| ID | Title | Points | Sprint | Dependencies |
|----|-------|--------|--------|-------------|
| STORY-06-001 | OpenLineage Integration | 5 | Sprint 8 | STORY-05-006 |
| STORY-06-002 | OpenTelemetry Metrics Emission | 3 | Sprint 8 | STORY-05-006 |
| STORY-06-003 | Grafana Pipeline Health Dashboard | 3 | Sprint 8 | STORY-06-002 |
| STORY-06-004 | Grafana DQ Scores Dashboard | 3 | Sprint 8 | STORY-06-002 |
| STORY-06-005 | Grafana SLA Tracking Dashboard | 2 | Sprint 8 | STORY-06-002 |
| STORY-06-006 | Alerting Rules and Allergy Escalation | 3 | Sprint 8 | STORY-06-003 |

## Acceptance Criteria (Epic-Level)

- [ ] Lineage events visible in Marquez UI [LLD §10.1]
- [ ] Metrics visible in Prometheus and queryable by Grafana [LLD §10.1]
- [ ] 3 Grafana dashboards operational [LLD §10.2]
- [ ] CRITICAL alerts route to PagerDuty within 15 min [LLD §8.3]
- [ ] Allergy DQ failures route to Clinical Ops Director within 10 min [LLD §8.4, DQS SS1]
- [ ] Observability is non-blocking (circuit breaker pattern) [LLD §8.5]

## Risks & Assumptions

- Marquez/Grafana connectivity issues -- mitigated by circuit breaker pattern (non-blocking)
- Assumption: Docker Compose services from EPIC-01 include Marquez, Grafana, Prometheus
