# Orchestration Patterns

| Field | Value |
|-------|-------|
| **Version** | 1.0 |
| **Last Updated** | 2026-03-22 |
| **Owner** | Data Engineering Lead |
| **Applies To** | Patient 360 Data Pipeline |

---

## 1. DAG Naming Conventions

| Element | Convention | Example |
|---------|-----------|---------|
| DAG ID | `{domain}_{pipeline}_{version}` | `patient360_daily_v1` |
| Task ID | `{verb}_{entity}_{layer}` | `ingest_patients_bronze` |
| Task group | `{layer}_{operation}` | `bronze_ingestion` |

---

## 2. Scheduling

| Pipeline | Schedule | Timezone | Catchup |
|----------|----------|----------|---------|
| Bronze ingestion | Daily 02:00 UTC | UTC | Yes (backfill) |
| Silver transforms | Daily 03:00 UTC (after bronze) | UTC | Yes |
| Gold denormalization | Daily 04:00 UTC (after silver) | UTC | Yes |
| DQ monitoring | Hourly | UTC | No |

---

## 3. Retry & Timeout Defaults

| Task Type | Max Retries | Retry Delay | Timeout | Backoff |
|-----------|-------------|-------------|---------|---------|
| Bronze ingestion | 3 | 60s | 30 min | Exponential (2x) |
| Silver transformation | 2 | 120s | 45 min | Exponential (2x) |
| Gold denormalization | 2 | 120s | 30 min | Exponential (2x) |
| DQ validation | 1 | 30s | 15 min | Fixed |
| Reconciliation | 1 | 60s | 20 min | Fixed |

---

## 4. Dependency Patterns

### 4.1 Layer Dependencies

```
Bronze (all tables) → DQ Gate (bronze) → Silver (all tables) → DQ Gate (silver) → Gold (all tables) → DQ Gate (gold)
```

### 4.2 Intra-Layer Parallelism

| Layer | Strategy | Notes |
|-------|----------|-------|
| Bronze | Full parallel | All 13 tables ingested independently |
| Silver | Partial parallel | Dimension tables first (patients, providers, payers, organizations), then fact tables |
| Gold | Sequential | patient_summary → patient_clinical_history → patient_billing_summary |

### 4.3 DQ Gates

| Gate | Trigger | Action on CRITICAL Failure |
|------|---------|---------------------------|
| Bronze DQ | After all bronze tasks | Block silver processing, alert data-ops |
| Silver DQ | After all silver tasks | Block gold processing, alert data-ops |
| Gold DQ | After all gold tasks | Block consumer access, alert clinical-ops |

---

## 5. Alerting Channels

| Severity | Channel | Response Time |
|----------|---------|---------------|
| CRITICAL | PagerDuty (`p360-critical`) | 15 min |
| WARNING | Slack `#data-alerts-{env}` | 1 hour |
| INFO | Grafana dashboard only | Next business day |

### 5.1 Escalation Path

1. Primary on-call (data engineer) — 15 min
2. Secondary on-call (senior data engineer) — 30 min
3. Engineering manager — 1 hour
4. For allergy DQ failures: Clinical Ops Director — 10 min (elevated path)

---

## 6. Idempotency Patterns

| Pattern | Usage | Implementation |
|---------|-------|----------------|
| `replaceWhere` | All Delta writes | `replaceWhere = "ds = '{run_date}'"` |
| Checkpoint | Pipeline state recovery | JSON checkpoint per task |
| Deduplication | Bronze ingestion | `dropDuplicates(["id", "ds"])` |

---

## 7. Sensor / Trigger Patterns

| Trigger | Type | Configuration |
|---------|------|---------------|
| Source data availability | File sensor | Check `_SUCCESS` marker |
| Upstream pipeline completion | DAG sensor | Wait for bronze DAG completion |
| Manual trigger | API / UI | For ad-hoc backfills |
