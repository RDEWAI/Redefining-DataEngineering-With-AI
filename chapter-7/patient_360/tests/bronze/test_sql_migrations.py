"""STORY-02-004 -- Bronze DDL migration contract tests (plain .sql).

Asserts the dated plain-SQL migrations under ``ddl/migrations/`` satisfy the
story's acceptance criteria (LLD §9.1, §13 Decision 12, DMS §2). Liquibase was
removed (developer-plugin L-015): on UC OSS + Spark Thrift no Liquibase path
works, so DDL lives as plain dated ``.sql`` applied via ``beeline -f`` in
lexical (dated/sequenced bronze->silver->gold) order.

* AC1 -- one migration per Bronze table, count matches LLD §5.1 (13); every
  migration pre-creates a UC EXTERNAL Delta table via
  ``CREATE TABLE unity.bronze.synthea_<t> ... USING DELTA LOCATION``.
* AC3 -- every migration carries a ``-- rollback:`` comment with a DROP
  (the plain-SQL replacement for the Liquibase ``<rollback>``).

Naming: ``<YYYYMMDD>_<NNN>_<table>.sql`` -- a plain lexical sort yields the
apply order. Pure stdlib -- no Liquibase, XML, or Spark dependency.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS_DIR = PROJECT_ROOT / "ddl" / "migrations"

# LLD §5.1 Bronze table count (one migration per Bronze table).
EXPECTED_BRONZE_COUNT = 13

# Bronze migrations end in `_synthea_<table>.sql`.
BRONZE_MIGRATIONS = sorted(MIGRATIONS_DIR.glob("*_synthea_*.sql"))

# `<YYYYMMDD>_<NNN>_<table>.sql`
NAME_RE = re.compile(r"^\d{8}_\d{3}_[a-z0-9_]+\.sql$")


def _table_of(path: Path) -> str:
    # strip the `<date>_<NNN>_` prefix -> `synthea_<table>`
    return path.stem.split("_", 2)[2]


def test_bronze_migration_count_matches_lld() -> None:
    assert len(BRONZE_MIGRATIONS) == EXPECTED_BRONZE_COUNT, (
        f"expected {EXPECTED_BRONZE_COUNT} Bronze migrations (LLD §5.1), "
        f"found {len(BRONZE_MIGRATIONS)}: {[p.name for p in BRONZE_MIGRATIONS]}"
    )


@pytest.mark.parametrize("path", BRONZE_MIGRATIONS, ids=lambda p: p.name)
def test_migration_name_is_dated_and_ordered(path: Path) -> None:
    assert NAME_RE.match(path.name), (
        f"{path.name}: must be `<YYYYMMDD>_<NNN>_<table>.sql` so a lexical "
        f"sort gives the apply order"
    )


@pytest.mark.parametrize("path", BRONZE_MIGRATIONS, ids=lambda p: p.name)
def test_migration_pre_creates_uc_external_delta(path: Path) -> None:
    sql = path.read_text()
    table = f"unity.bronze.{_table_of(path)}"
    assert table in sql, f"{path.name}: CREATE TABLE must target {table}"
    assert "USING DELTA" in sql, f"{path.name}: must declare USING DELTA"
    assert "LOCATION" in sql, f"{path.name}: EXTERNAL table must declare a LOCATION (Decision 12)"
    assert "${PATIENT360_WAREHOUSE_ROOT}" in sql, (
        f"{path.name}: LOCATION must use ${{PATIENT360_WAREHOUSE_ROOT}} "
        f"(substituted by ddl-apply.sh)"
    )


@pytest.mark.parametrize("path", BRONZE_MIGRATIONS, ids=lambda p: p.name)
def test_every_migration_has_rollback_comment(path: Path) -> None:
    """AC3 -- the plain-SQL rollback is a `-- rollback: DROP ...` comment."""
    sql = path.read_text()
    m = re.search(r"^--\s*rollback:\s*(DROP\s+TABLE.+)$", sql, flags=re.MULTILINE | re.IGNORECASE)
    assert m, (
        f"{path.name}: must carry a `-- rollback: DROP TABLE ...` comment "
        f"(LLD §9.1 rollback requirement, plain-SQL form)"
    )
