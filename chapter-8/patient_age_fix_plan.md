# Plan: correct calculated_age and harden SCD2 merges in Silver clinical_patients

## Goal

1. `clinical_patients.calculated_age` is the patient's age in whole years as of today. Subtract one
   if the birthday has not happened yet this year. NULL when `birth_date` is NULL. Applies to every
   patient, including deceased ones (no cap at `death_date`).
2. Existing rows pick up the corrected age without creating new SCD2 versions.
3. `apply_scd2` is safe for an hourly DAG whose runs share one `ds`, records deaths as new
   versions, and ignores backfills of an older `ds`.

## Rules for whoever executes this plan

- Change artifacts and generated code only through the `update-*`, `approve-*`, and generator
  skills. Invoke them with the Skill tool. Do not hand-edit artifacts or generated code.
- Skill files (`SKILL.md`, skill scripts) may be hand-edited.
- Every artifact skill call must include this sentence: "Edit the latest existing file in place.
  Do not create a new dated file, a copy, or a `.bak`." Without it, the skills create a new dated
  file when run on a different day.
- Forked skills cannot ask questions. Put the full change request in the skill arguments, as given
  below, and review each diff before running the matching `approve-*` skill.
- `update-silver` refuses to run until every upstream artifact is `Approved`.

## Target behavior

### Age expression

```python
def _calculated_age(birth_date: Column, as_of: Column) -> Column:
    birthday_not_yet_occurred = (F.month(as_of) < F.month(birth_date)) | (
        (F.month(as_of) == F.month(birth_date)) & (F.dayofmonth(as_of) < F.dayofmonth(birth_date))
    )
    return (
        F.year(as_of) - F.year(birth_date) - F.when(birthday_not_yet_occurred, 1).otherwise(0)
    ).cast("int")
```

`as_of` is `F.current_date()` by default. Tests pass a fixed date. A Feb 29 birthday counts as
Mar 1 in non-leap years.

### `clinical_patients` column sets

- Hash columns (14), a change creates a new version: `first_name`, `last_name`, `maiden_name`,
  `address`, `city`, `state`, `county`, `zip`, `marital_status`, `healthcare_expenses`,
  `healthcare_coverage`, `income`, `death_date`, `patient_status`.
- Refresh columns (11), updated in place on the current version: `birth_date`, `prefix`,
  `middle_name`, `suffix`, `race`, `ethnicity`, `gender`, `birth_place`, `lat`, `lon`,
  `calculated_age`.

### `apply_scd2` contract

Signature adds keyword-only `refresh_columns: list[str] | None = None`. Other dimensions do not
pass it and keep their current behavior.

For each natural key in the incoming batch, with `effective_date` = the run's `ds`:

| Case | Condition | Action | Metric |
|---|---|---|---|
| Backfill skip | Current `effective_from` > `effective_date` | No write. Log one WARNING per run | `rows_skipped_backfill` |
| Same-day overwrite | Hash changed, current `effective_from` = `effective_date` | Update the current row in place, including `_record_hash` | `rows_overwritten` |
| Earlier-day change | Hash changed, current `effective_from` < `effective_date` | Close current (`effective_to = effective_date - 1`, `is_current = false`), insert new version | `rows_inserted`, `rows_closed` |
| New key | No current row | Insert | `rows_inserted` |
| Unchanged | Hash equal | No write | `rows_unchanged` |

Hash comparison:

- Cast incoming columns to the target column types before hashing.
- Compare the incoming hash against a hash recomputed from the stored current values, not the
  stored `_record_hash`.
- Where the stored `_record_hash` differs from the recomputed one (hash column list changed),
  rewrite it in place in a separate MERGE before the main MERGE. Metric `rows_rehashed`.

Refresh (only when `refresh_columns` is passed):

- Runs last, as its own MERGE from the incoming batch deduplicated on the natural key.
- Updates only `is_current = true` rows where a refresh column differs under null-safe comparison.
- Skips backfill keys. Produces no Delta commit when nothing differs. Metric `rows_refreshed`.
- Never touches closed versions or `_record_hash`.

Invariants after every run: `(natural key, effective_from)` is unique, `effective_to >=
effective_from`, exactly one current row per key.

The function returns a dict with 7 metrics: `rows_inserted`, `rows_closed`, `rows_unchanged`,
`rows_overwritten`, `rows_skipped_backfill`, `rows_rehashed`, `rows_refreshed`.

## Steps

### 1. DMS

`data-modeler-plugin:update-dms` with:

> Edit the latest existing file in place. Do not create a new dated file, a copy, or a `.bak`.
> clinical_patients: set the §3 `calculated_age` business_rule to "whole years between birth_date
> and CURRENT_DATE, minus 1 if the birthday has not occurred yet this year; NULL when birth_date is
> NULL; no death_date cap". In §6, list the 14 hash columns and 11 refresh columns from this plan.
> State that refresh columns update in place on the current version, that a same-day hash change
> overwrites the current version, and that a backfill older than the current version is skipped.

Review the diff, then run `data-modeler-plugin:approve-dms`.

### 2. STM

`mapping-analyst-plugin:update-stm` with:

> Edit the latest existing file in place. Do not create a new dated file, a copy, or a `.bak`.
> Bronze-to-Silver clinical_patients: set the calculated_age expression to the birthday-adjusted
> rule from DMS §3, remove DEATHDATE from its inputs and remove the COALESCE. Set the `_record_hash`
> expression to the 14 DMS §6 hash columns. Remove Bronze `_scd2_hash` / `_record_hash` rows (Bronze
> has only the DMS §2 metadata columns). Update the Lineage note.

Review the diff, then run `mapping-analyst-plugin:approve-stm`.

### 3. LLD

`technical-lead-plugin:update-lld` with:

> Edit the latest existing file in place. Do not create a new dated file, a copy, or a `.bak`.
> Replace the §2.3 `apply_scd2` contract with the contract in this request: [paste the "apply_scd2
> contract" section of this plan]. Record decisions for: refresh columns updated in place; same-day
> overwrite; backfill skip with warning; hash compared against recomputed stored values with stale
> hashes rewritten in place.

Review the diff, then run `technical-lead-plugin:approve-lld`.

### 4. Stories

`scrum-master-plugin:update-stories` with:

> Edit the latest existing files in place. Do not create new dated files, copies, or `.bak` files.
> Update the Silver SCD2 helper story and the clinical_patients Silver story acceptance criteria to
> match the approved LLD §2.3 `apply_scd2` contract and DMS §6 hash and refresh columns. Update the
> backlog LLD reference to the current LLD version.

Review the diff, then run `scrum-master-plugin:approve-stories`.

### 5. Generator skill

Hand-edit `developer-plugin/skills/create-silver/SKILL.md` so a full regeneration produces the
same code:

- Replace the `apply_scd2` signature and behavior with the contract in this plan.
- Read the hash and refresh column lists from DMS §6, not from a hardcoded list.
- Require the tests listed in step 7 and all 7 metrics.

Check that `developer-plugin/skills/validate-silver/scripts/validate_silver.py` and
`validate-gold/scripts/validate_gold.py` locate the project root by requiring an `outputs/lld`
directory. If `find_upstream_root` accepts any `outputs` directory, it stops at
`patient_360/outputs` and fails. Fix it to require `(cand / "outputs" / "lld").is_dir()`.

### 6. Code

`developer-plugin:update-silver` with:

> Apply the approved DMS §3/§6, STM Bronze-to-Silver, and LLD §2.3 changes for clinical_patients
> and the shared SCD2 helper. Regenerate `utils/scd2.py`, `silver/transform_patients.py`,
> `contracts/clinical_patients.yml`, and their unit tests. transform_patients passes
> `refresh_columns` with the 11 DMS §6 refresh columns. Other dimension transforms keep their
> behavior.

Expected outputs:

- `src/patient_360/utils/scd2.py`: the contract above.
- `src/patient_360/silver/transform_patients.py`: `_calculated_age`, `HASH_COLUMNS` (14),
  `REFRESH_COLUMNS` (11), `refresh_columns=REFRESH_COLUMNS` passed to `apply_scd2`.
- `contracts/clinical_patients.yml`: `scd2.hash_columns` has 14 entries; `calculated_age`
  description matches the rule.

Do not hand-edit any of these. If the output is wrong, fix the artifact or `SKILL.md` and re-run.

### 7. Tests (generated in step 6, confirm they exist)

`tests/silver/test_transform_patients_unit.py`:

- 1990-12-31 as of 2026-11-04 gives 35.
- 1980-12-25 as of 2026-02-11 gives 45.
- Birthday on, the day before, and the day after `as_of`.
- Feb 29 birth: 0 on 2025-02-28, 1 on 2025-03-01.
- NULL birth date gives NULL.
- Deceased patient age ignores `DEATHDATE`.
- Expected ages in `_cleanse` tests are computed from today's date, not hardcoded.
- `transform` passes `refresh_columns` equal to the 11 refresh columns.

`tests/silver/test_scd2_unit.py`:

- Refresh-only change updates in place: same row count, same `effective_from`, no new version.
- Closed versions are never changed by a refresh.
- Same-day hash change overwrites the current row. No duplicate `(key, effective_from)`.
- Earlier-day hash change closes the current row and inserts a new one.
- A `death_date` change creates a new version with `patient_status = DECEASED`.
- Backfill older than the current version writes nothing, logs a warning, counts in
  `rows_skipped_backfill`.
- Stale stored hash is rewritten in place without a new version.
- Duplicate source rows for one key do not fail the MERGE.
- Omitting `refresh_columns` keeps the previous behavior.

### 8. Semantic docs

Update the observed age range in `semantic/entities/patient_summary.yml` and
`ontology/entities/patient.yml` to the range measured after step 10. Then run
`make knowledge-metadata` and `make semantic-validate`.

## Verification

Run from `patient_360/`:

1. `uv run pytest tests/silver tests/utils -v` passes.
2. `make test` and `make lint` pass.
3. `developer-plugin:validate-silver` reports 0 critical.
4. Start the stack (`make dev-up`) and let one scheduled `patient360_hourly_v1` run finish.
   Unpausing and triggering the DAG are user actions when the SRE hook is installed.
5. Read-only checks on Silver `clinical_patients` after the first run:
   - Every current row's `calculated_age` equals the rule for the run date.
   - Current row count is unchanged and no new versions were created.
   - The first run after the hash column change reports `rows_rehashed` equal to the current row
     count. A second run reports 0 for every metric.
   - Every patient with a `death_date` has `patient_status = DECEASED`.
   - `(patient_id, effective_from)` is unique and each patient has one current row.
6. Gold `patient_summary.calculated_age` equals Silver for every patient. Gold needs no code change
   because it reads current Silver rows and overwrites.

Same-day overwrite, backfill skip, and new versions on death are covered by unit tests. Static
source data cannot exercise them in a live run.
