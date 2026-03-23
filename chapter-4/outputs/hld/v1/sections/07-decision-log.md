## 7. Decision Log

### Decision 1: Architecture Pattern -- Medallion vs. Lambda/Kappa/Data Vault

**Options Considered**:
1. Medallion (Bronze/Silver/Gold) -- batch pipeline, team high proficiency
2. Lambda Architecture -- dual batch + streaming paths
3. Kappa Architecture -- streaming-only with reprocessing
4. Data Vault -- hub-satellite with surrogate keys for audit trails

**Selected**: Medallion (Bronze/Silver/Gold)

**Rationale**: DRD [SS4.4] requires 1-hour maximum latency for clinical users and 24-hour for others -- no sub-minute requirement. Team has demonstrated high proficiency in Medallion + Delta Lake [team-capabilities.md SS2]. Infrastructure is local Docker with no Kafka/Flink [technology-catalog.md]. User confirmed this selection.

**Trade-off**: Cannot achieve sub-minute data freshness for medications/allergies [DRD SS2.2]. Hourly batch is the Phase 1 compromise. Sub-minute CDC deferred to Phase 2 with streaming infrastructure.

### Decision 2: CDC Method -- Hourly Full Snapshot for All Tables

**Options Considered**:
1. Micro-batch with timestamp-based CDC
2. Spark Structured Streaming
3. Hourly Full Snapshot for all tables uniformly

**Selected**: Hourly Full Snapshot for all tables

**Rationale**: Source database has no `updated_at` or `modified_at` columns (verified 2026-03-16), making timestamp-based CDC unreliable. Team is Not Experienced in Streaming [team-capabilities.md SS2]. Hourly cadence satisfies the 1-hour clinical latency SLA [DRD SS4.4].

**Trade-off**: Full Snapshot scans entire source tables each run. Acceptable at current scale; evaluate incremental CDC in Phase 2.

### Decision 3: SCD Strategy -- Type 2 with Versioned Rows

**Options Considered**:
1. SCD Type 1 -- overwrite, no history
2. SCD Type 2 -- versioned rows with effective dates
3. Full snapshot daily reload

**Selected**: SCD Type 2 with versioned rows and effective dates

**Rationale**: Team is Proficient with Delta MERGE INTO for SCD2 [team-capabilities.md SS2]. Patient demographics change over time; clinical accuracy requires historical tracking [DRD SS1.2].

**Trade-off**: Increases Silver storage and MERGE INTO complexity. Acceptable because dimension tables are small (max 5,767 rows for patients).

### Decision 4: Storage Format -- Delta Lake

**Options Considered**:
1. Delta Lake -- ACID, time travel, MERGE INTO
2. Apache Iceberg -- multi-engine portability
3. Apache Hudi -- upsert-optimized

**Selected**: Delta Lake

**Rationale**: Infrastructure constraints mandate Delta Lake exclusively [infrastructure-constraints.md SS2]. Team has high proficiency [team-capabilities.md SS2].

**Trade-off**: Vendor lock-in to Databricks ecosystem. Iceberg migration path exists if needed.

### Decision 5: Gold Table Design -- 3 Consumer-Aligned Tables

**Options Considered**:
1. Three consumer-aligned tables
2. One wide patient_360 table for all consumers
3. Per-consumer tables (5+ tables)

**Selected**: Three consumer-aligned tables

**Rationale**: DRD [SS4.1] identifies three distinct access patterns. DRD [SS5.5] requires cost data hidden from non-billing roles -- separate tables enforce this at schema level.

**Trade-off**: Three Gold jobs instead of one. Acceptable because Gold tables are small.

### Decision 6: Monitoring -- Spark Expectations + Marquez + Grafana

**Options Considered**:
1. Spark Expectations + Marquez only
2. Spark Expectations + Marquez + Grafana
3. Minimal application logging only

**Selected**: Spark Expectations + Marquez + Grafana

**Rationale**: Marquez provides lineage tracking for HIPAA audit support [DRD SS7.5]. Grafana adds operational visibility with runtime dashboards and alerting. User requested both DQ/lineage and pipeline metrics.

**Trade-off**: Grafana not in approved technology catalog; team proficiency unverified. Requires catalog update.

### Decision 7: Recovery Targets -- Relaxed DR (RTO 4h / RPO 24h)

**Options Considered**:
1. Relaxed DR: RTO 4 hours / RPO 24 hours
2. Standard DR: RTO 1 hour / RPO 1 hour
3. Defer entirely to Phase 2

**Selected**: Relaxed DR (RTO 4 hours / RPO 24 hours)

**Rationale**: System is read-only [DRD SS1.5] and rebuildable from the authoritative source EHR. DRD [SS7.6] notes DR requirements are TBD for Phase 1.

**Trade-off**: Clinical users could lose access for up to 4 hours during an outage. Acceptable because source EHR remains available for direct lookup.

### Decision 8: Config-Driven Bronze Ingestion

**Options Considered**:
1. Per-table Python code -- each source table has its own ingestion script
2. Config-driven with single config file -- one monolithic YAML with all 13 tables
3. Config-driven with per-table files -- one YAML per source table (13 files for Phase 1)

**Selected**: Config-driven with per-table YAML files (Extended content)

**Rationale**: Config-driven ingestion eliminates per-table boilerplate code and enables adding new source tables without code changes [FR-11]. Per-table files (vs. monolithic) provide clear ownership, independent reviewability in PRs, and selective deployment -- a change to one table's config does not risk affecting others. Extended config content (table name, source path, schema reference, CDC method, frequency, partition column, write mode, DQ rule reference, load priority, SCD type, hash columns, derived fields, target layer mapping) gives the generic ingestion engine everything it needs without requiring code changes for new tables. Config scope is Bronze only -- Silver/Gold transformations remain code-driven because they contain business logic not suitable for declarative config. DQ rules are already config-driven via SE YAML files generated from the DQS, so no DQ config duplication is needed in ingestion configs.

**Trade-off**: Config proliferation risk at scale (50+ tables). Mitigated by potential config registry or generation from metadata catalog at that scale. Extended config content increases the schema validation surface -- mitigated by JSON Schema static validation at pre-commit and runtime fail-fast validation [NFR-13].

### Decision 9: Spark Declarative Pipelines (SDP) Adoption

**Options Considered**:
1. Manual PySpark scripts with explicit orchestration -- current baseline approach
2. Spark Declarative Pipelines (SDP) -- built into Spark 4.1+, declarative dependency resolution
3. SQLMesh -- SQL-based transformation framework with incremental models

**Selected**: Spark Declarative Pipelines (SDP)

**Rationale**: SDP is built into Spark 4.1+ [technology-catalog.md SS1], requiring no additional infrastructure or licensing. The team is Familiar with SDP [team-capabilities.md SS2] -- a manageable step from their Proficient Spark baseline. SDP provides three key capabilities that manual PySpark lacks: (1) automatic dependency resolution between tables within a pipeline, (2) parallelism of independent tables without explicit threading code, and (3) incremental processing via `@dp.materialized_view` -- Gold tables recompute only when upstream Silver tables change. Airflow (team Proficient [team-capabilities.md SS3]) handles cross-pipeline scheduling; SDP handles intra-pipeline orchestration. This separation of concerns keeps each tool focused on what it does best.

**Trade-off**: SDP is a Spark 4.1 feature (evolved from Databricks Delta Live Tables); it is newer than traditional PySpark scripts and the team is Familiar, not Proficient. Requires upskilling allocation in sprint 1. The `@dp.materialized_view` incremental refresh behavior must be tested against the SCD2 MERGE INTO pattern to ensure compatibility. Acceptable because the team's existing Spark proficiency reduces ramp-up time.

### Decision 10: DQ Strategy -- SDP Expectations + Spark Expectations (Dual-Layer)

**Options Considered**:
1. Spark Expectations only -- all DQ through SE YAML rules (current baseline approach)
2. SDP `@dp.expect*` only -- migrate all DQ to SDP built-in decorators
3. Dual-layer: SDP `@dp.expect*` for inline checks + Spark Expectations for complex rules

**Selected**: Dual-layer (SDP inline + SE complex)

**Rationale**: SDP `@dp.expect*` decorators are natural for simple, row-level assertions (schema validation, not-null, valid ranges) because they execute inline within the pipeline definition with zero external dependency. Spark Expectations excels at complex, cross-table validations (FK checks via `query_dq`), aggregate threshold rules (`agg_dq`), and action-based handling (fail/drop/ignore) -- capabilities that SDP expectations do not natively provide. The DQS already generates per-table SE YAML rule files, so SE integration is already planned. Using both tools avoids migrating existing SE rules to SDP while gaining SDP's inline check benefits.

**Trade-off**: Two DQ frameworks increase cognitive load for the team. Mitigated by clear responsibility split: SDP for schema/null/range inline checks, SE for everything else. The boundary is well-defined and documented in SS6.3.

---
