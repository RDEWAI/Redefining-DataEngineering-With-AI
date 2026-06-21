"""Spark Expectations runner — inline DQ for every Bronze write.

LLD references: §2.3 item 3 (`se_runner.py` interface contract, v1.20), §5.4
(Inline SE Validation), §8.2-§8.3 (error/stats tables + alerting), §8.6 + §13
Decision 14 (single-state fail-closed import contract), §13 Decision 12
(corrected 2026-06-20: UC 0.5.0 named side-catalog; SE stats/error tables are
per-table MANAGED `catalogManaged` UC tables addressed by 3-part FQN).

Contract
--------
``run_dq(df, *, table, env, dq_rules_dir, action_if_failed=None,
quarantine_path=None)`` wraps Nike Spark Expectations
(``SparkExpectations.with_expectations``) around a DataFrame and returns the
validated frame. Failing ``row_dq`` rows are routed to the SE-managed error
table; aggregate stats land in the SE-managed stats table.

**SE stats / error tables are MANAGED Unity Catalog tables (UC 0.5.0)** —
addressed by a per-table **3-part fully-qualified name** derived from the FQN
``target_table`` (LLD §2.3 item 3 v1.20 / §13 Decision 12 corrected
2026-06-20):

* ``target_table`` is the FQN ``unity.<schema>.<table>`` (read from the rules
  YAML ``dq_env.<ENV>.table_name``; if that value is a bare name it is
  qualified to ``unity.bronze.<table>``).
* SE derives the error table as ``f"{target_table}_error"`` and the stats
  table is passed explicitly as ``f"{target_table}_stats"`` — both well-formed
  3-part FQNs.
* Both writers are MANAGED:
  ``WrappedDataFrameWriter().mode("append").format("delta")`` with **no**
  ``.option("path", ...)``. SE creates both as ``catalogManaged`` tables via
  ``saveAsTable`` on first run, in the schema's ``storage_root`` set by
  ``scripts/uc_init.py``. They are SE-owned — NOT pre-created in Liquibase.
* ``se.enable.error.table`` and ``se.enable.stats.table`` both stay ``True``.
  The MANAGED ``_error`` table is the primary rejected-row audit trail; the
  per-table source schema makes the per-table FQN derivation mandatory (a
  single shared ``bronze_se_stats`` name collides across tables on schema).

**Why managed (corrected 2026-06-20, §13 Decision 12).** The earlier
path-based design (``warehouse/{env}/_se/<table>/`` via ``.option("path")``)
was adopted on UC 0.4.0 under the mistaken belief that ``UCSingleCatalog``
refuses RTAS/CTAS/``saveAsTable``. The TRUE 0.4.0 failure was an
**empty-namespace ``fullTableNameForApi`` defect**: a BARE error name
(``synthea_patients_error``) under spark-submit (empty session
current-database) made ``fullTableNameForApi`` split a length-0 namespace and
crash with ``ArrayIndexOutOfBoundsException`` — it was never an RTAS refusal.
UC **0.5.0** fixes the namespace handling AND supports managed ``saveAsTable``
creates, so an FQN ``target_table`` makes SE's ``<target>_error`` / ``_stats``
managed-table writes succeed. Requires UC server 0.5.0 + delta-spark 4.1+
coordinated commits (floors in LIBRARIES.md / ``library-imports.yaml``).
Business Bronze/Silver/Gold tables remain EXTERNAL by design (Decision 15) —
only the SE audit tables are MANAGED.

Per-row failures honour ``action_if_failed`` resolution order:

1. The per-rule ``action_if_failed`` declared in the YAML rule.
2. The per-table fail-closed default passed in via ``action_if_failed``.

``env`` is the pipeline runtime flag and is mapped to the SE ``dq_env``
selector before rule load:

+----------------+----------------+
| runtime ``env``| SE ``dq_env``  |
+================+================+
| ``DEV``        | ``DEV``        |
| ``STAGING``    | ``QA``         |
| ``PROD``       | ``PROD``       |
+----------------+----------------+

The mapping lives in :data:`_DQ_ENV_MAP` so it is verifiable from tests.

Spark Expectations version requirement
--------------------------------------
This module requires ``spark-expectations >= 2.10.0`` for the YAML rule
loader and ``WrappedDataFrameWriter`` APIs. Earlier versions raise
``ModuleNotFoundError`` for ``spark_expectations.rules``.

updated: 2026-06-20 — STORY-01-010 / STORY-02-010 (v2.9) / LLD §2.3 item 3
(v1.20) / §13 Decision 12 (corrected): switch the SE error/stats tables from
PATH-BASED to per-table MANAGED Unity Catalog tables addressed by 3-part FQN.
``target_table`` is the FQN ``unity.bronze.<table>`` (bare ``table_name``
values are qualified); error = ``f"{target}_error"``, stats =
``f"{target}_stats"``. ``se.enable.error.table`` re-enabled (True). Both
writers are ``WrappedDataFrameWriter().mode("append").format("delta")`` with
NO ``.option("path")``. The path-based ``_se/<table>/{stats,errors}`` writers
and the ``_delta_path_identifier`` / ``se_stats_path`` / ``se_error_path`` /
``_ensure_se_path`` helpers are removed. Kafka/notification disable keys and
the bare-name temp-view registration (for ``query_dq`` sibling resolution) are
preserved.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING

from spark_expectations.core.expectations import (  # noqa: I001
    SparkExpectations,
    WrappedDataFrameWriter,
)
from spark_expectations.rules.plugins.yaml_loader import (
    SparkExpectationsYamlRuleLoaderImpl,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from pyspark.sql import DataFrame

logger = logging.getLogger(__name__)


# LLD §2.3 / §5.4 — runtime --env → SE dq_env selector. Exposed at module
# scope so unit tests can parametrise over it without re-importing.
_DQ_ENV_MAP: dict[str, str] = {
    "DEV": "DEV",
    "STAGING": "QA",
    "PROD": "PROD",
}

# LLD §2.3 item 3 (v1.20) / §13 Decision 12 (corrected 2026-06-20) — the SE
# stats + error tables are per-table MANAGED Unity Catalog tables. SE derives
# them from the FQN ``target_table`` as ``<fqn>_error`` / ``<fqn>_stats``
# (3-part names). These suffixes name the SE companion tables; they are NOT
# path leaves and NOT a shared catalog table.
SE_STATS_SUFFIX = "_stats"
SE_ERROR_SUFFIX = "_error"

# Default UC catalog + Bronze schema used to qualify a bare ``table_name``
# from the dq_rules YAML into a 3-part FQN. Overridable via env vars so the
# module never hardcodes the project's catalog/schema (LLD §13 Decision 12).
UC_CATALOG_ENV = "SE_UC_CATALOG"
UC_BRONZE_SCHEMA_ENV = "SE_UC_BRONZE_SCHEMA"
_DEFAULT_UC_CATALOG = "unity"
_DEFAULT_UC_BRONZE_SCHEMA = "bronze"

# Env var that anchors every relative warehouse path (LLD §9.1). Kept for
# parity with the rest of the runtime; the SE audit tables no longer use it.
PROJECT_ROOT_ENV = "PATIENT360_PROJECT_ROOT"


def _qualify_target_table(table_name: str) -> str:
    """Return a 3-part FQN for the SE ``target_table``.

    LLD §2.3 item 3 (v1.20): SE addresses its ``<target>_error`` / ``_stats``
    companion tables by deriving the suffix off ``target_table``. That target
    MUST be a 3-part FQN (``unity.<schema>.<table>``) so the derived names are
    well-formed — a BARE name crashes UC's ``fullTableNameForApi`` on the
    empty namespace under spark-submit (the true UC-0.4.0 defect; §13
    Decision 12 corrected).

    Resolution:

    * Already a 3-part (``a.b.c``) or 2-part (``a.b``) name → returned as-is.
    * Bare name → qualified to ``${SE_UC_CATALOG}.${SE_UC_BRONZE_SCHEMA}.<n>``
      (defaults ``unity.bronze.<n>``).
    """
    if "." in table_name:
        return table_name
    catalog = os.environ.get(UC_CATALOG_ENV, _DEFAULT_UC_CATALOG)
    schema = os.environ.get(UC_BRONZE_SCHEMA_ENV, _DEFAULT_UC_BRONZE_SCHEMA)
    return f"{catalog}.{schema}.{table_name}"


def _resolve_dq_rules_dir(dq_rules_dir: Path | str | None) -> Path:
    """Resolve the dq_rules directory using the AIRFLOW_CONFIGS_DIR pattern.

    Resolution order (LLD §2.3):

    1. Explicit argument passed by the caller.
    2. ``DQ_RULES_DIR`` environment variable — the canonical container path
       injected by the cookiecutter ``docker-compose.yml``.
    3. ``/opt/dq_rules`` as a last-resort fallback for non-container runs.

    The literal ``"airflow/configs"`` / relative paths are never hardcoded
    here — the env var is the single resolution mechanism (see
    ``validate-dag DAG-PATHS-002`` regression rule).
    """
    if dq_rules_dir is not None:
        return Path(dq_rules_dir)
    env_dir = os.environ.get("DQ_RULES_DIR")
    if env_dir:
        return Path(env_dir)
    return Path("/opt/dq_rules")


def run_dq(
    df: DataFrame,
    *,
    table: str,
    env: str,
    dq_rules_dir: Path | str | None = None,
    action_if_failed: str | None = None,
    quarantine_path: str | None = None,
) -> DataFrame:
    """Run inline Spark Expectations validation against ``df``.

    Parameters
    ----------
    df:
        Input DataFrame about to be written to Bronze.
    table:
        Logical table name. Used to locate ``dq_rules/{table}.yml`` and to
        scope SE stats rows via ``product_id``.
    env:
        Runtime environment flag (``DEV | STAGING | PROD``). Mapped to SE
        ``dq_env`` via :data:`_DQ_ENV_MAP`.
    dq_rules_dir:
        Optional override for the SE rules directory. Defaults to the
        ``DQ_RULES_DIR`` env var, then ``/opt/dq_rules``.
    action_if_failed:
        Per-table fail-closed default for any rule whose YAML omits its own
        ``action_if_failed`` (LLD §5.4). One of ``fail | drop | ignore``.
    quarantine_path:
        Optional SECONDARY quarantine sink (LLD §8.2). With UC 0.5.0 the
        MANAGED ``<target>_error`` table is the primary rejected-row audit
        trail; this argument is retained for backwards compatibility but no
        longer redirects the SE error writer to a filesystem path.

    Returns
    -------
    DataFrame
        The validated DataFrame ready to be written to the Bronze target.

    Raises
    ------
    KeyError
        If ``env`` is not one of ``DEV | STAGING | PROD``.
    FileNotFoundError
        If the resolved rules file does not exist.
    """
    if env not in _DQ_ENV_MAP:
        raise KeyError(f"Unknown env={env!r}; expected one of {sorted(_DQ_ENV_MAP)}")
    dq_env = _DQ_ENV_MAP[env]

    rules_dir = _resolve_dq_rules_dir(dq_rules_dir)
    rules_yaml = rules_dir / f"{table}.yml"
    if not rules_yaml.exists():
        # Fall back to `.yaml` — both extensions are used in practice.
        alt = rules_dir / f"{table}.yaml"
        if alt.exists():
            rules_yaml = alt
        else:
            raise FileNotFoundError(f"SE rules file not found: {rules_yaml} (or {alt})")

    rules_df = SparkExpectationsYamlRuleLoaderImpl().load_rules(
        str(rules_yaml),
        format="yaml",
        options={"dq_env": dq_env},
    )

    # CRITICAL: SE selects which rules to run by filtering the rules table on
    # (product_id == ctx.product_id) AND (table_name == target_table)
    # (spark_expectations/utils/reader.py). The loaded rules carry the file's
    # `product_id` and a per-env `table_name` from the `dq_env.<ENV>` block.
    # If we pass the bare table name for product_id/target_table, ZERO rules
    # match → `_row_dq` is False → SE silently runs NO row_dq/agg_dq/query_dq
    # at all (no validation, no `drop`). Read the matching identifiers straight
    # from the rules YAML so the filter actually selects this table's rules.
    import yaml as _yaml  # local import; pyyaml is a runtime dep

    with open(rules_yaml, encoding="utf-8") as _rf:
        _rules_doc = _yaml.safe_load(_rf) or {}
    se_product_id = _rules_doc.get("product_id") or table
    # `dq_env` may be a per-env mapping ({DEV: {table_name: ...}, ...}); guard
    # against a scalar/malformed value so resolution falls back to the bare
    # table name instead of raising.
    _dq_env_block = _rules_doc.get("dq_env")
    _env_entry = _dq_env_block.get(dq_env) if isinstance(_dq_env_block, dict) else None
    _raw_target = (_env_entry.get("table_name") if isinstance(_env_entry, dict) else None) or table

    # LLD §2.3 item 3 (v1.20) / §13 Decision 12 (corrected) — the SE
    # `target_table` MUST be a 3-part FQN so SE's derived `<target>_error`
    # (and the explicit `<target>_stats`) are well-formed MANAGED UC tables.
    # A bare `table_name` is qualified to `unity.bronze.<table>`; an already
    # qualified value (e.g. `unity.bronze.synthea_patients`) is passed through.
    se_target_table = _qualify_target_table(_raw_target)
    se_stats_table = f"{se_target_table}{SE_STATS_SUFFIX}"
    se_error_table = f"{se_target_table}{SE_ERROR_SUFFIX}"

    # Referential `query_dq` rules reference sibling tables by BARE name
    # (e.g. `FROM clinical_observations c LEFT JOIN clinical_patients p ...`).
    # With `spark.sql.defaultCatalog=unity`, a bare 1-part name does NOT
    # resolve to `unity.silver.<t>` (it looks in the default schema), so the
    # rule SQL fails. Register every UC bronze/silver/gold table as a
    # bare-name TEMP VIEW (LLD §2.3 v1.17 AC3) so those references resolve,
    # then register the in-flight `df`
    # LAST under THIS table's bare name — so the referential SQL validates the
    # rows actually being processed (which, at the SCD2/insert source stage,
    # are not yet in the catalog table).
    _spark = df.sparkSession
    for _schema in ("bronze", "silver", "gold"):
        try:
            _siblings = _spark.sql(f"SHOW TABLES IN unity.{_schema}").collect()
        except Exception:  # schema may not exist yet (e.g. cold warehouse)
            continue
        for _row in _siblings:
            _tn = _row["tableName"]
            try:
                _spark.sql(
                    f"CREATE OR REPLACE TEMP VIEW {_tn} AS SELECT * FROM unity.{_schema}.{_tn}"
                )
            except Exception:  # noqa: S110 — best-effort view registration
                pass
    # The in-flight DataFrame wins over any same-named sibling view.
    df.createOrReplaceTempView(table)

    # Disable Kafka stats streaming + every notifier — required to keep
    # local (non-Databricks) runs free of Databricks-secret lookups.
    #
    # LLD §2.3 item 3 (v1.20) / §13 Decision 12 (corrected 2026-06-20) — BOTH
    # the SE error / rejected-rows table AND the stats table are ENABLED. On
    # UC 0.5.0 SE writes them as MANAGED `catalogManaged` UC tables via
    # `saveAsTable` against the 3-part FQNs `<target>_error` / `<target>_stats`
    # — which succeeds (the prior `se.enable.error.table=False` workaround
    # diagnosed an empty-namespace AIOOBE on BARE names as an RTAS refusal; the
    # FQN target fixes the real cause). The `row_dq` `drop` action removes
    # failing rows from the returned DataFrame AND persists them to the managed
    # `_error` audit table.
    user_conf: dict[str, object] = {
        "se.enable.error.table": True,
        "se.enable.stats.table": True,
        "se.streaming.enable": False,
        "spark.expectations.notifications.alert.flag.disable": True,
        "spark.expectations.notifications.email.enabled": False,
        "spark.expectations.notifications.slack.enabled": False,
        "spark.expectations.notifications.teams.enabled": False,
        "spark.expectations.notifications.pagerduty.enabled": False,
        "spark.expectations.notifications.zoom.enabled": False,
    }
    if action_if_failed:
        # Fail-closed per-table default; per-rule declarations still win
        # because SE consults the rule row first.
        user_conf["se.default_action_if_failed"] = action_if_failed

    # AC8 (LLD §2.3 v1.17/v1.20) — column stability. Capture the input schema
    # BEFORE `with_expectations`: SE APPENDS run-tracking columns
    # (`meta_dq_run_id`, `meta_dq_run_datetime`) to the DataFrame it returns.
    # Projecting back to `input_cols` after validation drops those appended
    # columns so the returned schema equals the input schema. This lets any
    # caller (e.g. Bronze `write_bronze` → `insertInto(unity.bronze.<table>)`)
    # write the validated frame straight to the pre-created target without a
    # Delta schema mismatch (`_LEGACY_ERROR_TEMP_DELTA_0007`). The run-tracking
    # values still persist in the SE stats table, not the data table.
    input_cols = df.columns

    # MANAGED writers (LLD §2.3 item 3 v1.20 / §13 Decision 12 corrected). NO
    # `.option("path", ...)` — SE writes both audit tables as `catalogManaged`
    # UC tables via `saveAsTable` against the 3-part FQNs. Business
    # Bronze/Silver/Gold tables stay EXTERNAL (Decision 15); only these SE
    # audit tables are MANAGED.
    error_writer = WrappedDataFrameWriter().mode("append").format("delta")
    stats_writer = WrappedDataFrameWriter().mode("append").format("delta")

    # SE consumes `stats_table` as a SQL identifier (SHOW TBLPROPERTIES /
    # ALTER TABLE) and a writer target. Hand it the 3-part FQN
    # `<target>_stats` so it resolves to a MANAGED UC table.
    se = SparkExpectations(
        product_id=se_product_id,
        rules_df=rules_df,
        stats_table=se_stats_table,
        stats_table_writer=stats_writer,
        target_and_error_table_writer=error_writer,
        debugger=False,
    )

    logger.info(
        "SE run_dq table=%s env=%s dq_env=%s action_if_failed=%s rules=%s "
        "target_table=%s stats_table=%s error_table=%s",
        table,
        env,
        dq_env,
        action_if_failed,
        rules_yaml,
        se_target_table,
        se_stats_table,
        se_error_table,
    )

    # spark-expectations' `with_expectations` is a decorator: it returns a
    # wrapper that expects a *function* producing a DataFrame, not a
    # DataFrame itself. Wrap `df` in a no-arg lambda, then invoke the
    # wrapped callable to get the validated DataFrame back.
    decorated = se.with_expectations(
        target_table=se_target_table,
        user_conf=user_conf,
        target_and_error_table_writer=error_writer,
    )(lambda: df)
    validated = decorated()
    # AC8 — drop SE's appended run-tracking columns so the returned schema
    # matches the input (see `input_cols` capture above).
    return validated.select(*input_cols)


__all__ = [
    "_DQ_ENV_MAP",
    "SE_STATS_SUFFIX",
    "SE_ERROR_SUFFIX",
    "_qualify_target_table",
    "run_dq",
]
