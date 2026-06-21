# Change Brief: SE Runner Interface Gaps

**Date**: 2026-04-21
**From**: Developer Plugin (Bronze Ingestion)
**To**: Technical Lead
**Affects**: LLD §2.3, §3, §5.1, §5.4, §7

---

## Background

The Bronze ingestion layer has been built and is live. During implementation
four gaps were found between the LLD design and what is required at runtime.
This brief requests targeted edits to close those gaps before `se_runner.py`
is built and the DQ layer is wired up.

---

## Gap 1 — `dq_env` resolution not specified (§2.3, §5.4)

**Problem**: SE v2 rules are keyed by `dq_env: {DEV, QA, PROD}` (spark-expectations
convention). The pipeline's runtime `--env` flag uses `DEV | STAGING | PROD` (LLD §7,
config-template.yaml). There is no mapping between the two, so `run_dq` cannot
deterministically pick a rule profile.

**Required LLD change**: Add a one-line mapping table to §2.3 under `se_runner.py`
and to §5.4 (Inline SE Validation):

| runtime `--env` | SE `dq_env` |
|-----------------|-------------|
| `DEV`           | `DEV`       |
| `STAGING`       | `QA`        |
| `PROD`          | `PROD`      |

`run_dq` must accept an `env` parameter and pass the mapped value to spark-expectations.

---

## Gap 2 — `run_dq` signature is incomplete (§2.3)

**Problem**: Current §2.3 states `run_dq` inputs are "DataFrame, table name, action_if_failed".
The actual call site is:
```python
run_dq(df, table=cfg.dq_rules_table, action_if_failed=cfg.se_action_if_failed)
```
Missing `env` (needed for dq_env resolution above) and `dq_rules_dir` (path to
`dq_rules/` so the runner can locate `{table}.yml`).

**Required LLD change**: Update §2.3 `se_runner.py` Input line to:
```
Input: DataFrame, table (str), env (str), action_if_failed (str),
       dq_rules_dir (Path) — locates dq_rules/{table}.yml
```

---

## Gap 3 — `se_action_if_failed` override semantics undefined (§5.4)

**Problem**: Each SE rule in `dq_rules/{table}.yml` already carries its own
`action_if_failed` field. The per-table YAML also has `se_action_if_failed`.
The LLD does not say whether the YAML value *overrides* per-rule actions or is
only a *fail-closed default* when a rule omits its own action.

**Required LLD change**: Add one sentence to §5.4 clarifying:

> The per-table YAML `se_action_if_failed` is the **fail-closed default** for
> any rule that does not declare its own `action_if_failed`. Per-rule declarations
> take precedence.

---

## Gap 4 — Quarantine path not defined (§3, §7)

**Problem**: §2.3 says `se_runner.py` "routes rejections to quarantine paths" but
neither the per-table YAML schema nor §3 (Storage Layout) defines the quarantine
directory. Running `action_if_failed: drop` with no quarantine path is a
runtime error.

**Required LLD change**:
- Add `quarantine_path` to the per-table YAML schema in §7 (Configuration Schema):
  ```yaml
  quarantine_path: warehouse/{env}/quarantine/bronze/{table}/
  ```
- Add a row to §3 storage layout for `warehouse/{env}/quarantine/`.

---

## Gap 5 — Soft-import degradation not documented (§2.3, §8)

**Problem**: `ingestion_runner.py` currently wraps the `se_runner` import in a
`try/except ImportError`, logs a WARNING, and passes the DataFrame through unchanged
if SE is not installed. This is an intentional bootstrap choice (SE is not yet
implemented) but is undocumented. Either it should be a declared degradation path
or it should be removed when `se_runner.py` lands.

**Required LLD change**: Add a note to §2.3 under `se_runner.py`:

> **Bootstrap mode**: Until `se_runner.py` is implemented, `ingestion_runner.py`
> soft-imports it. A missing import logs `WARNING: se_runner not available` and
> passes data through without DQ validation. Once `se_runner.py` is shipped this
> fallback must be removed — ingestion must fail closed if SE is unavailable.

Also add to §8 (Error Handling): SE import failure is a WARNING in bootstrap mode
and a CRITICAL failure post-implementation.

---

## Gap 6 — Metadata column names not pinned (§2.3, §3)

**Problem**: The three metadata columns added to every Bronze table are `ds`,
`_ingested_at`, `_source_batch_id`. The SE rules in `dq_rules/{table}.yml`
reference these column names verbatim. The LLD does not name them.

**Required LLD change**: Add to §2.3 `ingestion_runner.py` Responsibility:

> Adds three metadata columns — `ds` (partition date, string `YYYY-MM-DD`),
> `_ingested_at` (ingestion timestamp, `TimestampType`), and
> `_source_batch_id` (deterministic `{table}:{ds}`, `StringType`) — before
> writing Delta. SE rules in `dq_rules/{table}.yml` reference these names verbatim;
> renaming them requires a matching SE rules update.

---

## Gap 7 — Implementation status of `se_runner.py` and `reconciliation.py` (§2.3)

**Problem**: Both modules are listed in §2.3 and referenced throughout §5 as if
they exist. Neither has been implemented yet. This is misleading for any developer
reading the LLD to understand build scope.

**Required LLD change**: Add `[PENDING IMPLEMENTATION]` marker to the §2.3 entries
for `se_runner.py` and `reconciliation.py`, and add an open item to §13 (Decision Log):

> **D-NEW**: `se_runner.py` and `reconciliation.py` are not yet implemented.
> Bronze ingestion runs in bootstrap mode (no inline DQ). These must be built
> before the pipeline can be promoted to STAGING.
