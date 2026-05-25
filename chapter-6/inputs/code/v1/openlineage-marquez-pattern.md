---
Version: 1.0
Status: Approved
Topic: OpenLineage Spark listener + Marquez backend for lineage capture
---

# OpenLineage & Marquez Pattern

## Purpose

Every Spark job emits **OpenLineage** events (job start/complete,
input/output datasets, column-level lineage where supported). Marquez
stores the events and serves a lineage UI. Enabling is config-only —
no application code changes — and failure to reach Marquez never fails
a Spark job.

## Pattern

- **Spark listener via `spark.jars.packages`** — pulls the
  `io.openlineage:openlineage-spark` jar at session creation. No manual
  jar copying.
- **Extra Spark listener** — `spark.extraListeners =
  io.openlineage.spark.agent.OpenLineageSparkListener`.
- **Transport to Marquez** —
  `spark.openlineage.transport.type = http`,
  `spark.openlineage.transport.url = http://localhost:5001` (macOS
  AirPlay squats on `5000`; container-internal is still `5000`, host
  maps to `5001`).
- **Namespace** — `spark.openlineage.namespace = {project}` so each
  project's lineage is isolated in Marquez's UI.
- **Soft-fail** — `spark.openlineage.facets.disabled = [...]` and
  transport timeouts prevent Marquez downtime from cascading into
  Spark failures. Lineage is observability, not critical-path.
- **Column-level lineage** enabled by default in OpenLineage ≥1.30;
  confirm via Marquez UI → dataset → "Column Lineage" tab.

## Key APIs

- OpenLineage Spark listener 1.46.0 (see `LIBRARIES.md`).
- Marquez REST API — `POST /api/v1/lineage`.
- Marquez web UI — `http://localhost:3000/`.

## Illustrative snippet

```python
# run_local.py — add to SparkSession.builder config
OPENLINEAGE_PACKAGES = "io.openlineage:openlineage-spark_2.13:1.46.0"

spark = (SparkSession.builder
    .config("spark.jars.packages",
            f"{DELTA_PACKAGES},{UC_PACKAGES},{OPENLINEAGE_PACKAGES}")
    .config("spark.extraListeners",
            "io.openlineage.spark.agent.OpenLineageSparkListener")
    .config("spark.openlineage.transport.type", "http")
    .config("spark.openlineage.transport.url", "http://localhost:5001")
    .config("spark.openlineage.namespace", "{project}")
    .getOrCreate())
```

```yaml
# docker-compose.yml — Marquez block (excerpt; see docker-compose-conventions.md)
marquez:
  image: marquezproject/marquez:0.51.1
  ports: ["5001:5000"]
  depends_on: {marquez-db: {condition: service_healthy}}

marquez-web:
  image: marquezproject/marquez-web:0.51.1
  ports: ["3000:3000"]
```

## Common pitfalls

- Mixing Scala 2.12 and 2.13 artifacts — PySpark 4.x is Scala 2.13
  only. Use `openlineage-spark_2.13`, not the 2.12 jar.
- Leaving `spark.openlineage.transport.url = http://localhost:5000` —
  macOS AirPlay Receiver hijacks `5000`; use `5001` (host) /
  `5000` (inside docker network).
- Treating lineage as a hard dependency — if Marquez is down, Spark
  jobs should still run. Set short transport timeouts.
- Mixing projects under one namespace — Marquez UI becomes unreadable.
  One namespace per project.
- Forgetting to start `marquez-web` — the REST API at `5001` works but
  the UI at `3000` is 404.

## References

- `/mvp/run_local.py` (Spark config with listener)
- `/mvp/docker-compose.yml` (Marquez + marquez-web + Postgres)
- [`docker-compose-conventions.md`](docker-compose-conventions.md)
- [`LIBRARIES.md`](LIBRARIES.md) (OpenLineage + Marquez versions)
- OpenLineage Spark integration: https://openlineage.io/docs/integrations/spark/
- Marquez docs: https://marquezproject.github.io/marquez/
