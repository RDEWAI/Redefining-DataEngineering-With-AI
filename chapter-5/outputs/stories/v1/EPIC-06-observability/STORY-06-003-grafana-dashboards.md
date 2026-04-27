# STORY-06-003: Grafana DQ + pipeline-runtime dashboards + alerting rules

| Field | Value |
|-------|-------|
| **Epic** | EPIC-06: Observability — Lineage, Metrics, Dashboards |
| **Story Type** | observability |
| **Priority** | P2 |
| **Story Points** | 3 |
| **Sprint** | 4 |
| **Dependencies** | STORY-06-001, STORY-06-002 |
| **Status** | To Do |

## User Story

As a Data Engineer, I want a Grafana dashboard for pipeline runtime + DQ pass rate and Prometheus alerting rules wired to PagerDuty/Slack so that operators see and are paged on issues per LLD §8.5 thresholds.

## Description

Author Grafana dashboard JSON under `patient_360/_infra/docker/observability/grafana/dashboards/` for: (1) pipeline runtime per layer; (2) DQ pass rate per table from `*_se_stats`; (3) SE error drop rate per table; (4) DLQ row count per LLD §10.2. Add Prometheus alerting rules per LLD §8.5 (pipeline runtime > 45m, allergy DQ failure, etc.) routing to PagerDuty + Slack `#data-alerts-{env}`.

## Acceptance Criteria

- [ ] `patient_360/_infra/docker/observability/grafana/dashboards/pipeline_overview.json` exists [LLD §10.2]
- [ ] Dashboard renders DQ pass rate from `*_se_stats` tables [LLD §10.2]
- [ ] `patient_360/_infra/docker/observability/prometheus/alerts.yml` declares all §8.5 alerts [LLD §8.5, §10.3]
- [ ] Allergy DQ failure rule routes to PagerDuty (elevated path) [DQS §1, LLD §8.5]

## Technical Notes

- **Upstream references**: LLD §8.5 (alerting thresholds), §10.2 (dashboard specs), §10.3 (alerting rules)
- **Implementation hints**: Provision dashboards via Grafana's `provisioning/dashboards/` directory mounted into the container.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | §8.5, §10.2, §10.3 |
| DMS | — |
| STM | — |
| DQS | §1 (escalation) |

## Testing

| Coverage | What | How |
|----------|------|-----|
| Manual | Grafana renders dashboard panels with live data | UI inspection at `http://localhost:3000` |
| Unit | Prometheus rules YAML parses | `pytest patient_360/tests/observability/test_alerts_yaml_unit.py` |

## Verification

```yaml
AC1:
  - file_exists: "patient_360/_infra/docker/observability/grafana/dashboards/pipeline_overview.json"
AC2:
  - grep: {file: "patient_360/_infra/docker/observability/grafana/dashboards/pipeline_overview.json", pattern: 'se_stats|dq_pass_rate'}
AC3:
  - file_exists: "patient_360/_infra/docker/observability/prometheus/alerts.yml"
  - grep: {file: "patient_360/_infra/docker/observability/prometheus/alerts.yml", pattern: 'pipeline_runtime'}
AC4:
  - grep: {file: "patient_360/_infra/docker/observability/prometheus/alerts.yml", pattern: 'allergy|clinical_allergies'}
```

## How to Test (User)

### Prerequisites

- STORY-06-001, STORY-06-002 complete

### Steps

1. `open http://localhost:3000`  (login admin/admin or docker default)
2. Open dashboard "Patient 360 Pipeline Overview"
3. `curl -sS http://localhost:9090/api/v1/rules | jq '.data.groups[].rules[].name'`

### Expected outcome

- Step 2: panels render with non-empty data after the latest pipeline run
- Step 3: lists pipeline_runtime, dq_pass_rate, allergy_dq_failure rules

## Documentation Updates

- [ ] Update `patient_360/_infra/docker/observability/README.md` § "Grafana dashboards" with dashboard names and Prometheus rule list
