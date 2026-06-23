# Upgrade Notes: Unity Catalog OSS 0.5.0 / Spark 4.1

Status: completed and verified on the local stack.
Scope: the `patient_360` medallion pipeline (PySpark + Delta + Unity Catalog
OSS + Spark-Expectations + Airflow).

This document records why the upgrade was done, the exact version changes, the
issues encountered, what was tried, and how each was resolved. It is a factual
record, not a recommendation.

---

## 1. Why the upgrade was done

The trigger was a single, verifiable defect: **the Spark-Expectations (SE)
data-quality audit tables were not being written.**

SE is configured to write rejected rows into a per-table `<table>_error` table
(and run statistics into `<table>_stats`). On the pre-upgrade stack (Unity
Catalog OSS 0.4.0) these tables did not exist. The error table was disabled
(`se.enable.error.table=False`) and a path-based workaround was in place, so
there was no queryable record of which rows failed data quality.

For a healthcare pipeline this is a gap: rows are dropped by DQ rules, but the
evidence of what was dropped is not retained.

The investigation (Section 4.1) showed the underlying cause was a defect in the
UC 0.4.0 Spark connector, not a fundamental limitation. Unity Catalog 0.5.0
fixes that defect and additionally supports managed (`catalogManaged`) tables
with coordinated commits, which is what SE needs to create and own its audit
tables. That is the reason the version was raised rather than worked around
further.

### 1.1 What was not supported (or broken) in UC 0.4.0

To create the SE `_error` / `_stats` tables, SE needs to create a Delta table by
name through the catalog. Three things stood in the way on UC 0.4.0, each
confirmed by a direct probe (Section 4.1):

| Capability SE needs | UC 0.4.0 behaviour | Evidence |
|---|---|---|
| Create a **managed** table by name (`saveAsTable` overwrite) | Not supported — REPLACE TABLE AS SELECT is rejected | `UnsupportedOperationException: REPLACE TABLE AS SELECT (RTAS) is not supported` |
| A **managed storage location** for the table (coordinated commits) | Could not be configured — managed create fails its precondition | `FAILED_PRECONDITION: Neither catalog nor schema has managed location configured` |
| Correctly qualify a **single-part (bare) table name** | Connector crashes instead of qualifying an empty namespace | `ArrayIndexOutOfBoundsException ... UCSingleCatalog$.fullTableNameForApi(UCSingleCatalog.scala:346)` |

Because of these, the only thing that worked on 0.4.0 was writing the audit data
to a **filesystem path** outside the catalog (the path-based workaround), which
is why no `unity.<schema>.<table>_error` table existed.

### 1.2 What UC 0.5.0 provides

| Capability | UC 0.5.0 |
|---|---|
| Managed (`catalogManaged`) tables with coordinated commits | Supported (requires a schema `storage_root` managed location — Section 4.5) |
| Name qualification of fully-qualified `catalog.schema.table` names | Fixed — the `fullTableNameForApi` crash no longer occurs |
| Net effect | SE can create and own `unity.<schema>.<table>_error` / `_stats` as managed tables (`se.enable.error.table=True`) |

The business tables did **not** depend on any of this — they are EXTERNAL Delta
tables written with `insertInto`, which worked on 0.4.0 and was left unchanged
(Section 5). Only the managed audit tables required 0.5.0.

---

## 2. Version changes

| Component | From | To |
|---|---|---|
| PySpark / Spark | 4.0.2 (JVM 4.0.0) | **4.1.1** |
| delta-spark (PyPI + JAR) | 4.0.0 | **4.3.0** |
| Unity Catalog Spark connector (JAR) | `unitycatalog-spark_2.13:0.4.0` | **`unitycatalog-spark_4.1_2.13:0.5.0`** |
| Unity Catalog server image | `v0.4.0` (published image) | **`v0.5.0` (built from source)** |
| openlineage-spark | 1.46.0 | **1.50.0** |
| Airflow | 3.2.1 | 3.2.1 (unchanged) |
| spark-expectations | 2.10 | 2.10 (unchanged) |

The PySpark, delta-spark, and UC connector versions are locked together (see
Section 4.2). The connector coordinate carries a Spark-version infix (`_4.1`),
so it is published only against a specific Spark minor line.

---

## 3. Naming convention change (made as part of the upgrade)

All references to a table that the DQ engine touches were changed from bare
names to **fully-qualified three-part names**: `catalog.schema.table`
(`unity.<schema>.<table>`).

- In the DQ rule files this is the `dq_env.<ENV>.table_name` value.
- The same fully-qualified name is passed to SE's `with_expectations(...)`.
- SE derives the audit-table name by appending `_error` / `_stats` to that
  target, so the target must be well-formed.

This applies to the contract files, the DQ rule files, and the SE runner. The
fully-qualified name is identical across DEV / QA / PROD. This change is
required for correctness on the connector (see Section 4.1), not cosmetic.

---

## 4. Issues found, what was tried, and resolution

The error blocks below are verbatim from the actual runs (trimmed only with
`...` where long Java frames or JSON were elided). Line numbers in Scala/Java
frames are from the specific library versions in use at the time.

### 4.1 The SE error table was not being written (UC 0.4.0)

- **Symptom:** `unity.<schema>.<table>_error` did not exist after a run.
  `se.enable.error.table` was `False`; a path-based writer was used instead.
- **Existing explanation (incorrect):** a code comment attributed this to
  "RTAS/CTAS unsupported on Unity Catalog."
- **What was tried:** a minimal reproduction — creating one managed table via
  `saveAsTable` against a single-part (bare) table name — to read the actual
  failure rather than rely on the comment.
- **Actual cause:** the UC 0.4.0 connector raised
  `ArrayIndexOutOfBoundsException` in `UCSingleCatalog.fullTableNameForApi`.
  With an empty current database, a bare table name produced a zero-length
  namespace array, and the connector indexed `namespace[0]`. This is a
  name-qualification defect, not a refusal to create the table.
- **Resolution:** pass fully-qualified three-part names everywhere SE looks
  (Section 3), and upgrade to UC 0.5.0, which corrects the namespace handling
  and supports managed table creation. The error table was then re-enabled
  (`se.enable.error.table=True`).

**Captured errors.** The failure as seen by Spark-Expectations when it tried to
write the error table for `synthea_allergies`:

```
RESULT: FAILED SparkExpectationsMiscException
error occurred while processing spark expectations error occurred while
executing func_process error occurred while saving data into the final error
table error occurred while writing data in to the table -
synthea_allergies_error: Index 0 out of bounds for length 0

java.lang.ArrayIndexOutOfBoundsException: Index 0 out of bounds for length 0
	at io.unitycatalog.spark.UCSingleCatalog$.fullTableNameForApi(UCSingleCatalog.scala:346)
	at io.unitycatalog.spark.UCProxy.loadTable(UCSingleCatalog.scala:386)
```

The Python side wraps the same exception:

```
pyspark.errors.exceptions.captured.ArrayIndexOutOfBoundsException: Index 0 out of bounds for length 0
  ...
spark_expectations.core.exceptions.SparkExpectationsMiscException:
  error occurred while running expectations Index 0 out of bounds for length 0
```

**The controlled probe.** To separate the real cause from the existing
"RTAS unsupported" comment, three distinct create operations were run directly
against UC 0.4.0. They produced three *different* errors, which is why the
single "RTAS" comment was misleading:

```
# 1. Managed saveAsTable (no managed location on the schema):
=== MANAGED saveAsTable unity.bronze.uc_probe_managed: FAIL ===
  UnsupportedOperationException: REPLACE TABLE AS SELECT (RTAS) is not supported

# 2. CREATE TABLE ... AS SELECT (managed):
io.unitycatalog.client.ApiException: createStagingTable call failed with: 400 -
  {"error_code":"FAILED_PRECONDITION", ...,
   "message":"Neither catalog nor schema has managed location configured."}

# 3. The actual SE error-table write (bare name -> empty namespace):
java.lang.ArrayIndexOutOfBoundsException: Index 0 out of bounds for length 0
	at io.unitycatalog.spark.UCSingleCatalog$.fullTableNameForApi(UCSingleCatalog.scala:346)
```

Only the third error is the one that broke the SE error table. The first two
are separate limitations of managed-table creation on 0.4.0 (addressed by the
managed-location work in Section 4.5), not the cause of the missing audit
table.

### 4.2 PySpark 4.1.2 broke dependency resolution

- **What was tried:** PySpark 4.1.2 (the latest 4.1.x at the time).
- **Symptom:** `uv sync` / `uv lock` failed.
- **Cause:** `delta-spark==4.3.0` declares `requires_dist: pyspark<=4.1.1,
  >=4.0.1`. PySpark 4.1.2 is above that ceiling.
- **Resolution:** pin PySpark to **4.1.1**. The published `requires_dist`
  constraint of delta-spark should be read before choosing a PySpark pin.

**Captured fact.** The raw resolver output was not retained, but the controlling
constraint is on PyPI:

```
delta-spark==4.3.0  requires_dist: pyspark<=4.1.1,>=4.0.1
# pyproject.toml had pinned: pyspark[pipelines]==4.1.2   -> above the ceiling
# uv lock then resolved 148 packages once pinned to 4.1.1
```

### 4.3 The UC connector coordinate changed shape

- **Symptom:** using the old coordinate `unitycatalog-spark_2.13:0.4.0` with
  Spark 4.1 does not load the catalog plugin.
- **Cause:** the 0.5.0 connector coordinate is
  `unitycatalog-spark_4.1_2.13:0.5.0` — it adds a Spark-version infix (`_4.1`)
  to the artifact name. The connector is published per Spark minor line.
- **Resolution:** use the new coordinate in `spark.jars.packages`.

**Note on traces.** No separate verbatim trace was captured for this item in
isolation; the symptom is that the `unity` catalog plugin is not loaded. When a
session is misconfigured for the catalog, Spark reports it as
`QueryExecutionErrors$.catalogPluginClassNotFoundForCatalogError`
(`QueryExecutionErrors.scala:1887`). The fix was applied together with the
coordinate change, so a clean standalone reproduction was not recorded.

### 4.4 UC 0.5.0 server image had to be built from source, and the build was broken

- **Context:** Unity Catalog 0.5.0 did not have a published server image, so it
  was built from source.
- **Symptom:** the built image crashed on startup with
  `NoClassDefFoundError` (a Vert.x class).
- **Cause:** the upstream Dockerfile copied the build cache from `$HOME/.cache`,
  but the `sbt` build, running as root, cached its dependencies under
  `/root/.cache`. The runtime layer was missing those classes.
- **Resolution:** patch the Dockerfile to copy `/root/.cache` from the build
  stage and fix its permissions. The resulting image was then published to a
  container registry, and the compose file pulls it.

**Captured error.** The container exited (1) on startup:

```
container patient_360-uc exited (1)

Error: Unable to initialize main class io.unitycatalog.server.UnityCatalogServer
Caused by: java.lang.NoClassDefFoundError: io/vertx/core/Verticle
```

### 4.5 Managed audit tables require a schema storage location and coordinated commits

- **Context:** managed (`catalogManaged`) tables in UC 0.5.0 require: a schema
  with a managed storage location (`storage_root`); coordinated commits; and a
  `_delta_log` directory shared between the UC server and Spark.
- **Symptom:** schema creation failed a `FAILED_PRECONDITION` check.
- **Cause:** `uc_init.py` sent `storage_root` nested under `properties`. UC
  0.5.0 expects it as a **top-level** field in the create-schema request.
- **Resolution:** send `storage_root` as a top-level field. Configure the
  shared `_delta_log` volume between the UC server and Spark containers.

**Captured error.** Managed-table creation without a managed location returns:

```
io.unitycatalog.client.ApiException: createStagingTable call failed with: 400 -
  {"error_code":"FAILED_PRECONDITION",
   "details":[{"reason":"FAILED_PRECONDITION", ...}],
   "message":"Neither catalog nor schema has managed location configured."}
	at io.unitycatalog.client.api.TablesApi.getApiException(TablesApi.java:78)
```

This is the same precondition the schema `storage_root` (managed location)
satisfies. The same `FAILED_PRECONDITION` shape appeared when `uc_init.py` sent
`storage_root` nested under `properties` instead of at the top level.

---

## 5. What was intentionally not changed

- **Business tables stay EXTERNAL.** The bronze/silver/gold business tables
  (`unity.{bronze,silver,gold}.*`) remain EXTERNAL Delta tables written with
  `insertInto`. That path already worked and carried lower risk, so it was not
  changed.
- **Only the SE audit tables became managed.** The `_error` / `_stats` tables
  are the only managed (`catalogManaged`) tables, created by SE via
  `saveAsTable` against a fully-qualified name. This kept the change scoped to
  the part of the system that required it.

---

## 6. Verification

After the upgrade, on the local stack:

- The managed SE error table is written. A bronze run persisted **477,351**
  rejected observation rows into `unity.bronze.synthea_observations_error`.
  This table could not be created on UC 0.4.0.
- The full Bronze → reconciliation DAG ran end to end without the connector
  error.

The managed audit trail being writable is the concrete outcome that confirms
the upgrade achieved its purpose.

---

## 7. Operational requirements introduced by this upgrade

A deployment of this stack now requires:

1. A Unity Catalog **0.5.0** server image (built from source, with the
   Dockerfile cache fix in Section 4.4).
2. Schemas created with a top-level `storage_root` managed location
   (`uc_init.py`).
3. A `_delta_log` directory shared between the UC server and Spark (for
   coordinated commits on managed tables).
4. The Spark JAR set: delta-spark 4.3.0, `unitycatalog-spark_4.1_2.13:0.5.0`,
   openlineage-spark 1.50.0, on a Spark 4.1.1 runtime.
5. Fully-qualified `catalog.schema.table` names in all contracts and DQ rules.
