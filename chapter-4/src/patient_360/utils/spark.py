"""SparkSession factory with Delta Lake + Unity Catalog + OpenLineage configuration."""

from __future__ import annotations

from pathlib import Path

from pyspark.sql import SparkSession

# Absolute chapter-4 directory — stable regardless of working directory
_CHAPTER_DIR = Path(__file__).parents[3]

# JAR coordinates — Spark 4.1 uses Scala 2.13 (not 2.12)
# Cached in ~/.ivy2 after first run (~200 MB on first execution)
_SPARK_PACKAGES = ",".join([
    "io.delta:delta-spark_4.1_2.13:4.1.0",
    "io.unitycatalog:unitycatalog-spark_2.13:0.4.0",
    "io.openlineage:openlineage-spark_2.13:1.44.0",
])


def get_spark(
    app_name: str = "patient_360",
    warehouse_path: str = "warehouse",
    master: str = "local[*]",
    uc_uri: str = "http://localhost:8080",
    openlineage_url: str = "http://localhost:5001",
) -> SparkSession:
    """
    Build and return a SparkSession configured for Delta Lake, Unity Catalog, and OpenLineage.

    Unity Catalog (OSS) replaces Derby as the Spark metastore.  All existing 2-part table
    names (e.g. bronze.patients) continue to work because spark_catalog is the UC-backed
    catalog and the default catalog.

    OpenLineage events are emitted to Marquez at openlineage_url on every job run,
    producing a full Bronze → Silver → Gold lineage graph.

    Args:
        app_name: Spark application name.
        warehouse_path: Local path for Delta files (dev only; ignored in production).
        master: Spark master URL. Default is local mode.
        uc_uri: Unity Catalog server base URL.
        openlineage_url: Marquez (or other OpenLineage backend) base URL.

    Returns:
        Configured SparkSession.
    """
    abs_warehouse = str((_CHAPTER_DIR / warehouse_path).resolve())

    return (
        SparkSession.builder.appName(app_name)
        .master(master)
        # ── JARs: Delta + UC connector + OpenLineage ──────────────────────────
        .config("spark.jars.packages", _SPARK_PACKAGES)
        # ── Delta SQL extension ───────────────────────────────────────────────
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        # ── Unity Catalog as spark_catalog ────────────────────────────────────
        # Replaces Derby; all 2-part names (bronze.patients) resolve to UC.
        .config("spark.sql.catalog.spark_catalog", "io.unitycatalog.spark.UCSingleCatalog")
        .config("spark.sql.catalog.spark_catalog.uri", uc_uri)
        .config("spark.sql.catalog.spark_catalog.token", "")
        .config("spark.sql.defaultCatalog", "spark_catalog")
        .config("spark.sql.warehouse.dir", abs_warehouse)
        # ── OpenLineage → Marquez ─────────────────────────────────────────────
        .config("spark.extraListeners", "io.openlineage.spark.agent.OpenLineageSparkListener")
        .config("spark.openlineage.transport.type", "http")
        .config("spark.openlineage.transport.url", openlineage_url)
        .config("spark.openlineage.namespace", "patient_360")
        # ── Performance ───────────────────────────────────────────────────────
        .config("spark.sql.adaptive.enabled", "true")
        .config("spark.ui.enabled", "false")
        .config("spark.driver.memory", "4g")
        .config("spark.executor.memory", "4g")
        .config("spark.sql.shuffle.partitions", "8")
        .getOrCreate()
    )
