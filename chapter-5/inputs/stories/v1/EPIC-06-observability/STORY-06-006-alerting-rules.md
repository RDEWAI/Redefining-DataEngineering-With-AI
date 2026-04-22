# STORY-06-006: Alerting Rules and Allergy Escalation

| Field | Value |
|-------|-------|
| **Epic** | EPIC-06: Observability + Monitoring |
| **Priority** | P1 -- Critical Path |
| **Story Points** | 3 |
| **Sprint** | Sprint 8 |
| **Dependencies** | STORY-06-003 |
| **Status** | To Do |

## User Story

As a data operations engineer, I want alerting rules configured in Grafana with PagerDuty for CRITICAL failures and Slack for WARNING conditions so that the team responds within SLA to pipeline issues.

## Description

Configure Grafana alerting rules per LLD SS10.3 and SS8.3: (1) CRITICAL alerts to PagerDuty for DQ failures, pipeline task failures, and row count drops. (2) WARNING alerts to Slack for runtime degradation and elevated DQ warning rates. (3) Allergy-specific escalation path routing allergy DQ failures to PagerDuty + Clinical Ops Director within 10 minutes per DQS SS1.

## Acceptance Criteria

- [ ] CRITICAL alerts route to PagerDuty `p360-critical` [LLD §10.3, SS8.3]
- [ ] WARNING alerts route to Slack `#data-alerts-{env}` [LLD §10.3, SS8.3]
- [ ] Allergy DQ failures route to PagerDuty + Clinical Ops Director [LLD §8.4, DQS SS1]
- [ ] Pipeline runtime > 45 min triggers WARNING [LLD §8.3]
- [ ] Row count drop > 5% triggers CRITICAL [LLD §8.3, DQS SS3]
- [ ] DQ WARNING rate > 5% triggers WARNING [LLD §8.3]

## Technical Notes

- **Upstream references**: LLD SS10.3, SS8.3, SS8.4, DQS SS1, DQS SS3
- **Implementation hints**: Use Grafana alerting with notification channels for PagerDuty and Slack. Allergy escalation requires a separate notification policy with shorter evaluation interval (10 min vs 15 min).

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | SS10.3, SS8.3, SS8.4 |
| DMS | -- |
| STM | -- |
| DQS | SS1 (allergy escalation), SS3 (row count thresholds) |
