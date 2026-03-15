"""
Local pipeline runner — uses classic Spark + Delta (not Spark Connect).

Use this for local development and demos.
In production (Databricks / cloud), use:
    spark-pipelines run --spec spark-pipeline.yml

Usage:
    uv run python run_local.py --layer bronze --ds 2026-03-06
    uv run python run_local.py --layer silver --ds 2026-03-06
    uv run python run_local.py --layer gold   --ds 2026-03-06
    uv run python run_local.py --layer all    --ds 2026-03-06
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from patient_360.bronze.ingest import ingest_all
from patient_360.silver.dims import run_dims
from patient_360.silver.facts import run_facts
from patient_360.gold.patient_summary import run_gold
from patient_360.utils.spark import get_spark

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

RAW_DATA_PATH = Path(__file__).parents[1] / "data" / "raw"


def main():
    parser = argparse.ArgumentParser(description="Patient 360 local pipeline runner")
    parser.add_argument("--layer", choices=["bronze", "silver", "gold", "all"], required=True)
    parser.add_argument("--ds", default="2026-03-06", help="Load date YYYY-MM-DD")
    parser.add_argument("--raw-path", default=str(RAW_DATA_PATH), help="Path to raw CSV directory")
    args = parser.parse_args()

    spark = get_spark(app_name=f"patient_360_{args.layer}")
    # Unity Catalog persists schemas across sessions — CREATE IF NOT EXISTS is idempotent.
    spark.sql("CREATE DATABASE IF NOT EXISTS bronze")
    spark.sql("CREATE DATABASE IF NOT EXISTS silver")
    spark.sql("CREATE DATABASE IF NOT EXISTS gold")

    if args.layer in ("bronze", "all"):
        logger.info("Running bronze layer (ds=%s)...", args.ds)
        ingest_all(spark, ds=args.ds, raw_path=Path(args.raw_path))

    if args.layer in ("silver", "all"):
        logger.info("Running silver dims (ds=%s)...", args.ds)
        run_dims(spark, ds=args.ds)
        logger.info("Running silver facts (ds=%s)...", args.ds)
        run_facts(spark, ds=args.ds)

    if args.layer in ("gold", "all"):
        logger.info("Running gold layer (ds=%s)...", args.ds)
        run_gold(spark, ds=args.ds)

    logger.info("Done.")
    spark.stop()


if __name__ == "__main__":
    main()
