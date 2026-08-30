# LLD Update Session — 2026-06-20 (managed-table infra)

## What was updated
- File: outputs/lld/v1/LLD-2026-06-20-patient-360.md
- Version: 1.21 (Approved) -> 1.22 (Updated - Pending Review)
- Scenario C: same version folder (v1), same date (2026-06-20), in-place edit.

## Problem
The MANAGED SE `_error`/`_stats` audit tables (§2.3 item 3, §8.2, §8.3,
Decision 12 — adopted v1.20) referenced a schema `storage_root` "set by
`scripts/uc_init.py`", but §9 never specified the supporting infra and the
script did not actually set it. Two gaps:
1. UC server did not share the `uc-warehouse` volume the Spark writers use,
   so coordinated commits for MANAGED tables could not resolve.
2. `uc_init.py` created catalog/schemas with NO `storage_root`, so UC 0.5.0
   would reject SE's MANAGED `saveAsTable` (no managed location).

## Changes made (LLD §9 only + scaffold sync)
- §9.1.1: `unity-catalog` service row notes the shared
  `../../uc-warehouse:/tmp/uc-warehouse` mount; added "Managed-table storage &
  coordinated commits" callout documenting the two invariants.
- §9.1: added `make uc-init` bootstrap deploy step + explicit dev-up ordering
  (unity-catalog healthy -> uc-init -> spark-thrift-server healthy ->
  ddl-apply -> DAG).
- §9.3: added `make uc-init` row to Make-targets table.
- §9.5: added UC schema managed `storage_root` health check.
- §13 Decision 12 SE bullet: `storage_root` now names the concrete managed
  location (`file:///tmp/uc-warehouse/<schema>`) + cross-refs §9.1.1.
- §14: version-history row for 1.22.

## Scaffold sync (patient_360/)
- `_infra/docker/docker-compose.yml`: UC server gains
  `../../uc-warehouse:/tmp/uc-warehouse` bind mount.
- `scripts/uc_init.py`: `create_schema` now sends `properties.storage_root`
  per schema; new `--storage-root` arg / `UC_STORAGE_ROOT` env
  (default `file:///tmp/uc-warehouse`). py_compile + ruff clean.
- `Makefile`: new `UC_STORAGE_ROOT ?= file:///tmp/uc-warehouse` var, threaded
  into the existing `uc-init` target.

## Preserved unchanged
§2.3 Bronze runner write pattern (insertInto unity.bronze.<table>), §4 DAG,
§7 catalog block, configs/{dev,stage,prod}.yaml, DMS/STM/DQS.

## Validation
validate-lld: all checks passed, no issues. PostToolUse hook auto-validated
clean on every edit and regenerated config/, dag/, impl-sequence.md. Compose
YAML parses; uc_init.py compiles + lints clean; `make -n uc-init` renders
UC_STORAGE_ROOT correctly.

## Remaining open items
- Re-approval required (Status is Updated - Pending Review) before downstream
  stories re-cut.
- No code generator re-run needed: se_runner.py already addresses SE tables by
  FQN (v1.20 contract); this session only supplies the managed location they
  land in.
