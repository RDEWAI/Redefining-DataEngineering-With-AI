## 2. Requirements Summary

### 2.1 Functional Requirements

| # | Functional Requirement | DRD Reference | Satisfied By |
|---|------------------------|---------------|--------------|
| FR-1 | Unified patient search across demographics, conditions, medications, allergies, and encounters | DRD §1.1 | Gold: patient_summary |
| FR-2 | Full encounter and clinical history view for pre-appointment review | DRD §4.2 | Gold: patient_clinical_history |
| FR-3 | Billing summary with encounter costs and claims — isolated from clinical views | DRD §5.5 | Gold: patient_billing_summary |
| FR-4 | Ingest all 13 Phase 1 source tables from Synthea Healthcare EHR | DRD §2.2 | Bronze layer — Full Snapshot CDC for all 13 tables |
| FR-5 | Track patient demographic changes (address, name, insurance) over time | DRD §1.2 | Silver: SCD Type 2 on patients, providers, payers, organizations |
| FR-6 | Compute derived clinical fields: calculated_age, medication_status, is_30_day_readmission, total_visit_cost | DRD §5.2 | Silver layer transformation |
| FR-7 | Enforce referential integrity across all fact-to-dimension relationships | DRD §3.3 | Silver DQ Gate 2 — FK checks via Spark Expectations |
| FR-8 | Allergy information must always be visible; NULL severity displayed as "Unknown" | DRD §5.4 | Gold gate assertion + Silver default value rule |
| FR-9 | Apply default values: NULL costs → 0, NULL allergy severity → "Unknown" | DRD §5.1 | Silver transformation layer |
| FR-10 | Capture full data lineage from source to Gold across all pipeline jobs | DRD §7.5 | OpenLineage events emitted to Marquez at every layer |

### 2.2 Non-Functional Requirements

| # | Non-Functional Requirement | DRD Reference | Satisfied By | Target |
|---|---------------------------|---------------|--------------|--------|
| NFR-1 | Patient search query response time | DRD §4.3 | Gold layer denormalization + Delta Lake columnar reads | < 2s at p90 |
| NFR-2 | Data freshness for clinical users (physicians, nurses) | DRD §4.4 | Hourly Full Snapshot CDC pipeline | ≤ 1 hour |
| NFR-3 | Data freshness for billing and administrative users | DRD §4.4 | Hourly batch covers daily SLA | ≤ 24 hours |
| NFR-4 | Patient data completeness in Gold layer | DRD §4.3 | Gold gate assertion: all 5,767 patients present in patient_summary | 100% |
| NFR-5 | Pipeline idempotency — re-running same date produces identical results | infrastructure-constraints.md §2 | Partition-by-`ds` with `replaceWhere` in all layers | 100% |
| NFR-6 | SSN masked to last 4 digits in all layers | DRD §3.5 | Silver transformation; enforced at write time | Always applied |
| NFR-7 | HIPAA audit trail: log all patient record access | DRD §7.5 | OpenLineage job-level lineage (Phase 1); app audit logs (Phase 2) | All access logged |
| NFR-8 | Patient record retention | DRD §7.3 | Delta time travel + cold storage archival policy | 6 years minimum |
| NFR-9 | Claims and billing record retention | DRD §7.3 | Delta time travel + cold storage archival policy | 7 years minimum |
| NFR-10 | Recovery time objective (Phase 1 dev environment) | DRD §7.6 | Idempotent pipeline re-run from source EHR | RTO ≤ 4 hours |
| NFR-11 | Recovery point objective (Phase 1 dev environment) | DRD §7.6 | Hourly batch cadence; source EHR is system of record | RPO ≤ 24 hours |
| NFR-12 | Source database access must be read-only | DRD §1.5 | All queries use `-readonly` flag; no write operations permitted | Enforced by pre-tool hook |

---
