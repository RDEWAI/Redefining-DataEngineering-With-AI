## 7. Decision Log

### Decision 1: Architecture Pattern -- Medallion vs. Lambda/Kappa/Data Vault

**Options Considered**:
1. Medallion (Bronze/Silver/Gold) -- batch pipeline, team high proficiency
2. Lambda Architecture -- dual batch + streaming paths
3. Kappa Architecture -- streaming-only with reprocessing
4. Data Vault -- hub-satellite with surrogate keys for audit trails

**Selected**: Medallion (Bronze/Silver/Gold)

**Rationale**: DRD [§4.4] requires 1-hour maximum latency for clinical users and 24-hour for others -- no sub-minute requirement. Team has demonstrated high proficiency in Medallion + Delta Lake [team-capabilities.md §2]. Infrastructure is local Docker with no Kafka/Flink [technology-catalog.md]. User confirmed this selection.

**Trade-off**: Cannot achieve sub-minute data freshness for medications/allergies [DRD §2.2]. Hourly batch is the Phase 1 compromise. Sub-minute CDC deferred to Phase 2 with streaming infrastructure.

### Decision 2: CDC Method -- Hourly Full Snapshot for All Tables

**Options Considered**:
1. Micro-batch (1-5 minute polling with timestamp-based CDC)
2. Spark Structured Streaming (trigger-once or continuous)
3. Hourly Full Snapshot for all tables uniformly

**Selected**: Hourly Full Snapshot for all tables

**Rationale**: Source database has no `updated_at` or `modified_at` columns (verified via database query on 2026-03-16), making timestamp-based CDC unreliable. Team is Not Experienced in Streaming [team-capabilities.md §2]. Hourly cadence satisfies the 1-hour clinical latency SLA [DRD §4.4].

**Trade-off**: Full Snapshot scans entire source tables each run. For observations (4.37M rows), this adds processing time per run. Acceptable at current scale. Evaluate incremental CDC in Phase 2 when source systems provide audit timestamps.

### Decision 3: SCD Strategy -- Type 2 with Versioned Rows

**Options Considered**:
1. SCD Type 1 -- overwrite with latest value, no history
2. SCD Type 2 -- versioned rows with effective dates
3. Full snapshot -- daily full reload, simplest approach

**Selected**: SCD Type 2 with versioned rows and effective dates

**Rationale**: Team is Proficient with Delta MERGE INTO for SCD2 [team-capabilities.md §2]. Patient demographics change over time and clinical accuracy requires historical tracking [DRD §1.2]. SHA-256 hash comparison detects changes efficiently on small dimension tables (max 5,767 rows for patients).

**Trade-off**: SCD Type 2 increases Silver storage due to historical versions and adds MERGE INTO complexity. Acceptable because dimension tables are small and the team has proven proficiency.

### Decision 4: Storage Format -- Delta Lake

**Options Considered**:
1. Delta Lake -- ACID, time travel, MERGE INTO, team high proficiency
2. Apache Iceberg -- multi-engine portability, no team experience
3. Apache Hudi -- upsert-optimized, no team experience

**Selected**: Delta Lake

**Rationale**: Infrastructure constraints mandate Delta Lake exclusively [infrastructure-constraints.md §2]. Team has high proficiency in Delta MERGE INTO for SCD2 [team-capabilities.md §2]. No alternatives permitted by infrastructure policy.

**Trade-off**: Vendor lock-in to Databricks ecosystem. Acceptable for local dev; Iceberg migration path exists if multi-engine portability needed in production.

### Decision 5: Gold Table Design -- 3 Consumer-Aligned Tables

**Options Considered**:
1. Three consumer-aligned tables (patient_summary, patient_clinical_history, patient_billing_summary)
2. One wide denormalized patient_360 table for all consumers
3. Per-consumer tables (5+ tables, one per role group)

**Selected**: Three consumer-aligned tables

**Rationale**: DRD [§4.1] identifies three distinct consumer access patterns with different data needs. DRD [§5.5] requires cost data hidden from non-billing roles -- separate tables enforce this at the schema level.

**Trade-off**: Three Gold tables require three separate pipeline jobs instead of one. Acceptable because Gold tables are small (base of 5,767 patient rows).

### Decision 6: Monitoring -- Spark Expectations + Marquez + Grafana

**Options Considered**:
1. Spark Expectations + Marquez only (tools already in catalog)
2. Spark Expectations + Marquez + Grafana (adds pipeline metrics dashboards)
3. Minimal application logging only

**Selected**: Spark Expectations + Marquez + Grafana

**Rationale**: Spark Expectations provides DQ enforcement [technology-catalog.md §5]. Marquez provides lineage tracking for HIPAA audit support [DRD §7.5]. Grafana adds operational visibility with runtime dashboards, throughput metrics, and alerting.

**Trade-off**: Grafana is not currently in the approved technology catalog and team proficiency is unverified. Requires catalog update and team evaluation.

### Decision 7: Recovery Targets -- Relaxed DR (RTO 4h / RPO 24h)

**Options Considered**:
1. Relaxed DR: RTO 4 hours / RPO 24 hours
2. Standard DR: RTO 1 hour / RPO 1 hour
3. Defer entirely to Phase 2

**Selected**: Relaxed DR (RTO 4 hours / RPO 24 hours)

**Rationale**: System is read-only [DRD §1.5] and rebuildable from the authoritative source EHR at any time. DRD [§7.6] notes DR requirements are TBD for Phase 1.

**Trade-off**: 4-hour RTO means clinical users could lose access for up to 4 hours during an outage. Acceptable because source EHR systems remain available for direct lookup during outages.

---
