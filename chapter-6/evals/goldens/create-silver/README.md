# create-silver goldens

Phase 1 commits the **scope-claim** golden only — a check that the
emitted `transform_<table>.py` module follows the canonical structure
documented in `SKILL.md` §Phase 3 (imports, TABLE/DOMAIN constants,
`transform(spark, env, ds)` signature, DQ-before-write order, SCD2 vs
fact branch).

A real generated module isn't golden-committable yet because the
table list comes from the LLD/DMS at runtime — committing one would
hardcode `clinical_patients` and lose the project-agnostic claim. Phase
2 will commit per-table goldens against a frozen fixture LLD.

For now, see `tests/test_skill_evals.py::test_create_silver_skill_shape`
which asserts the SKILL.md still names the seven required phases.
