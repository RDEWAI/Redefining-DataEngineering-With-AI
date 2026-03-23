## 8. Open Questions & Risks

### Open Questions

| # | Question | Assigned To | Due Date | Status |
|---|----------|-------------|----------|--------|
| 1 | How will fuzzy name matching be implemented for patient search (Soundex, Levenshtein, other)? | Michael Torres (CIO) | 2026-02-28 | Open [DRD SS6.2 #1] |
| 2 | Which cloud platform for production deployment (Databricks, EMR, Dataproc)? | Michael Torres (CIO) | 2026-06-01 | Open |
| 3 | What are the production RTO/RPO targets? Phase 1 uses 4h/24h; production targets require compliance review. | Jennifer Martinez (Compliance) | 2026-04-30 | Open [DRD SS7.6] |
| 4 | Should schema evolution use `mergeSchema = true` or versioned schemas? | Data Engineering Team | 2026-04-15 | Open |
| 5 | Column-level lineage strategy for production (DataHub vs. Databricks UC)? UC OSS 0.4.0 has no column-level lineage API. | Data Engineering Team | 2026-06-01 | Open |
| 6 | Grafana proficiency assessment -- team capability for dashboard creation and alerting is unverified. | Data Engineering Team | 2026-04-15 | Open |
| 7 | What is the retention policy for deceased patient records? | Compliance Team | 2026-02-28 | Open [DRD SS6.2 #4] |
| 8 | SDP `@dp.materialized_view` compatibility with SCD2 Delta MERGE INTO -- does incremental refresh correctly handle SCD2 dimension updates in Silver? Requires spike/POC in sprint 1. | Data Engineering Team | 2026-04-15 | Open |
| 9 | Config-driven ingestion engine: should the generic engine use reflection/dynamic class loading or template-based code generation to create SDP `@dp.table` definitions from YAML? | Data Engineering Team | 2026-04-15 | Open |
| 10 | Airflow executor type for SDP integration: should Airflow use BashOperator (`spark-pipelines run`) or SparkSubmitOperator for invoking SDP pipeline specs? | Data Engineering Team | 2026-04-15 | Open |

### Key Risks

| Risk | Impact | Likelihood | Mitigation |
|------|--------|-----------|------------|
| Observations table (4.37M rows) hourly full snapshot exceeds local Spark memory or SLA | Pipeline failures, data freshness SLA breach | Low | Monitor runtime via Grafana; SDP parallelism helps; scale to cluster mode at 10x volume; increase shuffle partitions if runtime exceeds 30 min |
| HIPAA audit requirements not fully met in Phase 1 | Compliance gap if production traffic routed through Phase 1 | Medium -- Phase 1 is dev-only | Phase 2 adds encryption at rest, full audit logging, SSO + MFA [DRD SS7.4] |
| Team unfamiliar with UC OSS 0.4.0 | Slower development, misconfiguration | Medium | Allocate upskilling time; use `spark_catalog` default [infrastructure-constraints.md SS5] |
| Source database adds columns without notice | Bronze schema enforcement failures | Low | Use `mergeSchema` option in Bronze reads; enforce strict schema-on-write in Silver; alert on schema drift |
| Grafana not in approved technology catalog | Potential rejection during architecture review | Medium | Submit catalog update request; fall back to Marquez + Spark Expectations only if rejected |
| Full Snapshot CDC becomes unsustainable at 10x scale | Pipeline runtime exceeds 1 hour; hourly SLA missed | Low (3+ years at 5-10% growth) | Re-evaluation trigger at 50M rows or 1-hour runtime; evaluate Timestamp Watermark CDC when source provides audit columns |
| SDP Familiar-level team proficiency causes development delays | Sprint velocity below estimates in sprints 1-2 | Medium | Allocate SDP upskilling time in sprint 1; start with Bronze (simpler config-driven pattern) before Silver/Gold; fallback to manual PySpark if SDP adoption stalls |
| SDP `@dp.materialized_view` incremental refresh incompatible with SCD2 MERGE INTO | Gold tables may require full refresh instead of incremental, reducing SDP benefit | Low-Medium | POC spike in sprint 1 [Open Question #8]; if incompatible, Gold uses `@dp.table` with explicit refresh logic instead of `@dp.materialized_view` |
| Config validation gaps: runtime errors not caught by static JSON Schema | Pipeline fails mid-execution instead of fail-fast at startup | Low | Dual validation gate (static + runtime) [NFR-13]; comprehensive JSON Schema covering all field types and enum values; integration test suite for config validation |
| Dual DQ framework (SDP + SE) causes team confusion | Inconsistent DQ enforcement, rules defined in wrong tool | Medium | Clear responsibility split documented in SS6.3; code review checklist for DQ placement; team training on boundary |

---
