## 1. Executive Summary

The Patient 360 pipeline consolidates 13 Synthea healthcare source tables (13.5M total rows verified, 636 MB raw) into a unified patient view serving 415+ clinical, billing, and administrative users across five role groups. The architecture uses a Medallion pattern (Bronze, Silver, Gold) with Delta Lake for ACID guarantees and SCD Type 2 tracking on patient dimensions. All tables use hourly batch ingestion via Full Snapshot CDC, satisfying the DRD's 1-hour clinical latency SLA [DRD §4.4] and 2-second query response target [DRD §4.3] while keeping implementation within the team's demonstrated proficiency in batch Spark pipelines and Delta Lake MERGE INTO [team-capabilities.md §2]. Pipeline observability combines Spark Expectations for data quality enforcement, OpenLineage/Marquez for lineage tracking, and Grafana for pipeline metrics dashboards.

---
