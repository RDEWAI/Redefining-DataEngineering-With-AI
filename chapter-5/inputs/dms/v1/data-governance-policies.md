# Data Governance Policies

| Field | Value |
|---|---|
| **Version** | 1.0 |
| **Last Updated** | 2026-03-16 |
| **Owner** | Data Governance & Compliance Team |
| **Regulation** | HIPAA (Health Insurance Portability and Accountability Act) |

---

## 1. Data Classification

All columns in the data platform are classified into one of four tiers:

| Classification | Definition | Examples | Handling |
|---------------|-----------|----------|----------|
| **PHI** | Protected Health Information — any data that can identify a patient combined with health information | Patient name, SSN, DOB, address, phone, email, medical record number | Encryption at rest, access logging, role-restricted |
| **PII** | Personally Identifiable Information — subset of PHI that identifies a person without health context | SSN, driver's license, passport number | Drop from Silver/Gold layers entirely |
| **Sensitive** | Business-sensitive data not subject to HIPAA but restricted | Provider compensation, contract terms, internal cost rates | Role-restricted access |
| **Internal** | Non-sensitive operational data | Encounter class, condition codes, medication codes, pipeline metadata | Standard access controls |

---

## 2. PHI Handling Rules

### 2.1 Columns to Drop at Bronze-to-Silver Boundary

These columns contain PII that is **not needed** for clinical analytics or Patient 360 use cases. They must be excluded from Silver and Gold layers:

| Source Table | Column | Reason for Exclusion |
|-------------|--------|---------------------|
| `patients` | `SSN` | Social Security Number — never needed for clinical analytics |
| `patients` | `DRIVERS` | Driver's license number — no analytical value |
| `patients` | `PASSPORT` | Passport number — no analytical value |

### 2.2 Columns Requiring Encryption at Rest

| Layer | Columns | Method |
|-------|---------|--------|
| Bronze | All PHI columns (preserved as-is from source) | Delta Lake encryption or filesystem-level encryption |
| Silver | `patient_name`, `birth_date`, `address`, `phone`, `email` | Column-level encryption or tokenization in production |
| Gold | `dim_patient`: `first_name`, `last_name`, `birth_date`, `address_*` | Same as Silver |

### 2.3 Non-Production Masking Rules

| Column | Masking Rule |
|--------|-------------|
| `first_name`, `last_name` | Replace with `PATIENT_XXXX` (hash-based pseudonym) |
| `birth_date` | Shift by random offset (±180 days), preserve year |
| `address`, `city`, `zip` | Replace with synthetic address |
| `phone` | Replace with `555-0XXX` pattern |

---

## 3. Retention Policies

| Layer | Retention Period | Rationale |
|-------|-----------------|-----------|
| Bronze (raw) | Indefinite | Audit trail — raw data must be recoverable for compliance investigations |
| Silver (cleansed) | 7 years minimum | HIPAA requires 6 years; ZenHealth policy adds 1-year buffer |
| Gold (analytical) | Per consumer SLA | Clinical: 3 years active + 4 years archive. Analytics: 2 years rolling |
| Pipeline metadata | 3 years | DQ results, lineage records, job execution logs |
| Session memory | 1 year | Agent session notes in `memory/` directories |

**Deletion procedure**: Data deletion requires approval from the Data Governance Committee. No automated deletion pipelines — all purges are manual with audit logging.

---

## 4. Access Control (RBAC)

| Role | Bronze | Silver (Clinical) | Silver (Billing) | Gold (Analytics) | Pipeline Admin |
|------|--------|-------------------|-------------------|------------------|----------------|
| **Clinical User** (physicians, nurses) | No | Read | No | Read (PHI visible) | No |
| **Care Coordinator** | No | Read | No | Read (PHI visible) | No |
| **Billing Staff** | No | No | Read | Read (de-identified) | No |
| **Department Head** | No | Read | Read | Read (PHI visible) | No |
| **Data Analyst** | No | No | No | Read (de-identified) | No |
| **Data Engineer** | Read | Read/Write | Read/Write | Read/Write | Yes |
| **DBA / Platform Admin** | Read | Read | Read | Read | Yes |

**De-identified access**: Analysts and billing staff see `dim_patient` with masked names and shifted dates. Clinical users and care coordinators see unmasked PHI.

---

## 5. Audit Requirements

| Requirement | Implementation |
|------------|----------------|
| Schema change logging | All DDL changes (CREATE, ALTER, DROP) logged with timestamp, user, and before/after state |
| PHI access logging | Every query touching PHI columns logged with user, timestamp, and query text |
| Data lineage | Column-level lineage from Gold back to source — maintained via OpenLineage/Marquez |
| DQ rule changes | Version-controlled DQ rule definitions — changes tracked in git |
| Pipeline execution | Every pipeline run logged with start/end time, records processed, DQ pass/fail counts |
| Incident response | Data quality incidents documented with root cause, impact assessment, and remediation |

---

## 6. SCD Policy Guidelines

| Guideline | Policy |
|-----------|--------|
| **Default for patient demographics** | SCD Type 2 — track historical changes for address, insurance, marital status, phone |
| **Default for clinical attributes** | SCD Type 1 — overwrite for race, ethnicity, gender (changes are corrections, not history) |
| **Default for reference data** | SCD Type 1 — provider specialty, organization name (historical values rarely needed) |
| **Deviation policy** | Any deviation from defaults requires documented rationale citing a DRD business requirement |
| **Effective dating** | All Type 2 dimensions use `effective_from` (DATE), `effective_to` (DATE, default `9999-12-31`), `is_current` (BOOLEAN) |
| **Surrogate keys** | All Gold dimensions use surrogate keys (`_sk` suffix) — never expose natural keys as primary keys in Gold |

---

## 7. Data Quality Governance

| Area | Policy |
|------|--------|
| **DQ rule ownership** | Every DQ rule must have an assigned owner (role, not person) |
| **Severity classification** | CRITICAL: halts pipeline. WARNING: logs and continues. INFO: monitoring only |
| **Threshold review** | DQ thresholds reviewed quarterly by Data Governance Committee |
| **New table onboarding** | Every new table must have ≥1 not-null check, ≥1 uniqueness check, and ≥1 row-count check before promotion to production |
| **Reconciliation** | All Gold tables used in executive reporting must have source-to-target reconciliation rules |

---

## 8. Change Management

| Change Type | Approval Required | Process |
|------------|-------------------|---------|
| New table (any layer) | Data Engineer + Tech Lead | PR with schema definition, DQ rules, and lineage documentation |
| Column addition | Data Engineer | PR with impact assessment on downstream consumers |
| Column removal | Data Governance Committee | 30-day deprecation notice, consumer impact analysis, PR with migration plan |
| Data type change | Data Engineer + Tech Lead | PR with transformation logic for existing data |
| SCD type change | Data Governance Committee | Business justification required — affects historical data availability |
| PHI classification change | Compliance Officer | Formal review with legal team |
