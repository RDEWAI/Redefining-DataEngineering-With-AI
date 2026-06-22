"""Bronze SparkSubmitOperator wrapper — LLD §2.3, §6.1, §13 Decision 9.

# created: 2026-05-11
# updated: 2026-06-19 — re-synced catalog wiring to the named UC side
#   catalog (LLD §13 Decision 12, re-adopted 2026-06-18). The wrapper no
#   longer injects Derby/Hive metastore conf; catalog wiring is owned by
#   the runner's build_spark_session. Packages now include the UC connector
#   + OpenLineage JARs per LIBRARIES.md.
# updated: 2026-06-20 — UC 0.5.0 / Spark 4.1 upgrade (LLD v1.20 §6.1 / §13
#   Decision 3 / LIBRARIES.md). DEFAULT_PACKAGES bumped to the Spark-4.1 line:
#   delta-spark_2.13 4.0.0→4.3.0, unitycatalog-spark 0.4.0→0.5.0 with the NEW
#   `_4.1` Spark-version infix (io.unitycatalog:unitycatalog-spark_4.1_2.13),
#   openlineage-spark_2.13 1.46.0→1.50.0. The UC 0.5.0 connector publishes
#   only against Spark 4.1, so pyspark/delta-spark/connector move together.

Pattern
-------
Thin factory around Airflow's :class:`SparkSubmitOperator` that builds one
task per Bronze table. The wrapper centralises three things so the
TaskGroup factory (`ingestion_factory.py`) stays declarative:

1. **Compute knobs** -- driver/executor memory, cores, executor count,
   shuffle partitions, broadcast threshold -- are read from the pipeline
   config (LLD §6.1, §6.3, §7) and never hardcoded.
2. **Entry point** -- the Spark job's Python module is the one named by
   ``ingestion.spark_submit_class`` in ``config-template.yaml`` (default
   ``patient_360.bronze.ingestion_runner``). The wrapper resolves the
   module to its file path on the worker via :func:`importlib.util.find_spec`
   so SparkSubmit always receives an absolute application file, not a
   dotted module name.
3. **Application args** -- the wrapper always passes ``--config-path
   <per-table yaml>`` and ``--ds {{ ds }}`` (Airflow templated) so the
   generic runner is config-driven (LLD §2.3 / Decision 9).

Catalog wiring is owned entirely by the runner's
:func:`patient_360.utils.delta_helpers.build_spark_session`, which binds the
builtin ``spark_catalog`` to ``DeltaCatalog`` and adds Unity Catalog OSS as a
**named side catalog** ``unity`` (``UCSingleCatalog`` with ``.uri`` / ``.token``
/ ``.warehouse``) plus ``spark.sql.defaultCatalog=unity`` (LLD §13 Decision 12,
re-adopted 2026-06-18). The wrapper does NOT pass catalog ``--conf`` flags —
the runner runs in-process under ``local[*]`` and sets the catalog config on
the same session, so injecting catalog conf here would conflict. The wrapper
only ships the parallelism knobs (shuffle partitions, broadcast threshold,
driver cores) and the Maven coordinates for the Delta + UC + OpenLineage JARs
so the connector classes are on the classpath before the session boots.

The wrapper does not own retry / timeout policy -- those come from LLD
§4.2 / §8.1 and are applied by the DAG owner via ``operator_kwargs``.
"""

from __future__ import annotations

import importlib.util
import logging
from collections.abc import Mapping
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# LLD §7 — default entry-point module if pipeline config omits it. Kept
# in sync with ``ingestion_spark_submit_class`` in
# ``outputs/lld/v*/config/config-template.yaml``.
DEFAULT_INGESTION_ENTRY = "patient_360.bronze.ingestion_runner"

# LLD §13 Decision 12 (re-adopted 2026-06-18) — Maven coordinates for the
# JARs that must be on the driver classpath before SparkSession boots. The
# runner's build_spark_session wires the catalog conf at runtime; here we
# only ensure the connector classes are downloadable:
#   * delta-spark_2.13     → DeltaCatalog (builtin spark_catalog)
#   * unitycatalog-spark   → UCSingleCatalog (named `unity` side catalog)
#   * openlineage-spark    → lineage listener (LLD §11)
# Coordinates pinned to inputs/code/v1/LIBRARIES.md (Scala 2.13 / Spark 4.1,
# UC 0.5.0). Do NOT downgrade or drop the UC connector — without it the runner
# raises ClassNotFoundException for io.unitycatalog.spark.UCSingleCatalog. NOTE
# the UC 0.5.0 artifact name carries a `_4.1` Spark-version infix
# (`unitycatalog-spark_4.1_2.13`), NOT the old `unitycatalog-spark_2.13`; the
# name couples the connector to pyspark/delta-spark 4.1. The OpenLineage
# listener keeps the plain `_2.13` suffix (no Spark infix).
DEFAULT_PACKAGES: tuple[str, ...] = (
    "io.delta:delta-spark_2.13:4.3.0",
    "io.unitycatalog:unitycatalog-spark_4.1_2.13:0.5.0",
    "io.openlineage:openlineage-spark_2.13:1.50.0",
)


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------
def _resolve_entry_module(pipeline_cfg: Mapping[str, Any]) -> str:
    """Pull ``ingestion.spark_submit_class`` from the pipeline config."""
    ingestion = pipeline_cfg.get("ingestion") or {}
    return ingestion.get("spark_submit_class") or DEFAULT_INGESTION_ENTRY


def _resolve_application_path(module_name: str) -> str:
    """Locate ``<module>.py`` on the worker via importlib.

    SparkSubmitOperator wants a file path, not a dotted module. Falling
    back to ``python -m`` would skip the Spark CLI argument plumbing
    Airflow uses, so resolve to an absolute file at task-build time.
    """
    spec = importlib.util.find_spec(module_name)
    if spec is None or spec.origin is None:
        raise ModuleNotFoundError(
            f"Cannot locate Spark entry-point module {module_name!r}. "
            "Confirm the patient_360 package is installed on the worker "
            "(LLD §2.3)."
        )
    return str(Path(spec.origin).resolve())


def _resolve_compute(pipeline_cfg: Mapping[str, Any]) -> dict[str, Any]:
    """Read LLD §6.1 / §6.3 knobs out of the pipeline config.

    The config schema is the flat ``compute_spark_*`` namespace emitted
    by the LLD's ``config-template.yaml``. We translate to Spark CLI flag
    names the SparkSubmitOperator understands.
    """
    compute = pipeline_cfg.get("compute") or {}
    spark_section = compute.get("spark") or compute  # accept both shapes

    def _get(key: str, default: Any) -> Any:
        # Support both nested (compute.spark.driver_memory) and the flat
        # ``compute_spark_*`` shape used in config-template.yaml.
        if key in spark_section:
            return spark_section[key]
        flat_key = f"compute_spark_{key}"
        return pipeline_cfg.get(flat_key, default)

    # Defaults tuned for the local docker-compose dev stack (Docker cap
    # ~8GB shared with UC + Airflow + Postgres). Earlier 2g/2g caused
    # the Spark driver to be SIGKILL'd mid-write (exit -9), leaving
    # orphaned Delta files that cascade into
    # `DELTA_CREATE_TABLE_WITH_NON_EMPTY_LOCATION` on subsequent
    # attempts. Override per-table or per-env via pipeline_config.
    return {
        "driver_memory": _get("driver_memory", "1g"),
        "driver_cores": int(_get("driver_cores", 1)),
        "executor_memory": _get("executor_memory", "1g"),
        "executor_cores": int(_get("executor_cores", 1)),
        "num_executors": int(_get("num_executors", 1)),
        "shuffle_partitions": int(_get("shuffle_partitions", 4)),
        "broadcast_threshold": _get("broadcast_threshold", "10m"),
        "dynamic_allocation": bool(_get("dynamic_allocation", False)),
        "max_executors": int(_get("max_executors", 1)),
    }


def build_spark_conf(pipeline_cfg: Mapping[str, Any]) -> dict[str, str]:
    """Build the ``--conf`` map for SparkSubmit.

    Carries ONLY the parallelism knobs from LLD §6.3 (shuffle partitions,
    broadcast threshold, driver cores). Catalog wiring — Delta extensions,
    ``spark_catalog=DeltaCatalog``, the named ``unity`` side catalog, and
    ``spark.sql.defaultCatalog=unity`` — is owned by the runner's
    :func:`patient_360.utils.delta_helpers.build_spark_session` (LLD §13
    Decision 12, re-adopted 2026-06-18). The runner runs in-process under
    ``local[*]`` and sets that conf on the same session, so the wrapper must
    NOT inject catalog/extensions/metastore conf — doing so reintroduces the
    deprecated Derby/Hive metastore and conflicts with UC registration.

    Dynamic allocation is wired only when explicitly enabled so DEV stays
    deterministic.
    """
    c = _resolve_compute(pipeline_cfg)
    conf: dict[str, str] = {
        "spark.sql.shuffle.partitions": str(c["shuffle_partitions"]),
        "spark.sql.autoBroadcastJoinThreshold": str(c["broadcast_threshold"]),
        # Airflow 3.x SparkSubmitOperator removed the ``driver_cores`` kwarg
        # (only ``driver_memory`` survives as a first-class field). Pass the
        # value through the conf map so ``spark-submit --conf
        # spark.driver.cores=N`` lands on the command line.
        "spark.driver.cores": str(c["driver_cores"]),
    }
    if c["dynamic_allocation"]:
        conf["spark.dynamicAllocation.enabled"] = "true"
        conf["spark.dynamicAllocation.maxExecutors"] = str(c["max_executors"])
    return conf


# ---------------------------------------------------------------------------
# Operator factory
# ---------------------------------------------------------------------------
def build_spark_submit_task(
    *,
    task_id: str,
    config_path: str,
    pipeline_cfg: Mapping[str, Any],
    spark_conn_id: str = "spark_default",
    extra_application_args: list[str] | None = None,
    operator_kwargs: Mapping[str, Any] | None = None,
) -> Any:
    """Return a configured ``SparkSubmitOperator`` for one Bronze table.

    Parameters
    ----------
    task_id
        Airflow task id (e.g. ``ingest_patients``); the factory derives
        this from the per-table YAML filename.
    config_path
        Path to the per-table YAML (e.g.
        ``airflow/configs/patients.yml``); passed to the runner as
        ``--config-path``.
    pipeline_cfg
        Pipeline config dict from ``config-template.yaml``. Provides
        compute knobs (LLD §6.1, §6.3) and the entry-point module
        (LLD §7).
    spark_conn_id
        Airflow Spark connection id. Defaults to ``spark_default``;
        override per-env via the DAG factory.
    extra_application_args
        Optional extra args appended after ``--config-path``. The
        runner's ``--ds`` is injected automatically using Airflow's
        ``{{ ds }}`` template.
    operator_kwargs
        Passthrough kwargs for retries / timeout (LLD §4.2 / §8.1) and
        any per-task overrides. Anything explicitly set by this wrapper
        (memory, cores, conf, application) is preserved -- caller kwargs
        of the same name are dropped with a warning.

    Returns
    -------
    SparkSubmitOperator
        Ready to attach to a DAG / TaskGroup.
    """
    # Local import keeps the wrapper importable in non-Airflow contexts
    # (e.g. pure-Python unit tests via importlib).
    from airflow.providers.apache.spark.operators.spark_submit import (  # type: ignore[import-not-found]
        SparkSubmitOperator,
    )

    entry_module = _resolve_entry_module(pipeline_cfg)
    application = _resolve_application_path(entry_module)
    compute = _resolve_compute(pipeline_cfg)
    spark_conf = build_spark_conf(pipeline_cfg)

    application_args = [
        "--config-path",
        str(config_path),
        "--ds",
        "{{ ds }}",
    ]
    if extra_application_args:
        application_args.extend(extra_application_args)

    # Explicit kwargs we own. Anything in operator_kwargs that collides
    # is dropped (with a warning) so the wrapper's contract is stable.
    # Airflow 3.x SparkSubmitOperator dropped the ``driver_cores`` kwarg;
    # the value is forwarded via ``spark.driver.cores`` in ``conf`` (see
    # build_spark_conf). Do NOT add ``driver_cores`` here — it raises
    # TypeError at DAG parse time.
    owned: dict[str, Any] = {
        "task_id": task_id,
        "application": application,
        "conn_id": spark_conn_id,
        "conf": spark_conf,
        "driver_memory": compute["driver_memory"],
        "executor_memory": compute["executor_memory"],
        "executor_cores": compute["executor_cores"],
        "num_executors": compute["num_executors"],
        "application_args": application_args,
        # `--packages` ensures Delta JARs land on the driver classpath
        # before SparkSession boots; required for DeltaSparkSessionExtension.
        "packages": ",".join(DEFAULT_PACKAGES),
    }

    if operator_kwargs:
        clean: dict[str, Any] = {}
        for k, v in operator_kwargs.items():
            if k in owned:
                logger.warning(
                    "spark_submit_wrapper: ignoring caller kwarg %r — "
                    "owned by the wrapper for task_id=%s",
                    k,
                    task_id,
                )
                continue
            clean[k] = v
        owned.update(clean)

    return SparkSubmitOperator(**owned)
