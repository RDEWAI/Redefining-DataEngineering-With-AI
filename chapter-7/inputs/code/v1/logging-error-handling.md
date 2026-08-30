---
Version: 1.0
Status: Approved
Topic: Structured logging and fail-fast error handling
---

# Logging & Error Handling

## Purpose

Predictable logs for operators (single format, severity-graded) and
fail-fast exceptions for the orchestrator. No silent failures, no
swallowed exceptions, no `print()`.

## Pattern

- **Module-level logger** — `logger = logging.getLogger(__name__)` at the
  top of every module. Never construct loggers per-call.
- **`logging.basicConfig` in entry-points only** — `run_local.py`,
  `pipelines/*.py`, Airflow task functions. Library modules (`src/`)
  never call `basicConfig`; they inherit the root config.
- **Standard format** —
  `%(asctime)s %(levelname)s [%(name)s] %(message)s` at `INFO` level by
  default; `DEBUG` opt-in via env var.
- **Structured args, not f-strings** — `logger.info("Ingested %s rows
  into %s (ds=%s)", count, table, ds)`. Lets log aggregators pull out
  fields; also cheaper when DEBUG is off.
- **Fail fast at boundaries** — check inputs (file existence, schema
  registry lookup, required env vars) **before** doing work. Raise
  domain-specific exceptions (`FileNotFoundError`, `KeyError`,
  `ValueError`) with a message that names the missing thing.
- **Don't catch-and-log-and-reraise in library code** — let the exception
  propagate to the entry-point, which logs once and exits non-zero. The
  orchestrator (Makefile target, Airflow operator, SDP runtime) handles
  retry.
- **Log row counts after every write** — gives operators an audit trail
  without opening a notebook.

## Illustrative snippet

```python
import logging

logger = logging.getLogger(__name__)

def ingest(spark, table, schema, csv_file, ds, raw_path, database="bronze"):
    csv_path = raw_path / csv_file
    if not csv_path.exists():
        raise FileNotFoundError(f"Source file not found: {csv_path}")

    logger.info("Ingesting %s from %s (ds=%s)", table, csv_path, ds)

    df = (spark.read.format("csv").option("header", "true")
          .schema(schema).load(str(csv_path))
          .withColumn("ds", F.lit(ds))
          .withColumn("ingested_at", F.current_timestamp()))

    save_as_delta_table(spark, df, f"{database}.{table}",
                        mode="overwrite", partition_by=["ds"],
                        replace_where=f"ds = '{ds}'")
    count = df.count()
    logger.info("Wrote %d rows to %s.%s (ds=%s)", count, database, table, ds)
    return df
```

Entry-point (`run_local.py`):

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)

try:
    run(spark, layer=args.layer, ds=args.ds)
except Exception:
    logger.exception("Pipeline failed for layer=%s ds=%s", args.layer, args.ds)
    raise
```

## Common pitfalls

- Using f-strings for `logger.info(...)` — evaluated even when DEBUG is
  off; also stops log aggregators from indexing fields.
- Calling `logging.basicConfig` in a `src/` module — fights with the
  entry-point config; last caller wins.
- Swallowing exceptions in library code (`except Exception: pass`) — the
  orchestrator now thinks the job succeeded.
- Logging PII — strip or mask before emit; see `{column}_masked`
  convention in [`naming-conventions.md`](naming-conventions.md).

## References

- `/mvp/src/patient_360/bronze/ingest.py` (module logger + fail-fast)
- `/mvp/run_local.py` (`basicConfig` + top-level try/except)
- `/mvp/src/patient_360/utils/` (shared helpers, no module-level config)
