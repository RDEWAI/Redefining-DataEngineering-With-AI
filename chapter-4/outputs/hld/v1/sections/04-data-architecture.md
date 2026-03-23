## 4. Data Architecture

### 4.1 Selected Pattern

**Pattern**: Medallion Architecture (Bronze, Silver, Gold) with Spark Declarative Pipelines (SDP)

**Justification**: The DRD [SS4.4] requires a maximum of 1-hour latency for clinical users and 24-hour latency for billing/reporting consumers. The team has demonstrated high proficiency in Medallion patterns, Delta Lake MERGE INTO, and SCD Type 2 [team-capabilities.md SS2] -- making Medallion the lowest-risk, highest-velocity choice. The 5,767-patient dataset with 13.5M total rows [DRD SS2.3, verified against source database] is well within local-mode Spark capacity and does not justify a streaming architecture. The team is Not Experienced in Streaming [team-capabilities.md SS2], ruling out Lambda and Kappa patterns without an upskilling investment. Spark Declarative Pipelines (built into Spark 4.1+ [technology-catalog.md SS1]) provide declarative dependency resolution, incremental processing, and built-in DQ expectations within each pipeline, while the team is Familiar with SDP [team-capabilities.md SS2] -- a manageable ramp-up from their Proficient Spark baseline.

### 4.2 Alternatives Considered

| Option | Description | Why Not Selected |
|--------|-------------|------------------|
| Medallion (Bronze/Silver/Gold) with SDP | 3-layer batch pipeline with Delta Lake, SDP for intra-pipeline orchestration | **Selected** -- team proficient in Medallion, Familiar with SDP, satisfies all DRD SLAs |
| Lambda Architecture | Dual batch + streaming paths for mixed latency | Over-engineered: DRD requires only 1-hour latency [SS4.4], not sub-minute; team has no streaming experience [team-capabilities.md SS2] |
| Kappa Architecture | Streaming-only with Kafka/Flink reprocessing | Requires Kafka/Flink infrastructure not in technology catalog; team gap in streaming |
| Data Vault | Hub-satellite modeling with surrogate keys | Team has no practical experience; longer development timeline; no audit-trail requirement in DRD that mandates Data Vault's overhead |

**Trade-off**: Medallion batch cannot achieve sub-minute data freshness. The DRD [SS2.2] notes sub-minute source sync for medications and allergies, but the physician latency SLA [SS4.4] accepts 1-hour maximum. Hourly batch for all tables is the Phase 1 compromise accepted by the user.

### 4.3 Layer Strategy

**Bronze Layer -- Config-Driven Ingestion via SDP `@dp.table` (Streaming Tables)**

Preserves source data exactly as received from the Synthea EHR. No business transformations -- only type casting, schema enforcement, and partition tagging with load metadata (`_ingested_at`, `_batch_id`, `_source_file`). Serves as the immutable audit record. All 13 Phase 1 tables land here with idempotent partition replacement per `ds` date [DRD SS2.2].

Bronze ingestion is **config-driven**: a generic ingestion engine reads per-table YAML config files (13 files for Phase 1) and dynamically generates SDP `@dp.table` definitions (streaming tables). Each config file specifies: table name, source path/connection, schema reference, CDC method, ingestion frequency, partition column, write mode, DQ rule reference, load priority/ordering, SCD type, hash columns, derived field definitions, and target layer mapping. Adding a new source table requires only a new YAML config file -- no pipeline code changes.

**Silver Layer -- Code-Driven Transformations via SDP `@dp.table`**

Applies business logic and data conformance using SDP `@dp.table` decorators. SDP manages dependency resolution between Silver tables automatically -- if `silver_encounters` depends on `silver_patients`, SDP resolves and parallelizes this. SCD Type 2 applied to dimension tables (patients, providers, payers, organizations) for historical tracking using SHA-256 change detection and Delta MERGE INTO [team-capabilities.md SS2]. Fact tables use insert-only pattern with partition overwrite. Derived fields computed here: `calculated_age`, `medication_status`, `is_30_day_readmission`, `total_visit_cost` [DRD SS5.2].

**Gold Layer -- Consumer-Specific Materialized Views via SDP `@dp.materialized_view`**

Produces three denormalized, consumer-specific tables using SDP `@dp.materialized_view` decorators. SDP handles incremental refresh -- only recomputing Gold outputs when upstream Silver tables change:

1. **patient_summary** -- Clinical users: demographics, active conditions, active medications, allergies (never suppressed), recent encounters. Serves the 2-second search SLA [DRD SS4.3].
2. **patient_clinical_history** -- Physicians and nurses: full encounter history, observations, procedures, immunizations, careplans. Pre-appointment review use case [DRD SS4.2].
3. **patient_billing_summary** -- Billing staff only: encounter costs, claims, total_visit_cost. Cost fields hidden from non-billing roles [DRD SS5.5].

> Detailed table inventories, column schemas, and per-table write strategies are documented in the **Data Model Specification (DMS)**.

### 4.4 Data Domain Map

**Clinical domain** (patients, encounters, conditions, medications, observations, allergies, immunizations, procedures, careplans) flows through all three layers. Core domain serving the Patient 360 search use case [DRD SS1.1].

**Reference domain** (organizations, providers, payers) lands in Bronze and becomes SCD Type 2 dimensions in Silver. Slowly changing reference tables (1,080 orgs, 1,080 providers, 10 payers) supporting FK relationships [DRD SS3.3].

**Financial domain** (claims) flows Bronze to Silver to Gold billing summary. Restricted to billing staff role [DRD SS5.5]. Cost fields hidden from clinical views.

```mermaid
flowchart LR
    subgraph Clinical["Clinical Domain"]
        C1[patients] & C2[encounters] & C3[conditions]
        C4[medications] & C5[observations] & C6[allergies]
        C7[immunizations] & C8[procedures] & C9[careplans]
    end

    subgraph Reference["Reference Domain\nSCD Type 2 dimensions"]
        R1[organizations] & R2[providers] & R3[payers]
    end

    subgraph Financial["Financial Domain\nbilling role only"]
        F1[claims]
    end

    Clinical -->|"core patient data"| GC["patient_summary\npatient_clinical_history"]
    Reference -->|"FK dimensions"| GC
    Financial -->|"cost & claims data"| GF["patient_billing_summary"]
    Reference -->|"FK dimensions"| GF
```

### 4.5 SCD Strategy

| Dimension Type | SCD Approach | Rationale |
|----------------|-------------|-----------|
| Patient demographics (5,767 rows) | SCD Type 2 | Track address, name, and insurance changes for clinical accuracy [DRD SS1.2]; team proficient with Delta MERGE INTO [team-capabilities.md SS2]; SCD type specified in per-table YAML config |
| Provider attributes (1,080 rows) | SCD Type 2 | Track specialty and organization changes for referential accuracy |
| Payer information (10 rows) | SCD Type 2 | Track plan and coverage changes for billing accuracy |
| Organization data (1,080 rows) | SCD Type 2 | Track organizational restructuring for reporting |
| Fact tables (encounters, conditions, etc.) | Insert-only with partition overwrite | Immutable event records; no history tracking needed -- partition by `ds` for idempotent reruns [infrastructure-constraints.md SS2] |

### 4.6 Pipeline Architecture Diagram

```mermaid
flowchart TB
    subgraph Sources["Source Systems"]
        EHR["Synthea Healthcare EHR\n13 source tables"]
    end

    subgraph Orchestration["Orchestration Layer"]
        AF["Apache Airflow\nCross-pipeline scheduling\nBronze->Silver->Gold dependency"]
        CFG["Per-Table YAML Configs\n13 config files"]
    end

    subgraph Platform["Data Platform -- Spark Declarative Pipelines"]
        subgraph Bronze["Bronze Layer -- SDP @dp.table streaming tables"]
            B["Config-driven generic ingestion\nSchema enforcement\nPartition tagging ds\nNo transformations"]
        end

        DQ1{{"DQ Gate 1\nSDP @dp.expect* inline checks\n+ SE YAML rules for complex checks"}}

        subgraph Silver["Silver Layer -- SDP @dp.table"]
            S["SCD Type 2 dimensions\nFact normalization\nDerived fields\nReferential integrity"]
        end

        DQ2{{"DQ Gate 2\nFK checks, business rules\nSpark Expectations YAML"}}

        subgraph Gold["Gold Layer -- SDP @dp.materialized_view"]
            G["Denormalized consumer tables\nIncremental refresh\nRole-based access\nSLA-optimized queries"]
        end

        META["Unity Catalog OSS\nCatalog and Schema Registry"]
        LIN["OpenLineage / Marquez\nLineage Tracking"]
        MON["Grafana\nPipeline Metrics"]
    end

    subgraph Consumers["Consumer Groups"]
        Clinical["Clinical Users 350\n< 2s p90, hourly refresh"]
        Billing["Billing Staff 50\n< 2s p90, daily refresh"]
        DeptHeads["Department Heads 15\nAggregates only"]
    end

    AF -->|"spark-pipelines run\n--spec bronze.yaml"| Bronze
    AF -->|"spark-pipelines run\n--spec silver.yaml"| Silver
    AF -->|"spark-pipelines run\n--spec gold.yaml"| Gold
    CFG -->|"Drive ingestion"| Bronze
    EHR -->|"Full Snapshot CDC\nHourly batch"| Bronze
    Bronze --> DQ1 --> Silver
    Silver --> DQ2 --> Gold
    Gold --> Clinical & Billing & DeptHeads
    Bronze & Silver & Gold -.-> LIN
    META -.->|"Catalog Registration"| Bronze & Silver & Gold
    Bronze & Silver & Gold -.->|"Job metrics"| MON
```

---
