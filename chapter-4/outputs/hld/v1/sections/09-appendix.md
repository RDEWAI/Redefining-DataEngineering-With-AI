## 9. Appendix

### Version History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-03-16 | Architect Agent | Initial HLD: Medallion pattern; hourly Full Snapshot CDC; SCD Type 2 on dimensions; 3 consumer-aligned Gold tables; Spark Expectations + Marquez + Grafana; relaxed DR (4h RTO / 24h RPO) |
| 1.1 | 2026-03-17 | Architect Agent | Restructured to 9-section template: added explicit FR/NFR traceability (SS2), consolidated Governance (SS6), added Data Domain diagram (SS4.4), split Integration Architecture from Data Architecture |
| 1.2 | 2026-03-23 | Architect Agent | Added config-driven Bronze ingestion (per-table YAML, extended content, dual validation gate); adopted Spark Declarative Pipelines (SDP) for all layers; added Airflow as cross-pipeline orchestrator; dual DQ strategy (SDP expectations + SE); updated all diagrams and decision log (Decisions 8-10) |

### Approval

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Technical Sponsor | Michael Torres | _Pending_ | __________ |
| Business Sponsor | Dr. Sarah Chen | _Pending_ | __________ |
| Compliance/Privacy | Jennifer Martinez | _Pending_ | __________ |
| Clinical Operations | Lisa Park | _Pending_ | __________ |

### Related Documents

- **DRD**: DRD-2026-02-11-patient-360.md (v1.1) -- source requirements
- **DMS**: Data Model Specification (downstream -- defines table schemas, column details, and write strategies)
- **DQS**: Data Quality Specification (downstream -- defines DQ rules; generates per-table SE YAML rule files)
- **LLD**: Low-Level Design (downstream -- defines deployment configs, technology versions, JAR coordinates, Airflow DAGs, SDP pipeline specs, config file schemas, and operational runbooks)
