"""Delta Lake write utilities for Unity Catalog compatibility."""

from __future__ import annotations

from pyspark.sql import DataFrame, SparkSession


def save_as_delta_table(
    spark: SparkSession,
    df: DataFrame,
    table: str,
    mode: str = "overwrite",
    partition_by: list[str] | None = None,
    replace_where: str | None = None,
) -> None:
    """
    Write df to a Delta location and register the table in Unity Catalog.

    Uses path-based writes to avoid REPLACE TABLE AS SELECT (RTAS), which is
    not supported by UCSingleCatalog (the UC OSS Spark V2 catalog connector).
    The ``CREATE TABLE IF NOT EXISTS ... LOCATION`` call is idempotent, so
    subsequent runs simply append/overwrite data without re-registering.

    Args:
        spark:        Active SparkSession.
        df:           DataFrame to write.
        table:        Fully qualified table name (e.g. "silver.fct_encounters").
        mode:         Write mode — "overwrite" or "append".
        partition_by: Partition column(s), or None for unpartitioned tables.
        replace_where: Dynamic partition overwrite predicate (e.g. "ds = '2026-03-06'").
    """
    warehouse = spark.conf.get("spark.sql.warehouse.dir")
    parts = table.split(".")
    schema_name, table_name = parts[-2], parts[-1]
    location = f"{warehouse}/{schema_name}/{table_name}"

    writer = df.write.format("delta").mode(mode)
    if replace_where:
        writer = writer.option("replaceWhere", replace_where)
    if partition_by:
        writer = writer.partitionBy(*partition_by)
    writer.save(location)

    # Partition info is embedded in the Delta log; no need to declare PARTITIONED BY
    # in DDL (which would require an explicit schema when used with LOCATION).
    spark.sql(
        f"CREATE TABLE IF NOT EXISTS {table} USING DELTA LOCATION '{location}'"
    )
