# SLA Definitions for Patient 360 Pipeline

| Field | Value |
|-------|-------|
| **Version** | 1.0 |
| **Effective Date** | 2026-01-01 |
| **Owner** | Data Platform Team |
| **DRD Reference** | DRD-2026-02-11-patient-360.md |
| **Status** | Active |

---

## 1. Consumer Groups

The Patient 360 pipeline serves four consumer groups with distinct freshness
and availability requirements.

| Consumer Group | Department | Use Case | Priority | Access Pattern |
|---------------|------------|----------|----------|----------------|
| Clinical Dashboard | Clinical Operations | Real-time patient lookup | P1 | Real-time, 100+ queries/day |
| BI Analytics Team | Analytics | Trend analysis, reporting | P2 | Batch, daily refresh |
| Regulatory Reporting | Compliance | HIPAA audit reports | P3 | Monthly batch extraction |
| Data Science | Research | Model training, exploration | P4 | Ad hoc, weekly refresh |

---

## 2. Freshness Requirements

### By Consumer Group

| Consumer Group | Gold Table | Max Latency | Measurement Point | DRD Reference |
|---------------|------------|-------------|-------------------|---------------|
| Clinical Dashboard | analytics.dim_patient | 1 hour | Pipeline completion | DRD §4.4 |
| Clinical Dashboard | analytics.fact_encounter | 1 hour | Pipeline completion | DRD §4.4 |
| Clinical Dashboard | analytics.fact_condition | 1 hour | Pipeline completion | DRD §4.4 |
| BI Analytics Team | analytics.dim_patient | 24 hours | Pipeline completion | DRD §4.4 |
| BI Analytics Team | analytics.fact_encounter | 24 hours | Pipeline completion | DRD §4.4 |
| Regulatory Reporting | All gold tables | 30 days | Report generation | DRD §7.1 |
| Data Science | All gold tables | 7 days | Table refresh | DRD §4.4 |

### Freshness Check Query

The freshness check compares the current timestamp against the maximum pipeline
completion timestamp in the target table:

```sql
SELECT
  table_name,
  MAX(_pipeline_completed_at) AS last_refresh,
  CURRENT_TIMESTAMP - MAX(_pipeline_completed_at) AS age,
  CASE
    WHEN CURRENT_TIMESTAMP - MAX(_pipeline_completed_at) > INTERVAL '1 hour'
    THEN 'STALE'
    ELSE 'FRESH'
  END AS freshness_status
FROM analytics.dim_patient
```

---

## 3. Reconciliation Tolerances

### Row Count Tolerances

| Source → Target Path | Tolerance | Rationale | Escalation |
|---------------------|-----------|-----------|------------|
| synthea.patients → bronze.patients | 0% | Full snapshot — must match exactly | CRITICAL |
| bronze.patients → clinical.patients | 0% | No filtering in bronze-to-silver | CRITICAL |
| clinical.patients → analytics.dim_patient (is_current) | ±0.1% | SCD2 current rows | CRITICAL |
| synthea.encounters → analytics.fact_encounter | ±0.1% | All encounters must land | CRITICAL |
| bronze.conditions → analytics.fact_condition | ±1% | Some conditions filtered | WARNING |

### Aggregate Sum Tolerances

| Source Aggregate | Target Aggregate | Tolerance | Rationale |
|-----------------|-----------------|-----------|-----------|
| SUM(base_encounter_cost) source | SUM(base_cost) gold | ±0.01% | Financial accuracy |
| COUNT(DISTINCT patient_id) | COUNT(DISTINCT patient_sk) is_current | ±0.1% | Deduplication |

---

## 4. Completeness Targets

Completeness targets define the minimum percentage of non-null values required
for each field classification.

| Field Classification | Minimum Completeness | CRITICAL Threshold | WARNING Threshold |
|--------------------|---------------------|-------------------|------------------|
| Primary keys | 100% | < 99.9% | N/A (hard fail) |
| Patient identifiers | 100% | < 99.9% | N/A (hard fail) |
| Required clinical fields | 99% | < 95% | < 99% |
| Optional clinical fields | 90% | < 70% | < 90% |
| Reference data fields | 95% | < 90% | < 95% |
| Derived/calculated fields | 98% | < 90% | < 98% |

### Per-Table Completeness Requirements (Gold Layer)

| Table | Column | Minimum Completeness | Severity if Breached |
|-------|--------|---------------------|---------------------|
| analytics.dim_patient | patient_id | 100% | CRITICAL |
| analytics.dim_patient | full_name | 99% | WARNING |
| analytics.dim_patient | birth_date | 95% | WARNING |
| analytics.dim_patient | gender | 98% | WARNING |
| analytics.fact_encounter | encounter_sk | 100% | CRITICAL |
| analytics.fact_encounter | patient_sk | 100% | CRITICAL |
| analytics.fact_encounter | encounter_date | 99% | CRITICAL |

---

## 5. Incident Response

### SLA Breach Response Procedures

When an SLA is breached (table is stale beyond the defined max latency), the
following response procedure applies:

#### P1 — Clinical Dashboard (1-hour SLA)

1. **Immediate** (0-15 min): PagerDuty alert fires automatically
2. **Response** (15-30 min): On-call data engineer assesses pipeline status
3. **Communication** (30 min): Notify Clinical Operations Director via email
4. **Resolution target**: Pipeline restored within 2 hours of breach
5. **Post-incident**: Root cause analysis within 24 hours

#### P2 — BI Analytics (24-hour SLA)

1. **Detection** (0-4 hours): Automated Slack alert to #data-quality channel
2. **Response** (4-8 hours): Data quality team reviews pipeline logs
3. **Communication** (8 hours): Notify Analytics Manager via Slack
4. **Resolution target**: Resolved within next scheduled batch

#### P3 — Regulatory Reporting (30-day SLA)

1. **Detection**: Weekly freshness check
2. **Response**: Data platform team schedules ad hoc run
3. **Communication**: Email to Compliance team if >5 days before deadline

### Escalation Contacts

| Tier | Contact | Channel | Response Time |
|------|---------|---------|---------------|
| On-call engineer | data-oncall@hospital.org | PagerDuty | 15 minutes |
| Data quality team lead | dq-lead@hospital.org | Slack DM | 2 hours |
| Data platform manager | platform-mgr@hospital.org | Email | 4 hours |
| Clinical Operations Director | clin-ops@hospital.org | Email | 4 hours |
| Compliance Officer | compliance@hospital.org | Email | 1 business day |

### Notification Channels

| Severity | Primary Channel | Secondary Channel | Audience |
|----------|----------------|-------------------|----------|
| CRITICAL | PagerDuty | Slack #data-alerts | On-call + team lead |
| WARNING | Slack #data-quality | Email digest | DQ team |
| INFO | Email digest | DQ dashboard | DQ team weekly review |
