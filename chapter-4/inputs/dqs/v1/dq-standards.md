# Enterprise Data Quality Standards

| Field | Value |
|-------|-------|
| **Version** | 1.0 |
| **Effective Date** | 2026-01-01 |
| **Owner** | Data Quality Team |
| **Status** | Active |

---

## 1. Severity Definitions

All DQ rules must be assigned one of three severity levels. The severity
determines the pipeline action and response time when a rule fires.

| Severity | Pipeline Action | Response Time | Escalation Path |
|----------|----------------|---------------|----------------|
| **CRITICAL** | Halt pipeline or reject record | 15 minutes | On-call engineer via PagerDuty |
| **WARNING** | Log and continue / quarantine row | 4 hours | Data quality team via Slack |
| **INFO** | Record for monitoring only | Next business day | DQ dashboard only |

### When to use CRITICAL

Assign CRITICAL when failure represents a data integrity risk that will
propagate to consumers and cause incorrect business decisions:

- Primary key is NULL
- Referential integrity violation in a fact table
- Record count drops more than 5% below baseline unexpectedly
- Financial aggregate differs from source by more than 0.1%

### When to use WARNING

Assign WARNING when failure degrades data quality but does not corrupt
downstream analytics:

- Optional field has unexpected NULL rate above threshold
- Categorical field contains an unexpected enum value
- Null rate is elevated but within tolerable range
- Statistical distribution deviates from baseline within acceptable bounds

### When to use INFO

Assign INFO for observational checks that track trends without blocking:

- Slowly increasing null rates (trending but not yet at WARNING threshold)
- New categorical values not yet in the approved enum list
- Row count slightly below baseline but within normal variation

---

## 2. Rule ID Conventions

All DQ rules must follow the `DQ-{CATEGORY}-{nnn}` naming convention.

| Prefix | Category | Applies To | Example |
|--------|----------|------------|---------|
| `DQ-FLD` | Field-Level Validation | All layers | DQ-FLD-001 |
| `DQ-REF` | Referential Integrity | Silver, Gold | DQ-REF-001 |
| `DQ-STA` | Statistical Distribution | All layers | DQ-STA-001 |
| `DQ-REC` | Reconciliation | Gold vs Source | DQ-REC-001 |
| `DQ-FRS` | Freshness/SLA | All layers | DQ-FRS-001 |

### Numbering

- Start from `001` per category per DQS document
- Do not reuse numbers when rules are removed — mark removed rules as inactive
  in the version history
- Cross-DQS references use the full rule ID including the DQS document name

---

## 3. Threshold Defaults

When a specific threshold is not defined by the business, use these enterprise
defaults. Override with a documented rationale.

### Row Count Thresholds

| Scenario | Default Threshold | Rationale |
|----------|-----------------|-----------|
| Production fact tables | ±5% per batch | Normal batch variation |
| Production dimension tables | ±2% per load | Dimensions change slowly |
| Financial aggregate tables | ±0.1% | Financial accuracy requirement |
| Daily reconciliation | ±0.5% | Acceptable end-of-day drift |

### Null Rate Thresholds

| Field Classification | WARNING Threshold | CRITICAL Threshold |
|---------------------|-------------------|-------------------|
| Primary key | 0% (any NULL = CRITICAL) | 0% |
| Required business fields | > 0.5% NULL rate | > 5% NULL rate |
| Optional descriptive fields | > 10% NULL rate | > 30% NULL rate |

### Statistical Baselines

Statistical baselines must be established from actual database row counts,
not documentation estimates. The baseline is the count observed in the first
30 days of production operation. Re-baseline every 6 months or after a
major data migration.

---

## 4. Monitoring Standards

### Frequency Requirements by Severity

| Rule Type | Minimum Check Frequency | Maximum Alert Latency |
|-----------|------------------------|----------------------|
| CRITICAL field validation | Per pipeline run | 15 minutes |
| WARNING field validation | Per pipeline run | 4 hours |
| Statistical distribution | Daily | 24 hours |
| Reconciliation | Per pipeline run for financial; daily otherwise | 4 hours |
| Freshness/SLA | Every 15 minutes for clinical; every 4 hours for analytics | 15 minutes |

### Layer Coverage Requirement

Every DQS must define rules for **all three Medallion layers**:

1. **Bronze layer**: Ingestion-time format and NOT NULL checks
2. **Silver layer**: Business rule, FK, and data type checks
3. **Gold layer**: Aggregation accuracy, uniqueness, and consumer-readiness checks

DQS documents that cover only the gold layer will be rejected at review.

### Multi-Environment Enforcement

DQ rules must be configured per environment:

| Environment | Enforcement Mode | Error Threshold |
|-------------|-----------------|-----------------|
| DEV | Log only — no halts | 5% (permissive) |
| QA | Halt on CRITICAL, log WARNING | 1% (moderate) |
| PROD | Halt on CRITICAL, alert on WARNING | 0.1% (strict) |

---

## 5. Spark-Expectations Integration

The enterprise DQ execution engine is **spark-expectations** (spark_expectations)
>= 2.6.0.

### Required Rule Type Mapping

| DQ Category | SE Rule Type | Notes |
|-------------|-------------|-------|
| DQ-FLD (field validation) | `row_dq` | Per-row expression evaluation |
| DQ-REF (referential integrity) | `query_dq` | Cross-table SQL SELECT |
| DQ-STA (statistical distribution) | `agg_dq` | Aggregate SQL expression |
| DQ-REC (reconciliation) | `query_dq` | Source vs target COUNT/SUM |
| DQ-FRS (freshness) | `agg_dq` | Recency check via MAX(timestamp) |

### action_if_failed Mapping

| Severity | action_if_failed |
|----------|-----------------|
| CRITICAL | `"fail"` |
| WARNING | `"ignore"` |
| INFO | `"ignore"` |

### error_drop_threshold

Set `error_drop_threshold` as a decimal fraction (not a percentage):
- 0.001 = 0.1%
- 0.01 = 1%
- 0.05 = 5%

Use the enterprise defaults from Section 3 unless a specific threshold is
documented and approved in the DQS.

### SE Rules Output Location

Generated SE YAML files are stored at:
`outputs/dqs/v{N}/se-rules/se-rules-{table-name}.yaml`

One file per target table. File naming uses hyphens, not underscores.
