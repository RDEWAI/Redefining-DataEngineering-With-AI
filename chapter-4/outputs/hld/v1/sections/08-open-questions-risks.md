## 8. Open Questions & Risks

### Open Questions

| # | Question | Assigned To | Due Date | Status |
|---|----------|-------------|----------|--------|
| 1 | How will fuzzy name matching be implemented for patient search (Soundex, Levenshtein, other)? | Michael Torres (CIO) | 2026-02-28 | Open [DRD §6.2 #1] |
| 2 | Which cloud platform for production deployment (Databricks, EMR, Dataproc)? | Michael Torres (CIO) | 2026-06-01 | Open |
| 3 | What are the production RTO/RPO targets? Phase 1 uses 4h/24h; production targets require compliance review. | Jennifer Martinez (Compliance) | 2026-04-30 | Open [DRD §7.6] |
| 4 | Should schema evolution use `mergeSchema = true` or versioned schemas? | Data Engineering Team | 2026-04-15 | Open |
| 5 | Column-level lineage strategy for production (DataHub vs. Databricks UC)? UC OSS 0.4.0 has no column-level lineage API. | Data Engineering Team | 2026-06-01 | Open |
| 6 | Grafana proficiency assessment -- team capability for dashboard creation and alerting is unverified. | Data Engineering Team | 2026-04-15 | Open |
| 7 | What is the retention policy for deceased patient records? | Compliance Team | 2026-02-28 | Open [DRD §6.2 #4] |

### Key Risks

| Risk | Impact | Likelihood | Mitigation |
|------|--------|-----------|------------|
| Observations table (4.37M rows) hourly full snapshot exceeds local Spark memory or SLA | Pipeline failures, data freshness SLA breach | Low -- well within 4 GB driver memory [infrastructure-constraints.md §1] | Monitor runtime via Grafana; scale to cluster mode at 10x volume; increase shuffle partitions if runtime exceeds 30 min |
| HIPAA audit requirements not fully met in Phase 1 | Compliance gap if production traffic routed through Phase 1 | Medium -- Phase 1 is dev-only | Phase 2 adds encryption at rest, full audit logging, SSO + MFA [DRD §7.4]; Phase 1 restricted to development use |
| Team unfamiliar with UC OSS 0.4.0 | Slower development, misconfiguration of catalog | Medium | Allocate upskilling time; use `spark_catalog` default to reduce configuration complexity [infrastructure-constraints.md §5] |
| Source database adds columns without notice | Bronze schema enforcement failures | Low | Use `mergeSchema` option in Bronze reads; enforce strict schema-on-write in Silver; alert on schema drift |
| Grafana not in approved technology catalog | Potential rejection during architecture review | Medium | Submit catalog update request; if rejected, fall back to Marquez + Spark Expectations only |
| Full Snapshot CDC becomes unsustainable at 10x scale | Pipeline runtime exceeds 1 hour; hourly SLA missed | Low (3+ years at 5-10% growth) | Re-evaluation trigger at 50M rows or 1-hour runtime; evaluate Timestamp Watermark CDC when source provides audit columns |

---
