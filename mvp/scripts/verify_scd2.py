"""
Verify SCD2 behavior across both load dates.

Checks:
  1. Total rows = current + expired
  2. Changed rows have exactly 2 versions
  3. Expired rows have end_ts = DS2 - 1 day  (2026-03-12)
  4. Expired rows have dim_is_current = false
  5. New current rows have start_ts = DS2    (2026-03-13)
  6. New current rows have end_ts = null
  7. Unchanged rows have exactly 1 version, still current
  8. No surrogate_key duplicates
  9. Dim payers: no-op (all rows still have 1 version)
"""
from __future__ import annotations

from patient_360.utils.spark import get_spark

DS1 = "2026-03-06"
DS2 = "2026-03-13"

PASS = "  PASS"
FAIL = "  FAIL"


def check(label: str, condition: bool) -> None:
    status = PASS if condition else FAIL
    print(f"{status}  {label}")
    if not condition:
        raise AssertionError(label)


def main() -> None:
    spark = get_spark("scd2_verify", warehouse_path="warehouse")

    # Register existing Delta tables from warehouse/
    from pathlib import Path
    warehouse = Path(__file__).parents[1] / "warehouse"
    for db_dir in sorted(warehouse.iterdir()):
        if not db_dir.is_dir():
            continue
        db = db_dir.name.replace(".db", "")
        spark.sql(f"CREATE DATABASE IF NOT EXISTS {db}")
        for tbl_dir in sorted(db_dir.iterdir()):
            if not tbl_dir.is_dir() or "_delta_log" in tbl_dir.name:
                continue
            spark.sql(
                f"CREATE TABLE IF NOT EXISTS {db}.{tbl_dir.name} "
                f"USING delta LOCATION '{tbl_dir.resolve()}'"
            )

    print("\n══════════════════════════════════════════════")
    print(" SCD2 Verification — dim_patients")
    print("══════════════════════════════════════════════")

    patients = spark.table("silver.dim_patients")
    total       = patients.count()
    current     = patients.filter("dim_is_current = true").count()
    expired     = patients.filter("dim_is_current = false").count()
    two_version = patients.groupBy("patient_id").count().filter("count = 2").count()
    one_version = patients.groupBy("patient_id").count().filter("count = 1").count()
    distinct_sk = patients.select("surrogate_key").distinct().count()

    print(f"  Total rows   : {total}")
    print(f"  Current rows : {current}")
    print(f"  Expired rows : {expired}")
    print(f"  Patients w/ 2 versions: {two_version}  (expected ~577)")
    print(f"  Patients w/ 1 version : {one_version}  (expected ~5190)")

    check("current + expired = total",            current + expired == total)
    check("changed patients have 2 versions",      two_version == 577)
    check("unchanged patients have 1 version",     one_version == (5767 - 577))
    check("no surrogate_key duplicates",           distinct_sk == total)

    # Spot-check expired rows
    expired_rows = patients.filter("dim_is_current = false")
    check("expired rows have end_ts = 2026-03-12",
          expired_rows.filter("end_ts != '2026-03-12'").count() == 0)
    check("expired rows have start_ts = 2026-03-06",
          expired_rows.filter("start_ts != '2026-03-06'").count() == 0)

    # Spot-check new current rows (those added in DS2)
    new_current = patients.filter(f"dim_is_current = true AND start_ts = '{DS2}'")
    check("new current rows have start_ts = 2026-03-13", new_current.count() == 577)
    check("new current rows have end_ts = null",
          new_current.filter("end_ts IS NOT NULL").count() == 0)

    # Original current rows unchanged
    orig_current = patients.filter(f"dim_is_current = true AND start_ts = '{DS1}'")
    check("unchanged current rows retained from DS1", orig_current.count() == (5767 - 577))

    print("\n══════════════════════════════════════════════")
    print(" SCD2 Verification — dim_providers")
    print("══════════════════════════════════════════════")

    providers = spark.table("silver.dim_providers")
    total_p   = providers.count()
    current_p = providers.filter("dim_is_current = true").count()
    expired_p = providers.filter("dim_is_current = false").count()
    two_ver_p = providers.groupBy("provider_id").count().filter("count = 2").count()

    print(f"  Total rows   : {total_p}")
    print(f"  Current rows : {current_p}")
    print(f"  Expired rows : {expired_p}")
    print(f"  Providers w/ 2 versions: {two_ver_p}  (expected ~54)")

    check("dim_providers: current + expired = total",   current_p + expired_p == total_p)
    check("dim_providers: changed providers = 54",      two_ver_p == 54)
    check("dim_providers: expired end_ts = 2026-03-12",
          providers.filter("dim_is_current = false AND end_ts != '2026-03-12'").count() == 0)

    print("\n══════════════════════════════════════════════")
    print(" SCD2 Verification — dim_organizations (no changes)")
    print("══════════════════════════════════════════════")

    orgs = spark.table("silver.dim_organizations")
    check("dim_organizations: all rows current (no SCD2 triggers)",
          orgs.filter("dim_is_current = false").count() == 0)
    check("dim_organizations: exactly 1 version per org",
          orgs.groupBy("org_id").count().filter("count > 1").count() == 0)

    print("\n══════════════════════════════════════════════")
    print(" SCD2 Verification — dim_payers (no-op)")
    print("══════════════════════════════════════════════")

    payers = spark.table("silver.dim_payers")
    check("dim_payers: all rows current (payers unchanged across both loads)",
          payers.filter("dim_is_current = false").count() == 0)
    check("dim_payers: exactly 10 rows (no duplicates)",
          payers.count() == 10)

    print("\n══════════════════════════════════════════════")
    print(" SCD2 Verification — Sample changed patient")
    print("══════════════════════════════════════════════")
    changed_pid = (
        patients.groupBy("patient_id").count()
        .filter("count = 2")
        .limit(1)
        .collect()[0]["patient_id"]
    )
    print(f"\n  Patient ID: {changed_pid}")
    patients.filter(f"patient_id = '{changed_pid}'") \
            .select("patient_id", "city", "state", "zip", "start_ts", "end_ts", "dim_is_current") \
            .orderBy("start_ts") \
            .show(truncate=False)

    print("\n══════════════════════════════════════════════")
    print(" ALL CHECKS PASSED")
    print("══════════════════════════════════════════════\n")
    spark.stop()


if __name__ == "__main__":
    main()
