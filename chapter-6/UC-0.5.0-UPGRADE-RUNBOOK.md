# Unity Catalog 0.5.0 / Spark 4.1 Upgrade — Runbook

**Date:** 2026-06-20 · **Scope of the change set:** artifacts + skills + code (no live
infra run this pass). This runbook covers (A) what changed, (B) the build-time version tokens
no generator reconciled, and (C) the deferred live deploy + validation steps.

---

## A. What changed (all via skills / approved artifacts)

| Layer | Result |
|---|---|
| **Versions** (`inputs/code/v1/LIBRARIES.md` + `library-imports.yaml` + pattern docs) | pyspark **4.1.1** (capped by delta-spark 4.3.0 `requires_dist: pyspark<=4.1.1`), delta-spark **4.3.0**, UC server **v0.5.0**, connector **`unitycatalog-spark_4.1_2.13:0.5.0`** (new `_4.1` infix), openlineage **1.50.0** |
| **Artifacts** | LLD **v1.21**, DQS **v2.2**, Stories backlog **v2.9** — updated + approved; validators clean |
| **Naming** | All 26 `dq_rules/*.yml` `dq_env.<ENV>.table_name` → 3-part FQN (`unity.bronze.*` / `unity.silver.*`) |
| **DQ audit** | SE error/stats tables re-enabled as **managed `catalogManaged`** UC tables by FQN (`unity.<schema>.<table>_error`/`_stats`); `se.enable.error.table=True`; path-based writers removed |
| **Mechanism** | The RTAS/Decision-12 misdiagnosis is corrected everywhere → true cause = empty-namespace `fullTableNameForApi` AIOOBE on bare names (UC 0.4.0), fixed in 0.5.0 |
| **Code** (via update-scaffold / update-ingestion / update-silver) | `se_runner.py` (managed FQN + `_qualify_target_table`), `spark_submit_wrapper.py` (`DEFAULT_PACKAGES`), reconciliation evidence gate, `pyproject.toml`, `uv.lock`, `docker-compose.yml`, `Makefile` |

**Business tables stay EXTERNAL + `insertInto` / SCD2 MERGE** — only the SE audit tables are managed.

---

## B. Build-time version tokens — ✅ RESOLVED (2026-06-20)

These were **outside the default `sync-infra` scope** (it covers compose/pyproject/Makefile only)
and the cookiecutter template hardcoded them, so they had drifted. **Now fixed:**

| File | Was | Now |
|---|---|---|
| `patient_360/_infra/docker/Dockerfile.airflow` | `pyspark==4.1.2` | `pyspark==4.1.1` ✅ |
| `patient_360/_infra/docker/Dockerfile.thrift` | `apache/spark:4.1.0` + `spark-examples_2.13-4.1.0.jar` | `apache/spark:4.1.1` + `...-4.1.1.jar` ✅ |
| `patient_360/scripts/bsql.sh` | `delta-spark_2.13:4.0.0` | `delta-spark_2.13:4.3.0` ✅ |

How it was fixed (skill-driven): (1) extended `update-scaffold`'s `sync-infra` SKILL.md spec to
reconcile these tokens against `LIBRARIES.md`; (2) bumped the cookiecutter template literals
(`inputs/lld/v1/templates/.../Dockerfile.airflow`, `docker-compose.yml`, `Makefile`) so fresh
renders start correct; (3) re-ran `update-scaffold sync-infra` with an explicit token directive.
Verified: no stale Spark/Delta tokens remain in `src`/`_infra`/`scripts`/`pyproject`.

> Note: SKILL.md edits only drive a skill run if the **installed** plugin copy is refreshed
> (`make install-plugins`) — the source edit is for future installs; this session's behavior was
> driven by the explicit `.skill-arg` directives.

---

## C. Managed-table infra (coordinated commits) — ✅ RESOLVED (2026-06-20, LLD v1.22)

The managed `catalogManaged` error/stats tables need the UC 0.5.0 commit coordinator. Both infra
pieces are now wired (LLD §9.1.1 v1.22 + scaffold sync):

1. **Schema managed location (`storage_root`)** ✅ — `scripts/uc_init.py` now sends
   `properties.storage_root` per schema (`--storage-root` / `UC_STORAGE_ROOT`, default
   `file:///tmp/uc-warehouse`, → `file:///tmp/uc-warehouse/<schema>`), threaded through the
   `make uc-init` target. Without it SE's managed `saveAsTable` would fail with
   `FAILED_PRECONDITION: Neither catalog nor schema has managed location configured`.
2. **Shared `_delta_log` filesystem** ✅ — the `unity-catalog` service now mounts the same
   warehouse volume as Spark (`../../uc-warehouse:/tmp/uc-warehouse`), so the commit coordinator
   and the writer see the same `_delta_log`.

Business Bronze/Silver/Gold tables remain EXTERNAL with explicit Liquibase `LOCATION` — only the
SE `_error`/`_stats` managed tables use the `storage_root`.

---

## D. Deferred live deploy + validation steps

1. **Build + push the UC 0.5.0 server image** (no released image): build from source at tag
   `v0.5.0` (mirror `make uc-ui-source`), tag `patient_360-uc:v0.5.0` (or your registry), push.
2. Apply the §B token fixes and the §C infra (uc_init `storage_root` + UC server shared volume).
3. `cd patient_360 && uv lock && make dev-up` — brings up the stack, runs `uc-init` + beeline
   `ddl-apply` (bronze + silver EXTERNAL business tables; the SE `_error`/`_stats` managed tables
   are SE-created on first run, NOT in Liquibase).
4. Trigger `patient360_hourly_v1` (or run a single bronze/silver task via spark-submit).
5. **Verify the managed error table works** — feed rows that fail a rule and confirm
   `unity.bronze.<table>_error` exists and holds the rejected rows
   (`DESCRIBE HISTORY` / `SELECT COUNT(*)`); confirm `unity.bronze.<table>_stats` records
   input/error/output counts.
6. `make validate-ingestion && make validate-silver` → PASS.

---

## E. Pre-existing issues — ✅ RESOLVED (2026-06-20)

- **63 `tests/silver/test_transform_*` failures** (`PYTHON_VERSION_MISMATCH`, Spark worker 3.11 vs
  driver 3.12) — ✅ fixed: `tests/conftest.py` now pins `PYSPARK_PYTHON` / `PYSPARK_DRIVER_PYTHON`
  to `sys.executable` at collection time. `tests/silver/` → **99 passed**.
- **4 `test_dq_rules_contract::test_ac3_critical_tables_have_fail_action` failures**
  (`organizations`, `providers`, `payers`) — ✅ fixed via DQS **v2.3**: added DQ-REC-011/012/013
  source-to-bronze row-count reconciliation rules (`action_if_failed: fail`, `is_active: true`),
  re-synced into the three bronze `dq_rules` (FQN preserved). `test_dq_rules_contract.py` → **73 passed**.

### Still open (separate, surfaced during #3 — NOT part of this upgrade)
- **`tests/bronze/test_dag_unit.py::test_dag_concurrency_and_max_active_runs`** — asserts
  `max_active_tasks == 16` but the DAG sets `1`. DAG config drift, owned by `create-dag`/`update-dag`;
  does not touch any upgrade artifact. Fix in a separate DAG pass if desired.

---

## F. Verification status (this pass — no live infra)

- ✅ `dq_rules/*.yml` — all 26 `table_name` are 3-part FQN.
- ✅ `se_runner.py` — managed FQN, `se.enable.error.table=True`, no `.option("path")` writers.
- ✅ `validate-ingestion` PASS · `validate-silver` PASS (per generator runs).
- ✅ `pyproject.toml` + `uv.lock` resolve (pyspark 4.1.1 + delta-spark 4.3.0).
- ⚠️ `validate-gold` FAILs — Gold layer is still stubbed (out of scope; expected).
- ⚠️ §B Dockerfile/bsql tokens + §C managed-table infra — fix before live build.
