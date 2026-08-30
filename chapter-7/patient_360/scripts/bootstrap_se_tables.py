"""Deprecated — SE stats/error tables are now PATH-BASED (no pre-creation).

LLD §13 Decision 12 / 15 + STORY-01-010 AC7: Spark Expectations writes its
stats and error Delta tables to filesystem paths under
``warehouse/{env}/_se/`` via ``.option("path", ...).save()``, OUTSIDE the
Unity Catalog catalog. ``UCSingleCatalog`` rejects ``saveAsTable``-create,
so there is no catalog registration (``CREATE TABLE ... USING DELTA
LOCATION``) for the SE tables and nothing to pre-create — Delta materialises
the path on the first append.

This module previously pre-created ``unity.bronze.bronze_se_stats`` /
``...bronze_se_errors`` as EXTERNAL Delta tables to dodge a CREATE race. That
race no longer exists in the path-based model, and pre-registering the
tables in UC contradicts the path-based contract. The script is kept as a
no-op shim so any stale ``make`` target / docs reference still exits 0.

Resolve the SE table paths with
``patient_360.utils.se_runner.se_stats_path(env)`` /
``se_error_path(env)`` if you need the on-disk locations.
"""

from __future__ import annotations


def main() -> int:
    print(
        "bootstrap_se_tables: no-op — SE stats/error tables are path-based "
        "(LLD §13 Decision 12/15). Nothing to pre-create."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
