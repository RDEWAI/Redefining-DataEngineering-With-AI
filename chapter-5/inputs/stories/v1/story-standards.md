# Story Standards — Patient 360 Data Pipeline

| Field | Value |
|-------|-------|
| **Document Version** | 1.0 |
| **Last Updated** | 2026-03-23 |
| **Author** | Scrum Master |
| **Applicable Project** | Patient 360 |

---

## 1. Story Template

Every story MUST follow this structure:

### Required Sections
1. **User Story** — "As a {persona}, I want {goal} so that {benefit}"
2. **Description** — Detailed technical description (minimum 3 sentences)
3. **Acceptance Criteria** — Checkboxes with upstream artifact references
4. **Technical Notes** — Implementation hints, upstream references
5. **Estimation Support** — Table mapping to DMS/STM/DQS/LLD sections
6. **Verification** — YAML mapping each AC to one or more verifier specs (parsed by `developer-plugin/scripts/verify_acs.py`)
7. **Testing** — Table of automated coverage rows (Unit / Contract / Integration / Smoke / DQ / Benchmark) per story type. Required minimums per type below. Maps DoD criterion #2 / #3 / #4 onto concrete tests.
8. **How to Test (User)** — Prerequisites + ≥1 numbered Step + Expected outcome that a human can run on their own machine. Required for `build`, `integration-test`, `runtime-bootstrap`. Maps DoD criterion #2 / #3 onto a runnable runbook.
9. **Documentation Updates** — List of specific README/runbook sections that must change. Required for `runtime-bootstrap`, `integration-test`, `release`. Maps DoD criterion #6 onto a concrete edit list.

### Runtime-Bootstrap Coverage Rules

A `runtime-bootstrap` story's Acceptance Criteria must verify every executor
that downstream `build` stories will invoke. The fixed checklist (JDK / Docker
/ UC catalog+schemas / source seed / UC API 200) is the **floor**, not the
ceiling — each backlog must add ACs derived from the LLD §6.1 `local_executor_mode`:

| LLD §6.1 `local_executor_mode` | Bootstrap MUST add an AC like… |
|---|---|
| `in-airflow-local[*]` (chapter-5 default) | `docker compose exec airflow spark-submit --master 'local[2]' --version` reports the pinned Spark version (4.0.0) AND `docker compose exec airflow python -c "from spark_expectations.core.expectations import SparkExpectations"` exits 0 |
| `sidecar-spark` | `docker compose exec airflow-worker spark-submit --master spark://spark-master:7077 --version` returns 0 AND `curl http://localhost:8080/api/2.1/unity-catalog/catalogs` returns 200 |
| `external-cluster` | `airflow tasks test <bronze-dag-id> <one-spark-task> <ds>` exits 0 against the configured cluster |

Validator rule `STORIES-BOOTSTRAP-COVERAGE-001` enforces this: if any `build`
story references `SparkSubmitOperator`, `spark-submit`, `pyspark`, or
`--master`, the runtime-bootstrap story(ies) collectively must contain ≥1 AC
that mentions one of `spark-submit`, `spark.master`, `pyspark`, `--master`,
or `airflow tasks test`. Without this rule, "the stack is up" can be true
while no Spark task can actually run — exactly the gap that motivated the
runtime-bootstrap story type.

### Optional Sections
- **Mockup / Diagram** — Visual aid if applicable
- **Out of Scope** — What this story explicitly does NOT cover

---

## 2. Definition of Done

A story is "Done" when ALL of the following are met:

| # | Criterion | Verifier | Story-section that maps to it |
|---|-----------|----------|-------------------------------|
| 1 | Code committed to feature branch | Developer | (git) |
| 2 | Unit tests written and passing | Developer | `## Testing` (Unit row) → `## Verification` (`pytest:`) |
| 3 | Integration test passing (if applicable) | Developer | `## Testing` (Integration row) → `## Verification` (`pytest: marker: integration`) |
| 4 | DQ rules implemented per DQS reference | QA | `## Testing` (DQ row) → `## Verification` (Spark Expectations runner output) |
| 5 | Code reviewed by at least 1 peer | Reviewer | (PR) |
| 6 | Documentation updated (if applicable) | Developer | `## Documentation Updates` (≥1 README change) |
| 7 | Deployed to staging environment | CI/CD | `## Testing` (Deploy smoke for `deploy-validation` stories) |

`developer-plugin:complete-stories` enforces the testing rows by running
`verify_acs.py` and refusing to flip Status to `Done` on any FAIL exit.
Manual verifiers stay INDETERMINATE and require an explicit
`User-Verified-By:` line at the bottom of the story before they're
treated as PASS.

---

## 3. Acceptance Criteria Format

Acceptance criteria MUST:
- Use checkbox format: `- [ ] Criterion text [Upstream §X.Y]`
- Reference at least one upstream artifact section
- Be testable / verifiable (not vague)
- Use active voice ("Table contains..." not "Table should contain...")

### Examples

**Good:**
```
- [ ] bronze_patients table created with 12 columns matching DMS §4.2
- [ ] Null patient_id records rejected per DQS §3.1.1
- [ ] Ingestion completes within 5-minute SLA per HLD §5.4
```

**Bad:**
```
- [ ] Data is loaded correctly
- [ ] Quality checks pass
- [ ] Everything works
```

---

## 4. Story Sizing Guidelines

| Points | Complexity | Example |
|--------|-----------|---------|
| 1 | Trivial — config change, simple fix | Update a YAML config value |
| 2 | Small — single table, straightforward | Create one bronze table DDL |
| 3 | Medium — multi-step, one domain | Bronze ingestion for 3 related tables |
| 5 | Large — cross-domain, some complexity | Silver transformation with business rules |
| 8 | Very large — max allowed per story | Gold dimensional model with SCD Type 2 |
| 13 | Too large — MUST be split | Never assign 13 points |

---

## 5. Priority Scheme

| Priority | Definition | Sprint Placement |
|----------|-----------|-----------------|
| P1 — Critical Path | Blocks other stories; no workaround | Sprint 1-2 |
| P2 — Important | Needed for completeness; has workaround | Sprint 2-3 |
| P3 — Nice to Have | Improves quality or DX; can defer | Sprint 3+ |
