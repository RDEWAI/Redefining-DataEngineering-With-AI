---
Version: 1.0
Status: Approved
Topic: Unity Catalog OSS — server, UCSingleCatalog, bootstrap
---

# Unity Catalog Pattern

## Purpose

Use Unity Catalog OSS as the metastore so every table has a three-part
name (`catalog.schema.table`), ACLs can be declared even in local dev,
and the same metadata layer carries forward to managed UC on
Databricks/Azure/AWS. No hive-metastore, no direct-path reads.

## Pattern

- **One UC server per workspace** — `docker compose up -d server` runs
  `unitycatalog/unitycatalog:v0.5.0` (built from source and pushed to our
  own registry — no released server image) on port `8080`.
- **`UCSingleCatalog` as the Spark catalog** — configure
  `spark.sql.catalog.spark_catalog` to
  `io.unitycatalog.spark.UCSingleCatalog` and point it at
  `http://localhost:8080`. All `spark.table("...")` lookups resolve via
  UC.
- **Catalog = project, schemas = layers** — one UC catalog per project
  (`{project}`), three schemas (`bronze`, `silver`, `gold`) under it.
- **Bootstrap script** — `scripts/uc_init.py` creates the catalog and
  schemas on first start (idempotent; `CREATE CATALOG IF NOT EXISTS`).
- **No DROP TABLE in application code** — UC preserves table metadata
  across Delta operations; use `MERGE`, `replaceWhere`, or
  `DROP TABLE` in a one-off script if truly needed.

## Key APIs

- Unity Catalog 0.5.0 REST API (`/api/2.1/unity-catalog/...`).
- `io.unitycatalog:unitycatalog-spark_4.1_2.13:0.5.0` jar (Maven
  coordinate — the 0.5.0 connector name carries a `_4.1` Spark-version
  infix; see `LIBRARIES.md`).
- Spark config: `spark.sql.catalog.spark_catalog`,
  `spark.sql.catalog.spark_catalog.uri`.

## Illustrative snippet

```python
# scripts/uc_init.py
import requests
UC_URL = "http://localhost:8080/api/2.1/unity-catalog"
CATALOG = "{project}"
SCHEMAS = ["bronze", "silver", "gold"]

def ensure(path, body):
    r = requests.post(f"{UC_URL}/{path}", json=body)
    if r.status_code == 409:   # already exists
        return
    r.raise_for_status()

ensure("catalogs", {"name": CATALOG, "comment": "{project} medallion"})
for s in SCHEMAS:
    ensure("schemas", {"catalog_name": CATALOG, "name": s})
```

```python
# run_local.py — Spark session with UC
spark = (SparkSession.builder
    .config("spark.sql.catalog.spark_catalog",
            "io.unitycatalog.spark.UCSingleCatalog")
    .config("spark.sql.catalog.spark_catalog.uri",
            "http://localhost:8080")
    .config("spark.sql.defaultCatalog", "spark_catalog")
    .config("spark.sql.extensions",
            "io.delta.sql.DeltaSparkSessionExtension")
    .getOrCreate())
```

## Common pitfalls

- Pointing Spark at UC but leaving Hive metastore extensions active —
  two catalogs fight; use `UCSingleCatalog` exclusively.
- Skipping `uc_init.py` — the first `spark.sql("CREATE SCHEMA bronze")`
  succeeds in Spark but the schema never appears in UC's metastore,
  breaking UI reads and downstream ACLs.
- Hard-coding `http://localhost:8080` in library code — make it a
  config value (`UC_URL` env var); SDP / Airflow override it in
  non-local environments.
- Using two-part names (`bronze.patients`) when UC is the default
  catalog — works locally but breaks the moment you add a second
  catalog. Always use three-part names
  (`spark_catalog.bronze.{table}`) or rely on
  `spark.sql.defaultCatalog` consistently.

## References

- `/mvp/scripts/uc_init.py`
- `/mvp/run_local.py` (Spark session config)
- `/mvp/README.md` (UC setup section)
- [`docker-compose-conventions.md`](docker-compose-conventions.md)
- [`LIBRARIES.md`](LIBRARIES.md) (UC server + jar versions)
- UC OSS docs: https://docs.unitycatalog.io/
